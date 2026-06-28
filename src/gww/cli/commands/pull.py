"""Pull command implementation."""

from __future__ import annotations

from pathlib import Path

from gww.cli.context import (
    CommandContext,
    CommandExit,
    exit_on_error,
    resolve_source_repo,
)
from gww.git.branch import is_main_branch
from gww.git.repository import (
    GitCommandError,
    get_current_branch,
    is_clean,
    pull_repository,
)


@exit_on_error
def run_pull(ctx: CommandContext) -> int:
    """Execute the pull command.

    Args:
        ctx: Per-invocation command context.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    source_path = resolve_source_repo(Path.cwd())

    try:
        current_branch = get_current_branch(source_path)
    except GitCommandError as e:
        raise CommandExit(1, f"Error getting current branch: {e}") from e

    if not is_main_branch(current_branch):
        raise CommandExit(
            1,
            f"Error: Source repository must be on 'main' or 'master' branch. "
            f"Current branch: {current_branch}",
        )

    if not is_clean(source_path):
        raise CommandExit(
            1,
            "Error: Source repository has uncommitted changes. "
            "Commit or stash changes first.",
        )

    ctx.verbose_msg(f"Pulling updates for {source_path}...")

    try:
        pull_repository(source_path, pass_through_stdout=not ctx.quiet)
    except GitCommandError as e:
        raise CommandExit(1, f"Error pulling updates: {e}") from e

    ctx.say(f"Updated source repository: {source_path}")

    return 0