"""``gww clean`` command implementation.

Removes worktrees (and their local branches) whose branch satisfies the
active filter -- ``--merged`` (default) marks a worktree cleanable when
its branch has an upstream MR/PR in the merged state, ``--all`` skips
that check entirely. See ``docs/handoff-gww-clean-v2.md`` for the locked
contract and ``docs/adr/0015-cleanup-filter-polymorphism.md``,
``docs/adr/0017-cli-based-provider-no-direct-api.md``,
``docs/adr/0018-cleanup-exit-code-only-provider-contract.md`` and
``docs/adr/0019-provider-resolution-user-config-only.md`` for the
design rationale.

The implementation deliberately composes existing primitives rather than
introducing a new ``worktree remove``-style helper, so the per-worktree
side-effect order (``before_remove`` actions, ``git worktree remove``,
``git branch -d``) reuses the same criticality semantics as ``gww
remove``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from gww.actions import ActionError, MatcherError, apply_actions
from gww.cli.context import (
    CommandContext,
    CommandExit,
    RuleFailure,
    exit_on_error,
    load_config_or_exit,
    parse_uri_or_exit,
    print_action_failure_summary,
    resolve_source_repo,
)
from gww.config.validator import ProviderConfig
from gww.git.branch import (
    BranchNotFoundError,
    delete_branch,
    get_default_branch,
    is_main_branch,
    local_branch_exists,
)
from gww.git.repository import (
    GitCommandError,
    get_remote_uri,
)
from gww.git.worktree import (
    Worktree,
    WorktreeDirtyError,
    WorktreeNotFoundError,
    list_worktrees,
    remove_worktree,
)
from gww.providers import match_provider
from gww.template.evaluator import TemplateError, evaluate_template
from gww.template.functions import TemplateContext


PROVIDER_TIMEOUT_SECONDS = 60


def _run_provider_command(rendered: str) -> int:
    """Run a rendered provider command and return its exit code.

    Both stdout and stderr are inherited from the parent so the user sees
    the provider's output live (ADR-0018 §"Stream handling"). No parsing
    happens here -- the caller treats any non-zero exit as "do not remove".

    The shell binary itself is always present (it is the Python executable
    that calls into ``/bin/sh``), so ``FileNotFoundError`` cannot be
    raised for a missing leading command under ``shell=True``. The shell
    exits with ``127`` for "command not found"; the caller distinguishes
    that case from other non-zero exits so the per-branch ``X: skip
    (<command> not found)`` label fires correctly.

    ``set -o pipefail`` is enabled at the shell level so composed
    pipelines (e.g. ``tea pulls list … | jq -e …``) propagate an
    upstream provider failure rather than letting ``jq`` exit 0 on an
    empty stream mask it. POSIX shells that do not recognise the option
    (``dash``, macOS ``/bin/bash`` 3.x) silently ignore it.

    Args:
        rendered: Shell command to execute.

    Returns:
        The command's exit code.

    Raises:
        subprocess.TimeoutExpired: If the command exceeds the 60s timeout.
    """
    return subprocess.run(
        f"set -o pipefail; {rendered}",
        shell=True,
        timeout=PROVIDER_TIMEOUT_SECONDS,
        stdout=None,
        stderr=None,
        check=False,
    ).returncode


EXIT_COMMAND_NOT_FOUND = 127


def _command_name(rendered: str) -> str:
    """Extract the leading command name from a rendered shell string.

    Used purely for the ``X: skip (<command> not found)`` label so the user
    sees which binary is missing. We split on the first whitespace, which
    is good enough for ``gh``, ``glab``, ``tea`` and for composed
    ``tea | jq`` pipelines (where ``tea`` is the binary).

    Args:
        rendered: Rendered shell command.

    Returns:
        Leading command name, or ``""`` if the string is empty.
    """
    return rendered.split()[0] if rendered.strip() else ""


def _provider_template_for_branch(
    provider: ProviderConfig,
    branch: str,
    uri_string: str | None,
) -> str:
    """Render the provider's ``merged`` template against ``branch``.

    Builds a :class:`TemplateContext` populated with branch and (when
    available) the source's origin URI so predicates in the command
    template can reference ``branch()`` / ``host()`` etc. ``uri_string``
    is parsed defensively; a malformed remote URI is treated as "no URI
    context" rather than failing the whole command.

    Args:
        provider: User-declared :class:`ProviderConfig` whose ``merged``
            template to render.
        branch: Worktree branch to substitute into the template.
        uri_string: Source's origin URI string, or ``None`` if not set.

    Returns:
        Rendered shell command string.

    Raises:
        CommandExit: With code 2 if the template fails to evaluate
            (treated as a config error).
    """
    context = TemplateContext(
        branch=branch,
        tags={},
    )
    if uri_string:
        context.uri = parse_uri_or_exit(uri_string)

    try:
        return evaluate_template(provider.merged, context)
    except TemplateError as e:
        raise CommandExit(2, f"Config error: provider merged template: {e}") from e


def _git_merged_branch_set(source_path: Path, default_branch: str) -> set[str]:
    """Return the set of local branches fully merged into ``default_branch``.

    Implements the ``--merged`` git fallback (ADR-0015) by shelling out
    to ``git branch --merged <default_branch> --format=%(refname:short)``
    from the source. ``--format`` is documented in git since 2.10 and is
    used by the existing :func:`list_local_branches` so we know it
    works in our supported git versions.

    Args:
        source_path: Path to the source repository.
        default_branch: Branch to test merge-against (``main`` /
            ``master``).

    Returns:
        Set of local branch names fully merged into ``default_branch``.
        Returns an empty set on git failure so the caller treats
        everything as "not merged" rather than crashing.
    """
    proc = subprocess.run(
        ["git", "branch", "--merged", default_branch,
         "--format=%(refname:short)"],
        cwd=source_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return set()
    return {
        line.strip()
        for line in proc.stdout.splitlines()
        if line.strip() and line.strip() != default_branch
    }


def _resolve_default_branch(source_path: Path) -> str:
    """Return the source's default branch name (``main`` / ``master``).

    Used both as the comparison branch for the ``--merged`` git fallback
    and as the filter that excludes the main checkout from the cleanable
    set. Falls back to the heuristic from :func:`get_default_branch`.

    Args:
        source_path: Path to the source repository.

    Returns:
        ``"main"`` or ``"master"`` -- whichever exists locally; the
        remote ``origin`` is consulted if neither local branch exists.

    Raises:
        CommandExit: With code 1 if the source has neither ``main`` nor
            ``master`` locally or on ``origin`` -- a configured but
            broken repo.
    """
    try:
        return get_default_branch(source_path)
    except Exception as e:  # BranchError or GitCommandError
        raise CommandExit(
            1,
            f"Error: Could not determine default branch for {source_path}: {e}",
        ) from e


def _enumerate_worktrees(source_path: Path) -> list[Worktree]:
    """Return the worktrees attached to ``source_path``.

    The first entry of ``git worktree list --porcelain`` is the source
    repository itself (the "main checkout"); callers filter it out via
    :meth:`Worktree.is_bare` / path comparison, not here, so that policy
    lives in one place.

    Args:
        source_path: Path to the source repository.

    Returns:
        List of :class:`gww.git.worktree.Worktree` objects in source
        iteration order.

    Raises:
        CommandExit: With code 1 if the worktree listing fails.
    """
    try:
        return list_worktrees(source_path)
    except GitCommandError as e:
        raise CommandExit(1, f"Error listing worktrees: {e}") from e


def _main_checkout_path(source_path: Path) -> Path:
    """Return the main checkout path -- the entry that is never cleanable.

    Args:
        source_path: Path to the source repository (already the "main"
            checkout by construction).

    Returns:
        Resolved source path.
    """
    return source_path.resolve()


def _is_main_worktree(worktree_path: Path, main_path: Path) -> bool:
    """Test whether ``worktree_path`` is the source's main checkout.

    Resolves symlinks / ``..`` segments on both sides before comparing so
    the test holds even when one path is reached via different
    components.

    Args:
        worktree_path: Path of the worktree being considered.
        main_path: Resolved path of the source's main checkout.

    Returns:
        ``True`` if the worktree IS the main checkout.
    """
    try:
        return worktree_path.resolve() == main_path
    except OSError:
        return False


def _prompt_confirmation(
    filter_label: str,
    provider_label: str | None,
) -> bool:
    """Prompt the user to confirm the destructive batch.

    Reads one line from stdin. ``y`` (case-insensitive, with optional
    leading whitespace) confirms; anything else (including EOF) is a
    decline. The prompt format matches the locked Phase 1 contract from
    the handoff.

    Args:
        filter_label: ``"--merged"`` or ``"--all"`` for the prompt.
        provider_label: Provider kind (``"github"``/...) when
            ``filter_label == "--merged"`` and a provider resolved;
            otherwise ``None`` (renders the bare ``"--merged"`` label).

    Returns:
        ``True`` if the user confirmed with ``y``, ``False`` otherwise.
    """
    label = filter_label
    if filter_label == "--merged" and provider_label:
        label = f"{filter_label} (provider: {provider_label})"
    try:
        answer = input(f"Filter: {label}. Delete matching worktrees? [y/N] ")
    except EOFError:
        return False
    return answer.strip().lower() == "y"


def _format_summary(
    *,
    removed: int,
    kept: int,
    failed: int,
    timed_out: int,
    dry_run: bool,
) -> str:
    """Build the end-of-execution summary line per the locked format.

    Zero counts are omitted for terseness. ``failed`` is always 0 in
    dry-run mode (no side effects ran).

    Args:
        removed: Number of worktrees removed (or "would remove").
        kept: Number of worktrees left in place.
        failed: Number of per-worktree ``git worktree remove`` /
            ``git branch -d`` failures.
        timed_out: Number of per-branch provider-command timeouts.
        dry_run: Whether this is a dry-run summary.

    Returns:
        The summary line, terminated by no trailing newline.
    """
    parts: list[str] = []
    if dry_run:
        parts.append(f"Would remove {removed}; would keep {kept}")
        if timed_out > 0:
            parts.append(f"{timed_out} timed out")
    else:
        parts.append(f"Removed {removed}; kept {kept}")
        if failed > 0:
            parts.append(f"{failed} failed")
        if timed_out > 0:
            parts.append(f"{timed_out} timed out")
    return "; ".join(parts)


def _run_git_pass_through(args: list[str], cwd: Path) -> int:
    """Run a git command with both stdout and stderr inherited.

    Used for ``git worktree remove`` and ``git branch -d`` in ``gww
    clean``. Mirrors the existing ``_run_git(..., pass_through_stdout=...)``
    semantics from ``src/gww/git/repository.py`` but adds stderr
    pass-through too, which the existing helper does not provide.

    Args:
        args: Git command arguments (without the leading ``git``).
        cwd: Working directory.

    Returns:
        The git command's exit code.
    """
    cmd = ["git"] + args
    return subprocess.run(
        cmd,
        cwd=cwd,
        stdout=None,
        stderr=None,
        text=True,
        check=False,
    ).returncode


def _delete_branch_silent(
    source_path: Path,
    branch: str,
    force: bool,
    pass_through: bool,
) -> int:
    """Delete a local branch, returning its exit code.

    Wraps :func:`gww.git.branch.delete_branch` so the per-worktree loop
    can use the existing git-level guard (``BranchNotFoundError``,
    etc.) without try/except boilerplate at every call site. The
    pass-through path runs git directly so the user sees git's own
    output, so we pre-check existence there -- ``git branch -d
    <missing>`` exits non-zero with a noisy stderr that would otherwise
    inflate ``failed`` even though cleanup is functionally complete
    (e.g. a ``before_remove`` action deleted the branch first).

    Args:
        source_path: Source repo path.
        branch: Branch to delete.
        force: ``True`` to use ``-D`` (force-delete un-merged branches).
        pass_through: Whether to stream git's stdout/stderr to the user.

    Returns:
        Exit code from ``git branch -d`` / ``-D``. Always 0 when the
        branch is already gone (treated as a successful no-op).
    """
    if pass_through:
        if not local_branch_exists(source_path, branch):
            return 0
        flag = "-D" if force else "-d"
        return _run_git_pass_through(["branch", flag, branch], source_path)
    try:
        delete_branch(source_path, branch, force=force)
    except BranchNotFoundError:
        return 0
    except GitCommandError:
        return 1
    return 0


@exit_on_error
def run_clean(ctx: CommandContext) -> int:
    """Execute the ``gww clean`` command.

    See ``docs/handoff-gww-clean-v2.md`` for the locked contract this
    function implements. Briefly:

    1. Resolve source repo from CWD; list its worktrees.
    2. Filter out the main checkout and the source's default branch.
    3. For each surviving worktree, under ``--merged`` evaluate the
       provider's ``merged`` template (falling back to
       ``git branch --merged <default>`` when no provider resolves) and
       keep / clean the worktree per its exit code.
    4. After enumeration, prompt (unless ``--yes`` / ``--dry-run``).
    5. For each cleanable worktree, run ``before_remove`` actions
       (re-using :func:`gww.actions.apply_actions` with ``kind="before_remove"``),
       then ``git worktree remove``, then ``git branch -d``. ``--force``
       escalates both git steps but NOT the MR filter.
    6. Print the end-of-execution summary and return 0 / 1 depending on
       whether any per-worktree git step failed.

    Args:
        ctx: Per-invocation command context.

    Returns:
        Exit code (0 for clean run with no per-worktree git failures,
        1 for any per-worktree git failure, 2 for config error).
    """
    use_merged: bool = ctx.clean_merged
    use_all: bool = ctx.clean_all
    dry_run: bool = ctx.dry_run
    yes: bool = ctx.clean_yes
    force: bool = ctx.force

    if use_merged and use_all:
        raise CommandExit(
            1,
            "Error: --merged and --all are mutually exclusive.",
        )

    if not use_merged and not use_all:
        use_merged = True

    source_path = resolve_source_repo(Path.cwd())
    main_path = _main_checkout_path(source_path)

    default_branch = _resolve_default_branch(source_path)

    config = load_config_or_exit()

    origin_uri: str | None = get_remote_uri(source_path)

    provider: ProviderConfig | None = None
    if use_merged and origin_uri:
        try:
            parsed_uri = parse_uri_or_exit(origin_uri)
        except CommandExit:
            parsed_uri = None
        if parsed_uri is not None:
            provider = match_provider(config.providers, parsed_uri.host)

    worktrees = _enumerate_worktrees(source_path)

    candidate_branches: list[str] = []
    for wt in worktrees:
        if _is_main_worktree(wt.path, main_path):
            continue
        if wt.is_bare or wt.is_detached:
            continue
        if wt.branch is None or wt.branch == default_branch:
            continue
        if is_main_branch(wt.branch):
            continue
        candidate_branches.append(wt.branch)

    if not candidate_branches:
        label = "--merged" if use_merged else "--all"
        if dry_run:
            print(f"Filter: {label}. No matching worktrees.")
        else:
            print(f"Filter: {label}. No matching worktrees.")
        return 0

    git_merged_set: set[str] | None = None
    if use_merged and provider is None:
        git_merged_set = _git_merged_branch_set(source_path, default_branch)

    cleanable: list[str] = []
    kept: list[str] = []
    timed_out = 0

    provider_label: str | None = provider.kind if provider is not None else None

    for branch in candidate_branches:
        print(f"checking {branch}")
        sys.stdout.flush()

        is_cleanable: bool
        if use_all:
            is_cleanable = True
            label = "clean"
        elif provider is not None:
            try:
                rendered = _provider_template_for_branch(
                    provider, branch, origin_uri,
                )
            except CommandExit as e:
                print(f"{branch}: {e.message or ''}".rstrip(), file=sys.stderr)
                raise
            try:
                exit_code = _run_provider_command(rendered)
            except subprocess.TimeoutExpired:
                print(f"{branch}: skip (timeout)")
                kept.append(branch)
                timed_out += 1
                continue
            if exit_code == EXIT_COMMAND_NOT_FOUND:
                cmd_name = _command_name(rendered)
                msg = cmd_name if cmd_name else "command"
                print(f"{branch}: skip ({msg} not found)")
                kept.append(branch)
                continue
            if exit_code == 0:
                is_cleanable = True
                label = "clean"
            else:
                is_cleanable = False
                label = "keep"
        else:
            if git_merged_set is not None and branch in git_merged_set:
                is_cleanable = True
                label = "clean"
            else:
                is_cleanable = False
                label = "keep"

        print(f"{branch}: {label}")

        if is_cleanable:
            cleanable.append(branch)
        else:
            kept.append(branch)

    if not cleanable:
        summary = _format_summary(
            removed=0,
            kept=len(kept),
            failed=0,
            timed_out=timed_out,
            dry_run=dry_run,
        )
        print(summary)
        return 0

    if not dry_run and not yes:
        filter_label = "--merged" if use_merged else "--all"
        confirmed = _prompt_confirmation(filter_label, provider_label)
        if not confirmed:
            return 0

    if dry_run:
        summary = _format_summary(
            removed=len(cleanable),
            kept=len(kept),
            failed=0,
            timed_out=timed_out,
            dry_run=True,
        )
        print(summary)
        return 0

    failures: list[RuleFailure] = []
    removed = 0
    failed = 0

    worktree_by_branch: dict[str, Path] = {}
    for wt in worktrees:
        if wt.branch is not None:
            worktree_by_branch[wt.branch] = wt.path

    for branch in cleanable:
        worktree_path = worktree_by_branch.get(branch)
        if worktree_path is None:
            failed += 1
            continue

        per_branch_failures: list[RuleFailure] = []

        if config.actions:
            uri = None
            if origin_uri:
                try:
                    uri = parse_uri_or_exit(origin_uri)
                except CommandExit:
                    uri = None
            context = TemplateContext(
                uri=uri,
                branch=branch,
                source_path=source_path,
                dest_path=worktree_path,
                tags=ctx.tags,
            )
            try:
                rule_bundles = apply_actions(
                    config.actions, context, kind="before_remove",
                )
            except MatcherError as e:
                raise CommandExit(2, f"Config error: {e}") from e

            if rule_bundles:
                ctx.verbose_msg(f"Executing {len(rule_bundles)} rule(s)...")
                for bundle in rule_bundles:
                    for action in bundle.actions:
                        try:
                            action.run(
                                source_dir=source_path,
                                target_dir=worktree_path,
                                pass_through_stdout=not ctx.quiet,
                            )
                        except ActionError as e:
                            per_branch_failures.append(
                                RuleFailure(bundle, action, e),
                            )
                            if bundle.critical:
                                break
            if per_branch_failures:
                failures.extend(per_branch_failures)
                if any(f.bundle.critical for f in per_branch_failures):
                    failed += 1
                    continue

        wt_removed = False
        try:
            remove_worktree(
                source_path,
                worktree_path,
                force=force,
                pass_through_stdout=not ctx.quiet,
            )
            wt_removed = True
        except (WorktreeNotFoundError, WorktreeDirtyError, GitCommandError):
            wt_removed = False

        if not wt_removed:
            failed += 1
            continue

        branch_rc = _delete_branch_silent(
            source_path, branch, force=force, pass_through=not ctx.quiet,
        )
        if branch_rc != 0:
            failed += 1
            continue

        removed += 1

    if failures:
        print_action_failure_summary(failures)

    summary = _format_summary(
        removed=removed,
        kept=len(kept),
        failed=failed,
        timed_out=timed_out,
        dry_run=False,
    )
    print(summary)

    if failed > 0:
        return 1
    return 0