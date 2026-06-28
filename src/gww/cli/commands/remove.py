"""Remove worktree command implementation."""

from __future__ import annotations

from pathlib import Path

from gww.cli.context import (
    CommandContext,
    CommandExit,
    exit_on_error,
    resolve_source_repo,
)
from gww.git.repository import (
    GitCommandError,
    NotGitRepositoryError,
    detect_repository,
    get_source_repository,
)
from gww.git.worktree import (
    WorktreeDirtyError,
    WorktreeNotFoundError,
    find_worktree_by_branch,
    remove_worktree,
)


@exit_on_error
def run_remove(ctx: CommandContext) -> int:
    """Execute the remove worktree command.

    Args:
        ctx: Per-invocation command context.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    if ctx.branch_or_path is None:
        raise CommandExit(1, "Error: Missing branch or path.")

    branch_or_path = ctx.branch_or_path
    is_path = "/" in branch_or_path and Path(branch_or_path).is_absolute()

    if is_path:
        worktree_path = Path(branch_or_path).resolve()

        try:
            repo = detect_repository(worktree_path)
        except NotGitRepositoryError as e:
            raise CommandExit(1, f"Error: Not a git repository: {worktree_path}") from e

        if not repo.is_worktree:
            raise CommandExit(1, f"Error: Not a worktree: {worktree_path}")

        try:
            source_path = get_source_repository(worktree_path)
        except (NotGitRepositoryError, GitCommandError) as e:
            raise CommandExit(1, f"Error finding source repository: {e}") from e
    else:
        branch = branch_or_path
        source_path = resolve_source_repo(Path.cwd())

        wt = find_worktree_by_branch(source_path, branch)
        if not wt:
            raise CommandExit(1, f"Error: No worktree found for branch '{branch}'")
        worktree_path = wt.path

    if ctx.verbose > 0:
        if ctx.force:
            ctx.verbose_msg(f"Force removing worktree: {worktree_path}...")
        else:
            ctx.verbose_msg(f"Removing worktree: {worktree_path}...")

    try:
        remove_worktree(source_path, worktree_path, force=ctx.force)
    except (WorktreeNotFoundError, WorktreeDirtyError, GitCommandError) as e:
        raise CommandExit(1, f"Error: {e}") from e

    ctx.say(f"Removed worktree: {worktree_path}")

    return 0