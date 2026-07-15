"""``gww clean`` orchestrator: wiring plan -> selection -> removal.

Holds :func:`run_clean` (the public entry point) and the clean-specific
``_delete_branch_silent`` helper. Cleanability, enumeration, and formatting
live in :mod:`.provider`, :mod:`.plan`, and :mod:`.report`; the per-worktree
removal itself is the shared :func:`gww.actions.removal.remove_one_worktree`
primitive.
"""

from __future__ import annotations

import sys
from pathlib import Path

from gww.actions import MatcherError
from gww.actions.removal import RuleFailure, remove_one_worktree
from gww.cli.commands.clean.plan import (
    _main_checkout_path,
    build_candidate_plan,
)
from gww.cli.commands.clean.provider import (
    _git_merged_branch_set,
    select_cleanable,
)
from gww.cli.commands.clean.report import _format_summary, _prompt_confirmation
from gww.cli.context import (
    CommandContext,
    CommandExit,
    exit_on_error,
    load_config_or_exit,
    parse_uri_or_exit,
    print_action_failure_summary,
    resolve_source_repo,
)
from gww.config.resolver import find_matching_provider
from gww.config.validator import ProviderConfig
from gww.git.branch import (
    BranchNotFoundError,
    delete_branch,
    local_branch_exists,
)
from gww.git.repository import (
    GitCommandError,
    get_remote_uri,
    run_git,
)
from gww.template.functions import TemplateContext
from gww.utils.uri import ParsedURI


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
        return run_git(
            ["branch", flag, branch],
            source_path,
            check=False,
            pass_through_stdout=True,
        ).returncode
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

    plan = build_candidate_plan(source_path, main_path)

    config = load_config_or_exit()

    origin_uri: str | None = get_remote_uri(source_path)

    parsed_uri: ParsedURI | None = None
    if origin_uri:
        try:
            parsed_uri = parse_uri_or_exit(origin_uri)
        except CommandExit:
            parsed_uri = None
            if use_merged:
                print(
                    f"warning: could not parse origin URI '{origin_uri}'; "
                    "provider matching disabled, falling back to git merge status",
                    file=sys.stderr,
                )

    provider: ProviderConfig | None = None
    if use_merged and parsed_uri is not None:
        provider = find_matching_provider(config, parsed_uri, ctx.tags)
        if provider is None and config.providers:
            print(
                f"warning: origin host '{parsed_uri.host}' matched no configured "
                "provider; falling back to git merge status",
                file=sys.stderr,
            )

    if not plan.branches:
        label = "--merged" if use_merged else "--all"
        print(f"Filter: {label}. No matching worktrees.")
        return 0

    git_merged_set: set[str] | None = None
    if use_merged and provider is None:
        git_merged_set = _git_merged_branch_set(source_path, plan.default_branch)

    provider_label: str | None = provider.name if provider is not None else None

    selection = select_cleanable(
        plan.branches,
        use_all=use_all,
        provider=provider,
        parsed_uri=parsed_uri,
        tags=ctx.tags,
        git_merged_set=git_merged_set,
    )

    if not selection.cleanable:
        summary = _format_summary(
            removed=0,
            kept=len(selection.kept),
            failed=0,
            timed_out=selection.timed_out,
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
            removed=len(selection.cleanable),
            kept=len(selection.kept),
            failed=0,
            timed_out=selection.timed_out,
            dry_run=True,
        )
        print(summary)
        return 0

    failures: list[RuleFailure] = []
    removed = 0
    failed = 0

    for branch in selection.cleanable:
        worktree_path = plan.worktree_by_branch.get(branch)
        if worktree_path is None:
            failed += 1
            continue

        context = TemplateContext(
            uri=parsed_uri,
            branch=branch,
            source_path=source_path,
            dest_path=worktree_path,
            tags=ctx.tags,
        )
        try:
            outcome = remove_one_worktree(
                source_path,
                worktree_path,
                actions=config.actions,
                context=context,
                force=force,
                quiet=ctx.quiet,
            )
        except MatcherError as e:
            raise CommandExit(2, f"Config error: {e}") from e

        failures.extend(outcome.failures)

        if not outcome.removed:
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
        kept=len(selection.kept),
        failed=failed,
        timed_out=selection.timed_out,
        dry_run=False,
    )
    print(summary)

    if failed > 0:
        return 1
    return 0
