"""Git branch operations."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from gww.git.repository import GitCommandError, _run_git


class BranchError(Exception):
    """Base exception for branch-related errors."""

    pass


class BranchNotFoundError(BranchError):
    """Raised when branch cannot be found."""

    pass


class BranchExistsError(BranchError):
    """Raised when branch already exists."""

    pass


def branch_exists(repo_path: Path, branch: str) -> bool:
    """Check if a branch exists (local or remote).

    Args:
        repo_path: Path to repository.
        branch: Branch name to check.

    Returns:
        True if branch exists.
    """
    # Check local branches
    result = _run_git(
        ["rev-parse", "--verify", f"refs/heads/{branch}"],
        cwd=repo_path,
        check=False,
    )
    if result.returncode == 0:
        return True

    # Check remote branches
    result = _run_git(
        ["rev-parse", "--verify", f"refs/remotes/origin/{branch}"],
        cwd=repo_path,
        check=False,
    )
    if result.returncode == 0:
        return True

    return False


def local_branch_exists(repo_path: Path, branch: str) -> bool:
    """Check if a local branch exists.

    Args:
        repo_path: Path to repository.
        branch: Branch name to check.

    Returns:
        True if local branch exists.
    """
    result = _run_git(
        ["rev-parse", "--verify", f"refs/heads/{branch}"],
        cwd=repo_path,
        check=False,
    )
    return result.returncode == 0


def remote_branch_exists(repo_path: Path, branch: str, remote: str = "origin") -> bool:
    """Check if a remote branch exists.

    Args:
        repo_path: Path to repository.
        branch: Branch name to check.
        remote: Remote name (default: "origin").

    Returns:
        True if remote branch exists.
    """
    result = _run_git(
        ["rev-parse", "--verify", f"refs/remotes/{remote}/{branch}"],
        cwd=repo_path,
        check=False,
    )
    return result.returncode == 0


def create_branch(
    repo_path: Path,
    branch: str,
    start_point: Optional[str] = None,
) -> None:
    """Create a new branch.

    Args:
        repo_path: Path to repository.
        branch: Branch name to create.
        start_point: Commit/branch to start from (default: HEAD).

    Raises:
        BranchExistsError: If branch already exists.
        GitCommandError: If command fails.
    """
    if local_branch_exists(repo_path, branch):
        raise BranchExistsError(f"Branch '{branch}' already exists")

    args = ["branch", branch]
    if start_point:
        args.append(start_point)

    _run_git(args, cwd=repo_path, check=True)


def delete_branch(
    repo_path: Path,
    branch: str,
    force: bool = False,
) -> None:
    """Delete a local branch.

    Args:
        repo_path: Path to repository.
        branch: Branch name to delete.
        force: If True, force deletion even if not merged.

    Raises:
        BranchNotFoundError: If branch doesn't exist.
        GitCommandError: If command fails.
    """
    if not local_branch_exists(repo_path, branch):
        raise BranchNotFoundError(f"Branch '{branch}' not found")

    flag = "-D" if force else "-d"
    _run_git(["branch", flag, branch], cwd=repo_path, check=True)


def list_local_branches(repo_path: Path) -> list[str]:
    """List all local branches.

    Args:
        repo_path: Path to repository.

    Returns:
        List of branch names.
    """
    result = _run_git(
        ["branch", "--format=%(refname:short)"],
        cwd=repo_path,
        check=True,
    )

    branches = [b.strip() for b in result.stdout.strip().split("\n") if b.strip()]
    return branches


def list_remote_branches(repo_path: Path, remote: str = "origin") -> list[str]:
    """List all remote branches.

    Args:
        repo_path: Path to repository.
        remote: Remote name (default: "origin").

    Returns:
        List of branch names (without remote prefix).
    """
    result = _run_git(
        ["branch", "-r", "--format=%(refname:short)"],
        cwd=repo_path,
        check=True,
    )

    prefix = f"{remote}/"
    branches: list[str] = []

    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if line.startswith(prefix):
            branch = line[len(prefix) :]
            if branch != "HEAD":  # Skip origin/HEAD
                branches.append(branch)

    return branches


def get_tracking_branch(repo_path: Path, branch: str) -> Optional[str]:
    """Get the upstream tracking branch for a local branch.

    Args:
        repo_path: Path to repository.
        branch: Local branch name.

    Returns:
        Tracking branch name (e.g., "origin/main") or None.
    """
    result = _run_git(
        ["rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}"],
        cwd=repo_path,
        check=False,
    )

    if result.returncode != 0:
        return None

    return result.stdout.strip()


def fetch_remote(repo_path: Path, remote: str = "origin") -> None:
    """Fetch updates from remote.

    Args:
        repo_path: Path to repository.
        remote: Remote name (default: "origin").

    Raises:
        GitCommandError: If command fails.
    """
    _run_git(["fetch", remote], cwd=repo_path, check=True)


def is_main_branch(branch: str) -> bool:
    """Check if branch is a main/master branch.

    Args:
        branch: Branch name to check.

    Returns:
        True if branch is "main" or "master".
    """
    return branch in ("main", "master")


def get_default_branch(repo_path: Path) -> str:
    """Get the default branch (main or master).

    Args:
        repo_path: Path to repository.

    Returns:
        Default branch name.

    Raises:
        BranchError: If neither main nor master exists.
    """
    if local_branch_exists(repo_path, "main"):
        return "main"
    if local_branch_exists(repo_path, "master"):
        return "master"

    # Check remote
    if remote_branch_exists(repo_path, "main"):
        return "main"
    if remote_branch_exists(repo_path, "master"):
        return "master"

    raise BranchError("Could not determine default branch (neither 'main' nor 'master' found)")
