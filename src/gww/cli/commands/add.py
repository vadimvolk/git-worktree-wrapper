"""Add worktree command implementation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from gww.actions.executor import ActionError, execute_actions
from gww.actions.matcher import MatcherError, get_worktree_actions
from gww.config.loader import ConfigLoadError, ConfigNotFoundError, load_config
from gww.config.resolver import ResolverError, resolve_worktree_path
from gww.config.validator import ConfigValidationError, validate_config
from gww.git.branch import (
    BranchExistsError,
    branch_exists,
    create_branch,
    local_branch_exists,
)
from gww.git.repository import (
    GitCommandError,
    NotGitRepositoryError,
    detect_repository,
    get_current_commit,
    get_remote_uri,
    get_source_repository,
)
from gww.git.worktree import WorktreeExistsError, add_worktree
from gww.utils.uri import parse_uri


def run_add(args: argparse.Namespace) -> int:
    """Execute the add worktree command.

    Args:
        args: Parsed command line arguments.

    Returns:
        Exit code (0 for success, 1 for error, 2 for config error).
    """
    branch = args.branch
    create_branch_flag = getattr(args, "create_branch", False)
    verbose = getattr(args, "verbose", 0)
    quiet = getattr(args, "quiet", False)
    tags = getattr(args, "tags", {})

    # Get current directory
    cwd = Path.cwd()

    # Detect current repository
    try:
        repo = detect_repository(cwd)
    except NotGitRepositoryError:
        print("Error: Not in a git repository.", file=sys.stderr)
        return 1

    # If in worktree, get source repository
    if repo.is_worktree:
        try:
            source_path = get_source_repository(repo.path)
        except (NotGitRepositoryError, GitCommandError) as e:
            print(f"Error finding source repository: {e}", file=sys.stderr)
            return 1
    else:
        source_path = repo.path

    # Get remote URI for path resolution
    remote_uri = get_remote_uri(source_path)
    if not remote_uri:
        print(
            "Error: Repository has no remote origin. Cannot determine worktree path.",
            file=sys.stderr,
        )
        return 1

    # Parse URI
    try:
        uri = parse_uri(remote_uri)
    except ValueError as e:
        print(f"Error parsing remote URI: {e}", file=sys.stderr)
        return 1

    # Load and validate config
    try:
        raw_config = load_config()
        config = validate_config(raw_config)
    except ConfigNotFoundError:
        print(
            "Error: Config file not found. Run 'gww init config' to create one.",
            file=sys.stderr,
        )
        return 2
    except ConfigLoadError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except ConfigValidationError as e:
        print(f"Config validation error: {e}", file=sys.stderr)
        return 2

    # Check if branch exists
    if not branch_exists(source_path, branch):
        if create_branch_flag:
            # Create branch from current commit (of the directory where command was run)
            try:
                current_commit = get_current_commit(cwd)
                create_branch(source_path, branch, current_commit)
                if verbose > 0 and not quiet:
                    print(
                        f"Created branch '{branch}' from {current_commit[:8]}",
                        file=sys.stderr,
                    )
            except (GitCommandError, BranchExistsError) as e:
                print(f"Error creating branch: {e}", file=sys.stderr)
                return 1
        else:
            print(
                f"Error: Branch '{branch}' not found. "
                "Use --create-branch to create from current commit.",
                file=sys.stderr,
            )
            return 1

    # Resolve worktree path
    try:
        worktree_path = resolve_worktree_path(config, uri, branch, tags)
    except ResolverError as e:
        print(f"Error resolving worktree path: {e}", file=sys.stderr)
        return 2

    if verbose > 0 and not quiet:
        print(f"Adding worktree for '{branch}' at {worktree_path}...", file=sys.stderr)

    # Add worktree
    try:
        add_worktree(source_path, worktree_path, branch)
    except WorktreeExistsError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except GitCommandError as e:
        print(f"Error adding worktree: {e}", file=sys.stderr)
        return 1

    # Execute worktree actions if any project rules match
    if config.projects:
        try:
            actions = get_worktree_actions(config.projects, source_path, tags, dest_path=worktree_path)
            if actions:
                if verbose > 0 and not quiet:
                    print(
                        f"Executing {len(actions)} worktree action(s)...",
                        file=sys.stderr,
                    )
                execute_actions(actions, source_path, worktree_path)
        except MatcherError as e:
            print(f"Error matching project rules: {e}", file=sys.stderr)
            # Continue - worktree added, just actions failed
        except ActionError as e:
            print(f"Error executing worktree action: {e}", file=sys.stderr)
            # Continue - worktree added, just actions failed

    # Output worktree path
    if not quiet:
        print(worktree_path)

    return 0
