"""Migrate command implementation."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from gww.config.loader import ConfigLoadError, ConfigNotFoundError, load_config
from gww.config.resolver import ResolverError, resolve_source_path
from gww.config.validator import ConfigValidationError, validate_config
from gww.git.repository import (
    GitCommandError,
    get_remote_uri,
    get_source_repository,
    is_submodule,
    is_worktree,
)
from gww.git.worktree import repair_worktrees
from gww.utils.uri import parse_uri


@dataclass
class MigrationPlan:
    """Plan for migrating a single repository."""

    old_path: Path
    new_path: Path
    uri: str
    reason: str = ""


def _find_git_repositories(directory: Path) -> list[Path]:
    """Find all git repositories in a directory tree.

    Args:
        directory: Directory to scan.

    Returns:
        List of paths to git repository roots.
    """
    repos: list[Path] = []

    for root, dirs, files in os.walk(directory):
        root_path = Path(root)

        # Check if this is a git repository (skip submodules - they move with parent)
        if (root_path / ".git").exists() and not is_submodule(root_path):
            repos.append(root_path)
            # Don't descend into the .git directory
            dirs[:] = [d for d in dirs if d != ".git"]

    return repos


def _plan_migration(
    old_repos: Path,
    config: "Config",  # type: ignore[name-defined]
    verbose: int = 0,
) -> tuple[list[MigrationPlan], list[Path]]:
    """Plan migrations for all repositories in a directory.

    Args:
        old_repos: Directory containing old repositories.
        config: Validated configuration.
        verbose: Verbosity level.

    Returns:
        Tuple of (migration plans, paths already at target).
    """
    plans: list[MigrationPlan] = []
    already_at_target: list[Path] = []
    repos = _find_git_repositories(old_repos)

    for repo_path in repos:
        # Get remote URI
        remote_uri = get_remote_uri(repo_path)
        if not remote_uri:
            if verbose > 0:
                print(
                    f"Skipping {repo_path}: No remote origin configured",
                    file=sys.stderr,
                )
            continue

        # Parse URI
        try:
            uri = parse_uri(remote_uri)
        except ValueError as e:
            if verbose > 0:
                print(f"Skipping {repo_path}: Invalid remote URI: {e}", file=sys.stderr)
            continue

        # Resolve expected path
        try:
            expected_path = resolve_source_path(config, uri)
        except ResolverError as e:
            if verbose > 0:
                print(f"Skipping {repo_path}: {e}", file=sys.stderr)
            continue

        # Check if migration needed
        if repo_path.resolve() == expected_path.resolve():
            already_at_target.append(repo_path)
            continue

        # Check if destination exists
        reason = ""
        if expected_path.exists():
            reason = "destination exists - will skip"

        plans.append(
            MigrationPlan(
                old_path=repo_path,
                new_path=expected_path,
                uri=remote_uri,
                reason=reason,
            )
        )

    return plans, already_at_target


def run_migrate(args: argparse.Namespace) -> int:
    """Execute the migrate command.

    Args:
        args: Parsed command line arguments.

    Returns:
        Exit code (0 for success, 1 for error, 2 for config error).
    """
    old_repos_str = args.old_repos
    dry_run = getattr(args, "dry_run", False)
    move = getattr(args, "move", False)
    verbose = getattr(args, "verbose", 0)
    quiet = getattr(args, "quiet", False)

    old_repos = Path(old_repos_str).expanduser().resolve()

    # Verify path exists
    if not old_repos.exists():
        print(f"Error: Path does not exist: {old_repos}", file=sys.stderr)
        return 1

    if not old_repos.is_dir():
        print(f"Error: Not a directory: {old_repos}", file=sys.stderr)
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

    # Plan migrations
    if verbose > 0 and not quiet:
        print(f"Scanning {old_repos} for repositories...", file=sys.stderr)

    plans, already_at_target = _plan_migration(old_repos, config, verbose)

    if not plans and not already_at_target:
        if not quiet:
            print("No repositories to migrate.")
        return 0

    # Filter out plans with existing destinations
    valid_plans = [p for p in plans if not p.reason]
    skipped_plans = [p for p in plans if p.reason]

    # Output "already at target" paths when not quiet
    if already_at_target and not quiet:
        for path in already_at_target:
            print(f"Already at target: {path}")

    if dry_run:
        # Output each path immediately, then summary at the end
        if not quiet:
            for plan in valid_plans:
                print(f"{plan.old_path} -> {plan.new_path}")
            for plan in skipped_plans:
                print(f"{plan.old_path}: {plan.reason}")
        if not quiet:
            print(f"Would migrate {len(valid_plans)} repositories")
            if skipped_plans:
                print(f"Would skip {len(skipped_plans)} repositories")
        return 0

    # Execute migrations
    migrated = 0
    failed = 0
    repaired = 0

    for plan in valid_plans:
        try:
            if not quiet:
                print(f"{plan.old_path} -> {plan.new_path}")
            # Ensure parent directory exists
            plan.new_path.parent.mkdir(parents=True, exist_ok=True)

            # Check if this is a worktree before moving (need source repo path)
            is_wt = is_worktree(plan.old_path)
            source_repo: Optional[Path] = None
            if is_wt:
                try:
                    source_repo = get_source_repository(plan.old_path)
                except Exception:
                    # If we can't get source repo, we'll skip repair
                    pass

            if move:
                if verbose > 0 and not quiet:
                    print(f"Moving {plan.old_path} -> {plan.new_path}", file=sys.stderr)
                shutil.move(str(plan.old_path), str(plan.new_path))
            else:
                if verbose > 0 and not quiet:
                    print(f"Copying {plan.old_path} -> {plan.new_path}", file=sys.stderr)
                shutil.copytree(str(plan.old_path), str(plan.new_path))

            # If this was a worktree, repair the source repository
            if is_wt and source_repo is not None:
                try:
                    if verbose > 0 and not quiet:
                        print(
                            f"Repairing worktree paths in {source_repo}",
                            file=sys.stderr,
                        )
                    repair_worktrees(source_repo)
                    repaired += 1
                except GitCommandError as e:
                    print(
                        f"Warning: Failed to repair worktree paths for {plan.new_path}: {e}",
                        file=sys.stderr,
                    )

            migrated += 1
        except OSError as e:
            print(f"Error migrating {plan.old_path}: {e}", file=sys.stderr)
            failed += 1

    # Summary
    if not quiet:
        action = "Moved" if move else "Migrated"
        print(f"{action} {migrated} repositories")
        if repaired:
            print(f"Repaired {repaired} worktrees")
        if skipped_plans:
            print(f"Skipped {len(skipped_plans)} repositories")
        if already_at_target:
            print(f"Already at target: {len(already_at_target)} repositories")
        if failed:
            print(f"Failed {failed} repositories")

    return 1 if failed > 0 else 0
