"""Git worktree operations wrapper."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from gww.git.repository import GitCommandError, _run_git, get_repository_root, is_worktree


class WorktreeError(Exception):
    """Base exception for worktree-related errors."""

    pass


class WorktreeNotFoundError(WorktreeError):
    """Raised when worktree cannot be found."""

    pass


class WorktreeDirtyError(WorktreeError):
    """Raised when worktree has uncommitted changes."""

    pass


class WorktreeExistsError(WorktreeError):
    """Raised when worktree already exists."""

    pass


@dataclass
class Worktree:
    """Represents a git worktree.

    Attributes:
        path: Absolute path to worktree root.
        branch: Branch checked out in worktree.
        commit: Commit hash (abbreviated).
        is_bare: Whether this is the bare repository.
        is_detached: Whether HEAD is detached.
        is_locked: Whether worktree is locked.
        prunable: Reason worktree can be pruned, if any.
    """

    path: Path
    branch: Optional[str]
    commit: str
    is_bare: bool = False
    is_detached: bool = False
    is_locked: bool = False
    prunable: Optional[str] = None


def list_worktrees(repo_path: Path) -> list[Worktree]:
    """List all worktrees for a repository.

    Args:
        repo_path: Path to repository (source or worktree).

    Returns:
        List of Worktree objects.

    Raises:
        GitCommandError: If command fails.
    """
    result = _run_git(
        ["worktree", "list", "--porcelain"],
        cwd=repo_path,
        check=True,
    )

    worktrees: list[Worktree] = []
    current: dict[str, str] = {}

    for line in result.stdout.strip().split("\n"):
        line = line.strip()

        if not line:
            # End of worktree entry
            if current:
                wt = _parse_worktree_entry(current)
                worktrees.append(wt)
                current = {}
            continue

        if line.startswith("worktree "):
            current["path"] = line[9:]
        elif line.startswith("HEAD "):
            current["commit"] = line[5:]
        elif line.startswith("branch "):
            current["branch"] = line[7:]
        elif line == "bare":
            current["bare"] = "true"
        elif line == "detached":
            current["detached"] = "true"
        elif line == "locked":
            current["locked"] = "true"
        elif line.startswith("prunable "):
            current["prunable"] = line[9:]

    # Handle last entry
    if current:
        wt = _parse_worktree_entry(current)
        worktrees.append(wt)

    return worktrees


def _parse_worktree_entry(data: dict[str, str]) -> Worktree:
    """Parse a worktree entry from porcelain output.

    Args:
        data: Dictionary of worktree properties.

    Returns:
        Worktree object.
    """
    branch = data.get("branch")
    if branch and branch.startswith("refs/heads/"):
        branch = branch[11:]  # Remove refs/heads/ prefix

    return Worktree(
        path=Path(data["path"]),
        branch=branch,
        commit=data.get("commit", ""),
        is_bare=data.get("bare") == "true",
        is_detached=data.get("detached") == "true",
        is_locked=data.get("locked") == "true",
        prunable=data.get("prunable"),
    )


def find_worktree_by_branch(repo_path: Path, branch: str) -> Optional[Worktree]:
    """Find a worktree by branch name.

    Args:
        repo_path: Path to repository.
        branch: Branch name to find.

    Returns:
        Worktree if found, None otherwise.
    """
    worktrees = list_worktrees(repo_path)

    for wt in worktrees:
        if wt.branch == branch:
            return wt

    return None


def find_worktree_by_path(repo_path: Path, worktree_path: Path) -> Optional[Worktree]:
    """Find a worktree by path.

    Args:
        repo_path: Path to repository.
        worktree_path: Path to worktree.

    Returns:
        Worktree if found, None otherwise.
    """
    worktrees = list_worktrees(repo_path)
    resolved_path = worktree_path.resolve()

    for wt in worktrees:
        if wt.path.resolve() == resolved_path:
            return wt

    return None


def is_worktree_clean(worktree_path: Path) -> bool:
    """Check if worktree has no uncommitted changes.

    Args:
        worktree_path: Path to worktree.

    Returns:
        True if worktree is clean.
    """
    result = _run_git(
        ["status", "--porcelain"],
        cwd=worktree_path,
        check=False,
    )

    return not bool(result.stdout.strip())


def add_worktree(
    repo_path: Path,
    worktree_path: Path,
    branch: str,
    create_branch: bool = False,
    base_commit: Optional[str] = None,
) -> Path:
    """Add a new worktree.

    Args:
        repo_path: Path to source repository.
        worktree_path: Path where worktree should be created.
        branch: Branch to checkout in worktree.
        create_branch: If True, create branch if it doesn't exist.
        base_commit: Commit to base new branch on (if create_branch=True).

    Returns:
        Path to created worktree.

    Raises:
        WorktreeExistsError: If worktree for branch already exists.
        GitCommandError: If command fails.
    """
    # Check if worktree already exists for this branch
    existing = find_worktree_by_branch(repo_path, branch)
    if existing:
        raise WorktreeExistsError(
            f"Worktree for branch '{branch}' already exists at: {existing.path}"
        )

    # Ensure parent directory exists
    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    args = ["worktree", "add", str(worktree_path)]

    if create_branch:
        args.extend(["-b", branch])
        if base_commit:
            args.append(base_commit)
    else:
        args.append(branch)

    try:
        _run_git(args, cwd=repo_path, check=True)
    except GitCommandError as e:
        if "already exists" in str(e):
            raise WorktreeExistsError(
                f"Branch '{branch}' is already checked out in another worktree"
            ) from e
        raise

    return worktree_path


def remove_worktree(
    repo_path: Path,
    worktree_path: Path,
    force: bool = False,
) -> None:
    """Remove a worktree.

    Args:
        repo_path: Path to source repository.
        worktree_path: Path to worktree to remove.
        force: If True, remove even if dirty.

    Raises:
        WorktreeNotFoundError: If worktree doesn't exist.
        WorktreeDirtyError: If worktree is dirty and force=False.
        GitCommandError: If command fails.
    """
    # Verify worktree exists
    wt = find_worktree_by_path(repo_path, worktree_path)
    if not wt:
        raise WorktreeNotFoundError(f"Worktree not found: {worktree_path}")

    # Check if clean (unless forcing)
    if not force and not is_worktree_clean(worktree_path):
        raise WorktreeDirtyError(
            f"Worktree has uncommitted changes: {worktree_path}\n"
            "Use --force to remove anyway."
        )

    args = ["worktree", "remove"]
    if force:
        args.append("--force")
    args.append(str(worktree_path))

    _run_git(args, cwd=repo_path, check=True)


def prune_worktrees(repo_path: Path, dry_run: bool = False) -> list[str]:
    """Prune stale worktree information.

    Args:
        repo_path: Path to repository.
        dry_run: If True, only report what would be pruned.

    Returns:
        List of pruned worktree paths.
    """
    args = ["worktree", "prune"]
    if dry_run:
        args.append("--dry-run")

    result = _run_git(args, cwd=repo_path, check=True)

    # Parse output for pruned paths
    pruned: list[str] = []
    for line in result.stdout.strip().split("\n"):
        if line.strip():
            pruned.append(line.strip())

    return pruned
