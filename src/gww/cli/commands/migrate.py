"""Migrate command implementation."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from gww.config.loader import ConfigLoadError, ConfigNotFoundError, load_config
from gww.config.resolver import ResolverError, resolve_source_path, resolve_worktree_path
from gww.config.validator import Config, ConfigValidationError, validate_config
from gww.git.repository import (
    GitCommandError,
    get_current_branch,
    get_remote_uri,
    get_source_repository,
    is_submodule,
    is_worktree,
)
from gww.git.worktree import repair_worktrees
from gww.utils.uri import parse_uri


@dataclass
class MigrationPlan:
    """Plan for migrating a single repository (source or worktree)."""

    old_path: Path
    new_path: Path
    uri: str
    reason: str = ""
    is_worktree: bool = False
    source_path: Optional[Path] = None  # main repo path (for worktrees only)


def _find_git_repositories(
    directory: Path,
    *,
    progress_callback: Optional[Callable[[Path], None]] = None,
) -> list[Path]:
    """Find all git repositories in a directory tree.

    Args:
        directory: Directory to scan.
        progress_callback: Optional callback invoked with current directory path
            at the start of each os.walk iteration.

    Returns:
        List of paths to git repository roots.
    """
    repos: list[Path] = []

    for root, dirs, files in os.walk(directory):
        root_path = Path(root)
        if progress_callback is not None:
            progress_callback(root_path)

        # Check if this is a git repository (skip submodules - they move with parent)
        if (root_path / ".git").exists() and not is_submodule(root_path):
            repos.append(root_path)
            # Don't descend into the .git directory
            dirs[:] = [d for d in dirs if d != ".git"]

    return repos


def _collect_all_repos(
    input_paths: list[Path],
    *,
    progress_callback: Optional[Callable[[Path], None]] = None,
) -> tuple[list[Path], list[Path]]:
    """Collect and merge repo roots from multiple input directories.

    Args:
        input_paths: List of directories to scan.
        progress_callback: Optional callback invoked with current directory path
            during the scan (passed to _find_git_repositories).

    Returns:
        Tuple of (deduplicated repo paths, input roots for cleanup).
    """
    seen: set[Path] = set()
    repos: list[Path] = []
    for directory in input_paths:
        for repo_path in _find_git_repositories(
            directory, progress_callback=progress_callback
        ):
            resolved = repo_path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                repos.append(repo_path)
    return repos, [p.resolve() for p in input_paths]


def _plan_migration(
    repos: list[Path],
    config: Config,
    verbose: int = 0,
    tags: Optional[dict[str, str]] = None,
) -> tuple[list[MigrationPlan], list[Path]]:
    """Plan migrations for all repositories.

    Classifies each repo as source or worktree; uses resolve_source_path for
    sources and resolve_worktree_path for worktrees (branch from get_current_branch).

    Args:
        repos: List of repository root paths.
        config: Validated configuration.
        verbose: Verbosity level.
        tags: Optional tags for template evaluation.

    Returns:
        Tuple of (migration plans, paths already at target).
    """
    if tags is None:
        tags = {}
    plans: list[MigrationPlan] = []
    already_at_target: list[Path] = []

    for repo_path in repos:
        remote_uri = get_remote_uri(repo_path)
        if not remote_uri:
            if verbose > 0:
                print(
                    f"Skipping {repo_path}: No remote origin configured",
                    file=sys.stderr,
                )
            continue

        try:
            uri_parsed = parse_uri(remote_uri)
        except ValueError as e:
            if verbose > 0:
                print(f"Skipping {repo_path}: Invalid remote URI: {e}", file=sys.stderr)
            continue

        is_wt = is_worktree(repo_path)
        source_path: Optional[Path] = None
        if is_wt:
            try:
                source_path = get_source_repository(repo_path)
            except Exception:
                if verbose > 0:
                    print(f"Skipping {repo_path}: Could not resolve source repository", file=sys.stderr)
                continue
            try:
                branch = get_current_branch(repo_path)
            except GitCommandError:
                if verbose > 0:
                    print(f"Skipping {repo_path}: Detached HEAD (branch required for worktree path)", file=sys.stderr)
                continue
            try:
                expected_path = resolve_worktree_path(config, uri_parsed, branch, tags)
            except ResolverError as e:
                if verbose > 0:
                    print(f"Skipping {repo_path}: {e}", file=sys.stderr)
                continue
        else:
            try:
                expected_path = resolve_source_path(config, uri_parsed, tags)
            except ResolverError as e:
                if verbose > 0:
                    print(f"Skipping {repo_path}: {e}", file=sys.stderr)
                continue

        if repo_path.resolve() == expected_path.resolve():
            already_at_target.append(repo_path)
            continue

        reason = ""
        if expected_path.exists():
            reason = "destination exists - will skip"

        plans.append(
            MigrationPlan(
                old_path=repo_path,
                new_path=expected_path,
                uri=remote_uri,
                reason=reason,
                is_worktree=is_wt,
                source_path=source_path,
            )
        )

    return plans, already_at_target


def _run_inplace(
    valid_plans: list[MigrationPlan],
    already_at_target: list[Path],
    input_roots: list[Path],
    dry_run: bool,
    quiet: bool,
    verbose: int,
) -> int:
    """Execute inplace migration (move worktrees then sources, then clean empty dirs)."""
    # Output "already at target" when not quiet
    if already_at_target and not quiet:
        for path in already_at_target:
            print(f"Already at target: {path}")

    worktree_plans = [p for p in valid_plans if p.is_worktree]
    source_plans = [p for p in valid_plans if not p.is_worktree]

    # First pass: worktrees
    for plan in worktree_plans:
        if dry_run:
            if not quiet:
                print(plan.new_path)
            continue
        if not quiet:
            print(plan.new_path)
        plan.new_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(plan.old_path), str(plan.new_path))
        if plan.source_path is not None:
            try:
                if verbose > 0 and not quiet:
                    print(f"Repairing worktree paths in {plan.source_path}", file=sys.stderr)
                repair_worktrees(plan.source_path)
            except GitCommandError as e:
                print(
                    f"Warning: Failed to repair worktree paths for {plan.new_path}: {e}",
                    file=sys.stderr,
                )

    # Second pass: sources (only repair if this source had worktrees we moved)
    source_paths_with_worktrees = {p.source_path.resolve() for p in worktree_plans if p.source_path is not None}
    for plan in source_plans:
        if dry_run:
            if not quiet:
                print(plan.new_path)
            continue
        if not quiet:
            print(plan.new_path)
        plan.new_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(plan.old_path), str(plan.new_path))
        if plan.old_path.resolve() in source_paths_with_worktrees:
            try:
                if verbose > 0 and not quiet:
                    print(f"Repairing worktree paths in {plan.new_path}", file=sys.stderr)
                repair_worktrees(plan.new_path)
            except GitCommandError as e:
                print(
                    f"Warning: Failed to repair worktree paths for {plan.new_path}: {e}",
                    file=sys.stderr,
                )

    # Clean empty source folders (inplace only, recursive)
    if not dry_run and valid_plans:
        vacated = [p.old_path.resolve() for p in valid_plans]
        roots_set = set(input_roots)
        # Process deepest paths first so parents can be removed after children
        vacated_sorted = sorted(vacated, key=lambda p: len(p.parts), reverse=True)
        for start_path in vacated_sorted:
            current = start_path
            while True:
                if current in roots_set or not current.exists():
                    break
                if not current.is_dir():
                    break
                try:
                    if any(current.iterdir()):
                        break
                    current.rmdir()
                    current = current.parent
                except OSError:
                    break

    if not quiet:
        if valid_plans:
            moved = len(worktree_plans) + len(source_plans)
            print(f"Moved {moved} repositories")
        if already_at_target:
            print(f"Already at target: {len(already_at_target)} repositories")
    return 0


def _run_copy(
    valid_plans: list[MigrationPlan],
    skipped_plans: list[MigrationPlan],
    already_at_target: list[Path],
    dry_run: bool,
    quiet: bool,
    verbose: int,
    tags: dict[str, str],
) -> int:
    """Execute copy migration (list, validate, copy sources then worktrees, repair, summary)."""
    # Output "already at target" when not quiet
    if already_at_target and not quiet:
        for path in already_at_target:
            print(f"Already at target: {path}")

    if not valid_plans:
        if skipped_plans and not quiet:
            for plan in skipped_plans:
                print(f"{plan.old_path}: {plan.reason}")
        if not quiet:
            if already_at_target:
                print(f"Already at target: {len(already_at_target)} repositories")
            else:
                print("No repositories to migrate.")
        return 0

    # List and output each found source and worktree
    if not quiet:
        for plan in valid_plans:
            kind = "Worktree" if plan.is_worktree else "Source"
            print(f"{kind}: {plan.old_path} -> {plan.new_path}")
        for plan in skipped_plans:
            print(f"{plan.old_path}: {plan.reason}")

    if dry_run:
        if not quiet:
            print(f"Would migrate {len(valid_plans)} repositories")
            if skipped_plans:
                print(f"Would skip {len(skipped_plans)} repositories")
        return 0

    # Migrate sources first, then worktrees
    source_plans = [p for p in valid_plans if not p.is_worktree]
    worktree_plans = [p for p in valid_plans if p.is_worktree]
    migrated_sources = 0
    migrated_worktrees = 0
    failed = 0

    for plan in source_plans:
        try:
            if not quiet:
                print(f"Copying repository {plan.old_path} -> {plan.new_path}")
            plan.new_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(str(plan.old_path), str(plan.new_path))
            migrated_sources += 1
        except OSError as e:
            print(f"Error migrating {plan.old_path}: {e}", file=sys.stderr)
            failed += 1

    for plan in worktree_plans:
        try:
            if not quiet:
                print(f"Copying worktree {plan.old_path} -> {plan.new_path}")
            plan.new_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(str(plan.old_path), str(plan.new_path))
            migrated_worktrees += 1
            # Recover relation: point copied worktree's .git to new source (if any) and repair
            if plan.source_path is not None:
                # Resolve new source path (source may have been copied in this run)
                new_source = None
                for sp in source_plans:
                    if sp.old_path.resolve() == plan.source_path.resolve():
                        new_source = sp.new_path
                        break
                if new_source is not None:
                    _fix_copied_worktree_gitfile(plan.new_path, plan.old_path, new_source)
                    try:
                        if verbose > 0 and not quiet:
                            print(f"Repairing worktree paths in {new_source}", file=sys.stderr)
                        repair_worktrees(new_source)
                    except GitCommandError as e:
                        print(
                            f"Warning: Failed to repair worktree paths for {plan.new_path}: {e}",
                            file=sys.stderr,
                        )
                else:
                    # Source was not in migration; repair old source with new worktree path
                    try:
                        if verbose > 0 and not quiet:
                            print(f"Repairing worktree paths in {plan.source_path}", file=sys.stderr)
                        repair_worktrees(plan.source_path, [plan.new_path])
                    except GitCommandError as e:
                        print(
                            f"Warning: Failed to repair worktree paths for {plan.new_path}: {e}",
                            file=sys.stderr,
                        )
        except OSError as e:
            print(f"Error migrating {plan.old_path}: {e}", file=sys.stderr)
            failed += 1

    if not quiet:
        print(f"Migrated {migrated_sources} repositories, {migrated_worktrees} worktrees")
        if skipped_plans:
            print(f"Skipped {len(skipped_plans)} repositories")
        if already_at_target:
            print(f"Already at target: {len(already_at_target)} repositories")
        if failed:
            print(f"Failed {failed} repositories")
    return 1 if failed > 0 else 0


def _fix_copied_worktree_gitfile(
    new_worktree_path: Path,
    old_worktree_path: Path,
    new_source_path: Path,
) -> None:
    """Update copied worktree's .git file to point to new source's worktrees dir."""
    git_file = new_worktree_path / ".git"
    if not git_file.is_file():
        return
    content = git_file.read_text().strip()
    if not content.startswith("gitdir:"):
        return
    old_gitdir = content.split(":", 1)[1].strip()
    # Old content points to old_source/.git/worktrees/<id>; extract worktree id
    parts = Path(old_gitdir.replace("\\", "/")).parts
    try:
        idx = parts.index("worktrees")
        if idx + 1 < len(parts):
            wt_id = parts[idx + 1]
            new_gitdir = str(new_source_path / ".git" / "worktrees" / wt_id)
            git_file.write_text(f"gitdir: {new_gitdir}\n")
    except (ValueError, IndexError):
        pass


def run_migrate(args: argparse.Namespace) -> int:
    """Execute the migrate command.

    Args:
        args: Parsed command line arguments.

    Returns:
        Exit code (0 for success, 1 for error, 2 for config error).
    """
    old_repos_raw = args.old_repos
    old_repos_list: list[str] = (
        old_repos_raw if isinstance(old_repos_raw, list) else [old_repos_raw]
    )
    dry_run = getattr(args, "dry_run", False)
    inplace = getattr(args, "inplace", False)
    verbose = getattr(args, "verbose", 0)
    quiet = getattr(args, "quiet", False)
    tags = getattr(args, "tags", {}) or {}

    input_paths = [Path(p).expanduser().resolve() for p in old_repos_list]

    for p in input_paths:
        if not p.exists():
            print(f"Error: Path does not exist: {p}", file=sys.stderr)
            return 1
        if not p.is_dir():
            print(f"Error: Not a directory: {p}", file=sys.stderr)
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

    progress_callback: Optional[Callable[[Path], None]] = None
    if not quiet:
        last_progress_time: list[float] = [0.0]

        def _progress_cb(path: Path) -> None:
            now = time.time()
            if now - last_progress_time[0] >= 1.0:
                print(f"\rExamining: {path}   ", end="", file=sys.stderr, flush=True)
                last_progress_time[0] = now

        progress_callback = _progress_cb

    repos, input_roots = _collect_all_repos(
        input_paths, progress_callback=progress_callback
    )
    if not quiet:
        print("\n", file=sys.stderr, end="")
    if verbose > 0 and not quiet:
        print(f"Scanning {len(input_paths)} path(s) for repositories...", file=sys.stderr)

    plans, already_at_target = _plan_migration(repos, config, verbose, tags)

    valid_plans = [p for p in plans if not p.reason]
    skipped_plans = [p for p in plans if p.reason]

    if not plans and not already_at_target:
        if not quiet:
            print("No repositories to migrate.")
        return 0

    if inplace:
        return _run_inplace(
            valid_plans, already_at_target, input_roots, dry_run, quiet, verbose
        )
    return _run_copy(
        valid_plans, skipped_plans, already_at_target, dry_run, quiet, verbose, tags
    )
