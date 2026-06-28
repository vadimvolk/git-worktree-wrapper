"""Plan repository migrations.

The planner is a pure function over the validated ``Config`` plus the list
of repository roots found by the directory scan. It returns a
:class:`MigrationResult` tagged union so callers can pattern-match on the
shape of the answer without having to thread an ``is_fatal`` flag through a
4-tuple of skips.

Two outcomes:

* :class:`Migration` — at least one plan succeeded and there are no
  destination-exists blockers. Carries the planned moves and the
  informational skips so the executor can report them.
* :class:`Blocked` — at least one destination already exists in copy mode.
  Callers should bail with exit code 1 before invoking the executor.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

from gww.config.resolver import ResolverError, resolve_source_path, resolve_worktree_path
from gww.config.validator import Config
from gww.git.repository import (
    GitCommandError,
    get_current_branch,
    get_remote_uri,
    get_source_repository,
    is_submodule,
    is_worktree,
)
from gww.utils.uri import parse_uri


@dataclass
class MigrationPlan:
    """One repository to migrate.

    Attributes:
        old_path: Current location of the repository.
        new_path: Configured target location.
        uri: Remote URI of the repository.
        is_worktree: Whether this plan is for a worktree (vs a source).
        source_path: For worktrees, the path to the source repo. ``None`` for
            source repos themselves.
    """

    old_path: Path
    new_path: Path
    uri: str
    is_worktree: bool = False
    source_path: Optional[Path] = None


@dataclass
class Skip:
    """A repository the planner could not produce a migration for.

    Attributes:
        reason: Human-readable explanation (e.g. ``"no remote origin configured"``).
        path: Repository the skip applies to.
        is_worktree: Whether the skipped repo was a worktree.
    """

    reason: str
    path: Path
    is_worktree: bool


@dataclass
class Migration:
    """Planner found at least one plan and no destination-exists blockers."""

    plans: list[MigrationPlan] = field(default_factory=list)
    already_at_target: list[Path] = field(default_factory=list)
    info_skips: list[Skip] = field(default_factory=list)


@dataclass
class Blocked:
    """At least one destination already exists; migration cannot proceed."""

    destinations: list[Path]


MigrationResult = Union[Migration, Blocked]


def find_git_repositories(directory: Path) -> list[Path]:
    """Find all git repositories and worktrees in a directory tree.

    Repository and worktree interiors are not traversed; each repo or
    worktree is treated as a single unit (no descent into subdirectories).

    Args:
        directory: Directory to scan.

    Returns:
        List of paths to git repository roots.
    """
    repos: list[Path] = []

    for root, dirs, _ in os.walk(directory):
        root_path = Path(root)

        # Check if this is a git repository or worktree (skip submodules - they move with parent)
        if (root_path / ".git").exists() and not is_submodule(root_path):
            repos.append(root_path)
            # Do not descend into the repository or worktree (treat as single unit)
            dirs.clear()

    return repos


def collect_repositories(input_paths: list[Path]) -> tuple[list[Path], list[Path]]:
    """Collect and merge repo roots from multiple input directories.

    Args:
        input_paths: List of directories to scan.

    Returns:
        Tuple of (deduplicated repo paths, input roots for cleanup).
    """
    seen: set[Path] = set()
    repos: list[Path] = []
    for directory in input_paths:
        for repo_path in find_git_repositories(directory):
            resolved = repo_path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                repos.append(repo_path)
    return repos, [p.resolve() for p in input_paths]


def plan_migration(
    repos: list[Path],
    config: Config,
    inplace: bool,
    verbose: int = 0,
    tags: Optional[dict[str, str]] = None,
) -> MigrationResult:
    """Plan migrations for all repositories.

    Args:
        repos: List of repository root paths.
        config: Validated configuration.
        inplace: Migration mode flag. When ``False`` (copy mode) a
            destination-exists conflict is fatal and produces a
            :class:`Blocked` result. When ``True`` (inplace) those conflicts
            are recorded as informational :class:`Skip` entries instead.
        verbose: Verbosity level.
        tags: Optional tags for template evaluation.

    Returns:
        Either a :class:`Migration` with the planned moves and informational
        skips, or a :class:`Blocked` listing the conflicting destinations.
    """
    if tags is None:
        tags = {}

    migration = Migration()
    blocked = Blocked(destinations=[])

    for repo_path in repos:
        remote_uri = get_remote_uri(repo_path)
        if not remote_uri:
            migration.info_skips.append(
                Skip(reason="no remote origin configured", path=repo_path, is_worktree=False)
            )
            if verbose > 0:
                print(
                    f"Skipping {repo_path}: No remote origin configured",
                    file=sys.stderr,
                )
            continue

        try:
            uri_parsed = parse_uri(remote_uri)
        except ValueError as e:
            migration.info_skips.append(
                Skip(reason=f"invalid remote URI: {e}", path=repo_path, is_worktree=False)
            )
            if verbose > 0:
                print(f"Skipping {repo_path}: Invalid remote URI: {e}", file=sys.stderr)
            continue

        is_wt = is_worktree(repo_path)
        source_path: Optional[Path] = None
        if is_wt:
            try:
                source_path = get_source_repository(repo_path)
            except Exception:
                migration.info_skips.append(
                    Skip(reason="could not resolve source repository", path=repo_path, is_worktree=is_wt)
                )
                if verbose > 0:
                    print(f"Skipping {repo_path}: Could not resolve source repository", file=sys.stderr)
                continue
            try:
                branch = get_current_branch(repo_path)
            except GitCommandError:
                migration.info_skips.append(
                    Skip(reason="detached HEAD", path=repo_path, is_worktree=is_wt)
                )
                if verbose > 0:
                    print(f"Skipping {repo_path}: Detached HEAD (branch required for worktree path)", file=sys.stderr)
                continue
            try:
                expected_path = resolve_worktree_path(config, uri_parsed, branch, tags)
            except ResolverError as e:
                migration.info_skips.append(
                    Skip(reason=str(e), path=repo_path, is_worktree=is_wt)
                )
                if verbose > 0:
                    print(f"Skipping {repo_path}: {e}", file=sys.stderr)
                continue
        else:
            try:
                expected_path = resolve_source_path(config, uri_parsed, tags)
            except ResolverError as e:
                migration.info_skips.append(
                    Skip(reason=str(e), path=repo_path, is_worktree=is_wt)
                )
                if verbose > 0:
                    print(f"Skipping {repo_path}: {e}", file=sys.stderr)
                continue

        if repo_path.resolve() == expected_path.resolve():
            migration.already_at_target.append(repo_path)
            continue

        if expected_path.exists():
            if inplace:
                # In inplace mode: skip and continue; the executor will leave
                # the existing destination alone.
                migration.info_skips.append(
                    Skip(reason="destination exists", path=expected_path, is_worktree=is_wt)
                )
            else:
                # Copy mode: this is a hard blocker.
                blocked.destinations.append(expected_path)
            continue

        migration.plans.append(
            MigrationPlan(
                old_path=repo_path,
                new_path=expected_path,
                uri=remote_uri,
                is_worktree=is_wt,
                source_path=source_path,
            )
        )

    if blocked.destinations:
        return blocked
    return migration