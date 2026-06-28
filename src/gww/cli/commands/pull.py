"""Pull command implementation."""

from __future__ import annotations

from pathlib import Path

from gww.cli.context import CommandContext, CommandExit, exit_on_error
from gww.git.branch import is_main_branch
from gww.git.repository import (
    GitCommandError,
    NotGitRepositoryError,
    detect_repository,
    get_current_branch,
    get_source_repository,
    is_clean,
    pull_repository,
)


def _resolve_source_repo(cwd: Path) -> Path:
    """Detect repo at cwd and walk back to its source if needed.

    Unlike :func:`gww.cli.context.resolve_source_repo_or_exit` this helper
    does not require a remote origin — ``pull`` updates the local source
    directly.

    Args:
        cwd: Directory to start the detection from.

    Returns:
        Path to the source repository.

    Raises:
        CommandExit: With code ``1`` if ``cwd`` is not in a git repo or the
            source repo cannot be found.
    """
    try:
        repo = detect_repository(cwd)
    except NotGitRepositoryError as e:
        raise CommandExit(1, "Error: Not in a git repository.") from e

    if repo.is_worktree:
        try:
            return get_source_repository(repo.path)
        except (NotGitRepositoryError, GitCommandError) as e:
            raise CommandExit(1, f"Error finding source repository: {e}") from e
    return repo.path


@exit_on_error
def run_pull(ctx: CommandContext) -> int:
    """Execute the pull command.

    Args:
        ctx: Per-invocation command context.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    cwd = Path.cwd()
    source_path = _resolve_source_repo(cwd)

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
        pull_repository(source_path)
    except GitCommandError as e:
        raise CommandExit(1, f"Error pulling updates: {e}") from e

    ctx.say(f"Updated source repository: {source_path}")

    return 0