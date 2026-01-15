"""Git repository detection and operations."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class GitError(Exception):
    """Base exception for git-related errors."""

    pass


class NotGitRepositoryError(GitError):
    """Raised when path is not a git repository."""

    pass


class GitCommandError(GitError):
    """Raised when a git command fails."""

    pass


@dataclass
class Repository:
    """Represents a git repository (source or worktree).

    Attributes:
        path: Absolute path to repository root.
        is_worktree: Whether this is a worktree (not main repository).
        remote_uri: Remote origin URI (if available).
    """

    path: Path
    is_worktree: bool
    remote_uri: Optional[str] = None


def _run_git(
    args: list[str],
    cwd: Path,
    check: bool = True,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a git command.

    Args:
        args: Git command arguments (without 'git').
        cwd: Working directory for the command.
        check: Whether to raise on non-zero exit.
        capture_output: Whether to capture stdout/stderr.

    Returns:
        CompletedProcess with command results.

    Raises:
        GitCommandError: If command fails and check=True.
    """
    cmd = ["git"] + args
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=capture_output,
            text=True,
            check=False,
        )
        if check and result.returncode != 0:
            raise GitCommandError(
                f"Git command failed: {' '.join(cmd)}\n"
                f"Exit code: {result.returncode}\n"
                f"Stderr: {result.stderr.strip()}"
            )
        return result
    except FileNotFoundError:
        raise GitCommandError("Git is not installed or not in PATH")


def is_git_repository(path: Path) -> bool:
    """Check if a path is inside a git repository.

    Args:
        path: Path to check.

    Returns:
        True if path is inside a git repository.
    """
    if not path.exists():
        return False

    result = _run_git(
        ["rev-parse", "--git-dir"],
        cwd=path,
        check=False,
    )
    return result.returncode == 0


def get_repository_root(path: Path) -> Path:
    """Get the root directory of a git repository.

    Args:
        path: Path inside the repository.

    Returns:
        Absolute path to repository root.

    Raises:
        NotGitRepositoryError: If path is not in a git repository.
    """
    if not path.exists():
        raise NotGitRepositoryError(f"Path does not exist: {path}")

    result = _run_git(
        ["rev-parse", "--show-toplevel"],
        cwd=path,
        check=False,
    )

    if result.returncode != 0:
        raise NotGitRepositoryError(f"Not a git repository: {path}")

    return Path(result.stdout.strip()).resolve()


def is_worktree(path: Path) -> bool:
    """Check if a path is a git worktree (not main repository).

    A worktree has a .git file pointing to the main repository's
    worktrees directory, while the main repository has a .git directory.

    Args:
        path: Path to repository root.

    Returns:
        True if path is a worktree.
    """
    git_path = path / ".git"
    return git_path.is_file()


def get_source_repository(worktree_path: Path) -> Path:
    """Get the source (main) repository for a worktree.

    Args:
        worktree_path: Path to worktree.

    Returns:
        Path to source repository.

    Raises:
        NotGitRepositoryError: If path is not a valid worktree.
        GitCommandError: If git command fails.
    """
    repo_root = get_repository_root(worktree_path)

    if not is_worktree(repo_root):
        # Already at source repository
        return repo_root

    # Read .git file to find worktree config
    git_file = repo_root / ".git"
    content = git_file.read_text().strip()

    # Format: "gitdir: /path/to/repo/.git/worktrees/name"
    if not content.startswith("gitdir:"):
        raise NotGitRepositoryError(f"Invalid .git file in worktree: {worktree_path}")

    gitdir = content.split(":", 1)[1].strip()
    gitdir_path = Path(gitdir).resolve()

    # Navigate from .git/worktrees/<name> to the repository root
    # Structure: /repo/.git/worktrees/<name>
    if gitdir_path.parent.name == "worktrees" and gitdir_path.parent.parent.name == ".git":
        source_git = gitdir_path.parent.parent
        return source_git.parent

    raise NotGitRepositoryError(
        f"Could not determine source repository for worktree: {worktree_path}"
    )


def get_remote_uri(repo_path: Path) -> Optional[str]:
    """Get the remote origin URI for a repository.

    Args:
        repo_path: Path to repository.

    Returns:
        Remote URI string, or None if not configured.
    """
    result = _run_git(
        ["remote", "get-url", "origin"],
        cwd=repo_path,
        check=False,
    )

    if result.returncode != 0:
        return None

    return result.stdout.strip()


def get_current_branch(repo_path: Path) -> str:
    """Get the current branch name.

    Args:
        repo_path: Path to repository.

    Returns:
        Branch name.

    Raises:
        GitCommandError: If command fails or HEAD is detached.
    """
    result = _run_git(
        ["rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo_path,
        check=True,
    )

    branch = result.stdout.strip()
    if branch == "HEAD":
        raise GitCommandError("HEAD is detached, not on a branch")

    return branch


def is_clean(repo_path: Path) -> bool:
    """Check if repository has no uncommitted changes.

    Args:
        repo_path: Path to repository.

    Returns:
        True if repository is clean (no changes).
    """
    result = _run_git(
        ["status", "--porcelain"],
        cwd=repo_path,
        check=False,
    )

    return not bool(result.stdout.strip())


def get_current_commit(repo_path: Path) -> str:
    """Get the current commit hash.

    Args:
        repo_path: Path to repository.

    Returns:
        Full commit hash.

    Raises:
        GitCommandError: If command fails.
    """
    result = _run_git(
        ["rev-parse", "HEAD"],
        cwd=repo_path,
        check=True,
    )

    return result.stdout.strip()


def detect_repository(path: Path) -> Repository:
    """Detect repository type and properties at a path.

    Args:
        path: Path to check.

    Returns:
        Repository object with detected properties.

    Raises:
        NotGitRepositoryError: If path is not a git repository.
    """
    repo_root = get_repository_root(path)
    is_wt = is_worktree(repo_root)
    remote = get_remote_uri(repo_root)

    return Repository(
        path=repo_root,
        is_worktree=is_wt,
        remote_uri=remote,
    )


def clone_repository(uri: str, target_path: Path) -> Path:
    """Clone a repository to the specified path.

    Args:
        uri: Repository URI to clone.
        target_path: Path where repository should be cloned.

    Returns:
        Path to cloned repository.

    Raises:
        GitCommandError: If clone fails.
    """
    # Ensure parent directory exists
    target_path.parent.mkdir(parents=True, exist_ok=True)

    _run_git(
        ["clone", uri, str(target_path)],
        cwd=target_path.parent,
        check=True,
    )

    return target_path


def pull_repository(repo_path: Path) -> None:
    """Pull changes from remote.

    Args:
        repo_path: Path to repository.

    Raises:
        GitCommandError: If pull fails.
    """
    _run_git(
        ["pull"],
        cwd=repo_path,
        check=True,
    )
