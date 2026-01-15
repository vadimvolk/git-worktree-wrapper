"""Remove worktree command implementation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

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
    find_worktree_by_path,
    remove_worktree,
)


def run_remove(args: argparse.Namespace) -> int:
    """Execute the remove worktree command.

    Args:
        args: Parsed command line arguments.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    branch_or_path = args.branch_or_path
    force = getattr(args, "force", False)
    verbose = getattr(args, "verbose", 0)
    quiet = getattr(args, "quiet", False)

    # Determine if argument is a path or branch name
    is_path = "/" in branch_or_path and Path(branch_or_path).is_absolute()

    if is_path:
        worktree_path = Path(branch_or_path).resolve()

        # Verify it's a valid worktree
        try:
            repo = detect_repository(worktree_path)
        except NotGitRepositoryError:
            print(f"Error: Not a git repository: {worktree_path}", file=sys.stderr)
            return 1

        if not repo.is_worktree:
            print(f"Error: Not a worktree: {worktree_path}", file=sys.stderr)
            return 1

        # Get source repository
        try:
            source_path = get_source_repository(worktree_path)
        except (NotGitRepositoryError, GitCommandError) as e:
            print(f"Error finding source repository: {e}", file=sys.stderr)
            return 1
    else:
        # branch_or_path is a branch name
        branch = branch_or_path
        cwd = Path.cwd()

        # Detect current repository
        try:
            repo = detect_repository(cwd)
        except NotGitRepositoryError:
            print("Error: Not in a git repository.", file=sys.stderr)
            return 1

        # Get source repository
        if repo.is_worktree:
            try:
                source_path = get_source_repository(repo.path)
            except (NotGitRepositoryError, GitCommandError) as e:
                print(f"Error finding source repository: {e}", file=sys.stderr)
                return 1
        else:
            source_path = repo.path

        # Find worktree by branch
        wt = find_worktree_by_branch(source_path, branch)
        if not wt:
            print(f"Error: No worktree found for branch '{branch}'", file=sys.stderr)
            return 1

        worktree_path = wt.path

    if verbose > 0 and not quiet:
        if force:
            print(f"Force removing worktree: {worktree_path}...", file=sys.stderr)
        else:
            print(f"Removing worktree: {worktree_path}...", file=sys.stderr)

    # Remove worktree
    try:
        remove_worktree(source_path, worktree_path, force=force)
    except WorktreeNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except WorktreeDirtyError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except GitCommandError as e:
        print(f"Error removing worktree: {e}", file=sys.stderr)
        return 1

    # Output confirmation
    if not quiet:
        print(f"Removed worktree: {worktree_path}")

    return 0
