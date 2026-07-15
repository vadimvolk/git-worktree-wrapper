"""Cleanability primitives for ``gww clean``: is this branch removable?

These helpers answer the per-branch "should we clean it?" question for the
``--merged`` filter -- rendering and running the user's provider command
(ADR-0017/0018), or falling back to ``git branch --merged`` when no provider
resolves (ADR-0015). :func:`select_cleanable` drives them per candidate branch
and returns the :class:`Selection` the orchestrator acts on.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from gww.cli.context import CommandExit
from gww.config.validator import ProviderConfig
from gww.git.repository import GitCommandError, run_git
from gww.template.evaluator import TemplateError, evaluate_template
from gww.template.functions import TemplateContext
from gww.utils.uri import ParsedURI


PROVIDER_TIMEOUT_SECONDS = 60


def _run_provider_command(rendered: str) -> int:
    """Run a rendered provider command and return its exit code.

    Both stdout and stderr are inherited from the parent so the user sees
    the provider's output live (ADR-0018 §"Stream handling"). No parsing
    happens here -- the caller treats any non-zero exit as "do not remove".

    The shell binary itself is always present (it is the Python executable
    that calls into bash via ``executable=``), so ``FileNotFoundError``
    cannot be raised for a missing leading command under ``shell=True``.
    The shell exits with ``127`` for "command not found"; the caller
    distinguishes that case from other non-zero exits so the per-branch
    ``X: skip (<command> not found)`` label fires correctly.

    The invocation goes through ``/bin/bash`` (not the platform's
    ``/bin/sh``) because ``set -o pipefail`` is required for composed
    pipelines (e.g. ``tea pulls list … | jq -e …``) to propagate an
    upstream provider failure, and ``/bin/sh`` on Linux runners is
    ``dash`` which rejects the option with exit 2 -- masking every real
    command exit code and breaking the caller. Bash 3.0+ (including
    macOS's ``bash 3.2.57``) supports ``pipefail`` directly.

    Args:
        rendered: Shell command to execute.

    Returns:
        The command's exit code.

    Raises:
        subprocess.TimeoutExpired: If the command exceeds the 60s timeout.
        FileNotFoundError: If ``/bin/bash`` is unavailable on the host.
    """
    return subprocess.run(
        f"set -o pipefail; {rendered}",
        executable="/bin/bash",
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
    parts = rendered.split()
    return parts[0] if parts else ""


def _provider_template_for_branch(
    provider: ProviderConfig,
    branch: str,
    uri: ParsedURI | None,
    tags: dict[str, str],
) -> str:
    """Render the provider's ``filter`` template against ``branch``.

    Builds a :class:`TemplateContext` populated with branch, tags, and (when
    available) the source's origin URI so predicates in the command
    template can reference ``branch()`` / ``host()`` / ``tag()`` etc. The URI
    is parsed once by the caller; a malformed remote URI is passed as
    ``None`` (treated as "no URI context") rather than failing here.

    Args:
        provider: User-declared :class:`ProviderConfig` whose ``filter``
            template to render.
        branch: Worktree branch to substitute into the template.
        uri: Parsed source origin URI, or ``None`` if unset/malformed.
        tags: Tag key-value pairs from CLI ``--tag`` options.

    Returns:
        Rendered shell command string.

    Raises:
        CommandExit: With code 2 if the template fails to evaluate
            (treated as a config error).
    """
    context = TemplateContext(
        branch=branch,
        tags=tags,
    )
    if uri is not None:
        context.uri = uri

    try:
        return evaluate_template(provider.filter, context)
    except TemplateError as e:
        raise CommandExit(2, f"Config error: provider filter template: {e}") from e


def _git_merged_branch_set(source_path: Path, default_branch: str) -> set[str]:
    """Return the set of local branches fully merged into ``default_branch``.

    Implements the ``--merged`` git fallback (ADR-0015) by routing
    ``git branch --merged <default_branch> --format=%(refname:short)``
    through :func:`gww.git.repository.run_git` (ADR-0020). ``--format``
    is documented in git since 2.10 and is used by the existing
    :func:`list_local_branches` so we know it works in our supported git
    versions.

    Args:
        source_path: Path to the source repository.
        default_branch: Branch to test merge-against (``main`` /
            ``master``).

    Returns:
        Set of local branch names fully merged into ``default_branch``.
        Returns an empty set on git failure (non-zero exit, or a missing
        git binary surfacing as :class:`GitCommandError`) so the caller
        treats everything as "not merged" rather than crashing.
    """
    try:
        proc = run_git(
            ["branch", "--merged", default_branch,
             "--format=%(refname:short)"],
            cwd=source_path,
            check=False,
        )
    except GitCommandError:
        return set()
    if proc.returncode != 0:
        return set()
    merged: set[str] = set()
    for line in proc.stdout.splitlines():
        name = line.strip()
        if name and name != default_branch:
            merged.add(name)
    return merged


@dataclass(frozen=True)
class Selection:
    """Outcome of the per-branch cleanability check.

    Attributes:
        cleanable: Branches that should be removed.
        kept: Branches left in place.
        timed_out: Count of branches skipped due to provider-command timeout.
    """

    cleanable: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    timed_out: int = 0


def select_cleanable(
    branches: list[str],
    *,
    use_all: bool,
    provider: ProviderConfig | None,
    parsed_uri: ParsedURI | None,
    tags: dict[str, str],
    git_merged_set: set[str] | None,
) -> Selection:
    """Decide, per branch, whether it is cleanable.

    Prints the per-branch progress/label lines exactly as the original loop
    did ("checking <branch>", "<branch>: <label>", skip messages). These
    prints are part of the locked output contract -- preserve them verbatim,
    including the ``sys.stdout.flush()`` after "checking".

    Args:
        branches: Candidate branch names in worktree iteration order.
        use_all: ``--all`` filter -- every candidate is cleanable.
        provider: Resolved provider, or ``None`` for the git fallback.
        parsed_uri: Parsed source origin URI for template context.
        tags: Tag key-value pairs from CLI ``--tag`` options.
        git_merged_set: Local branches merged into the default branch, used
            by the git fallback; ``None`` when a provider resolved.

    Returns:
        A :class:`Selection` with the cleanable/kept branches and timeout count.

    Raises:
        CommandExit: propagated from :func:`_provider_template_for_branch` on a
            provider template error (code 2), after printing the per-branch
            stderr line.
    """
    cleanable: list[str] = []
    kept: list[str] = []
    timed_out = 0

    for branch in branches:
        print(f"checking {branch}")
        sys.stdout.flush()

        is_cleanable: bool
        if use_all:
            is_cleanable = True
            label = "clean"
        elif provider is not None:
            try:
                rendered = _provider_template_for_branch(
                    provider, branch, parsed_uri, tags,
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

    return Selection(cleanable=cleanable, kept=kept, timed_out=timed_out)
