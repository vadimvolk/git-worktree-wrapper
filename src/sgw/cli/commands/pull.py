"""Pull command implementation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sgw.git.branch import is_main_branch
from sgw.git.repository import (
    GitCommandError,
    NotGitRepositoryError,
    detect_repository,
    get_current_branch,
    get_source_repository,
    is_clean,
    pull_repository,
)


def run_pull(args: argparse.Namespace) -> int:
    """Execute the pull command.

    Args:
        args: Parsed command line arguments.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    verbose = getattr(args, "verbose", 0)
    quiet = getattr(args, "quiet", False)

    # Get current directory
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

    # Check current branch
    try:
        current_branch = get_current_branch(source_path)
    except GitCommandError as e:
        print(f"Error getting current branch: {e}", file=sys.stderr)
        return 1

    if not is_main_branch(current_branch):
        print(
            f"Error: Source repository must be on 'main' or 'master' branch. "
            f"Current branch: {current_branch}",
            file=sys.stderr,
        )
        return 1

    # Check if clean
    if not is_clean(source_path):
        print(
            "Error: Source repository has uncommitted changes. "
            "Commit or stash changes first.",
            file=sys.stderr,
        )
        return 1

    if verbose > 0 and not quiet:
        print(f"Pulling updates for {source_path}...", file=sys.stderr)

    # Pull
    try:
        pull_repository(source_path)
    except GitCommandError as e:
        print(f"Error pulling updates: {e}", file=sys.stderr)
        return 1

    # Output confirmation
    if not quiet:
        print(f"Updated source repository: {source_path}")

    return 0
