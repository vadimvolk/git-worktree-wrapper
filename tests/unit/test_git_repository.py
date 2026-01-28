"""Unit tests for git repository operations in src/gww/git/repository.py."""

import pytest
import subprocess
from pathlib import Path

from gww.git.repository import (
    GitError,
    NotGitRepositoryError,
    GitCommandError,
    Repository,
    is_git_repository,
    get_repository_root,
    is_worktree,
    is_submodule,
    get_source_repository,
    get_remote_uri,
    get_current_branch,
    is_clean,
    get_current_commit,
    detect_repository,
    clone_repository,
)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository for testing."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    # Create initial commit
    (tmp_path / "README.md").write_text("# Test")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    return tmp_path


@pytest.fixture
def git_repo_with_worktree(git_repo: Path, tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Create a git repository with a worktree."""
    # Create a branch for the worktree
    subprocess.run(
        ["git", "branch", "feature-branch"],
        cwd=git_repo,
        check=True,
        capture_output=True,
    )
    
    # Create worktree in separate temp directory
    worktree_path = tmp_path_factory.mktemp("worktree")
    subprocess.run(
        ["git", "worktree", "add", str(worktree_path), "feature-branch"],
        cwd=git_repo,
        check=True,
        capture_output=True,
    )
    
    return git_repo, worktree_path


class TestIsGitRepository:
    """Tests for is_git_repository function."""

    def test_returns_true_for_git_repo(self, git_repo: Path) -> None:
        """Test that is_git_repository returns True for git repos."""
        assert is_git_repository(git_repo) is True

    def test_returns_true_for_subdirectory(self, git_repo: Path) -> None:
        """Test that is_git_repository returns True for subdirectory."""
        subdir = git_repo / "src"
        subdir.mkdir()

        assert is_git_repository(subdir) is True

    def test_returns_false_for_non_repo(self, tmp_path: Path) -> None:
        """Test that is_git_repository returns False for non-git directory."""
        assert is_git_repository(tmp_path) is False

    def test_returns_false_for_nonexistent_path(self, tmp_path: Path) -> None:
        """Test that is_git_repository returns False for nonexistent path."""
        nonexistent = tmp_path / "does-not-exist"
        assert is_git_repository(nonexistent) is False


class TestGetRepositoryRoot:
    """Tests for get_repository_root function."""

    def test_returns_root_from_root(self, git_repo: Path) -> None:
        """Test getting root when already at root."""
        root = get_repository_root(git_repo)
        assert root == git_repo.resolve()

    def test_returns_root_from_subdirectory(self, git_repo: Path) -> None:
        """Test getting root from subdirectory."""
        subdir = git_repo / "src" / "deep" / "nested"
        subdir.mkdir(parents=True)

        root = get_repository_root(subdir)
        assert root == git_repo.resolve()

    def test_raises_error_for_non_repo(self, tmp_path: Path) -> None:
        """Test that get_repository_root raises error for non-git directory."""
        with pytest.raises(NotGitRepositoryError, match="Not a git repository"):
            get_repository_root(tmp_path)

    def test_raises_error_for_nonexistent_path(self, tmp_path: Path) -> None:
        """Test that get_repository_root raises error for nonexistent path."""
        nonexistent = tmp_path / "does-not-exist"
        with pytest.raises(NotGitRepositoryError, match="does not exist"):
            get_repository_root(nonexistent)


class TestIsWorktree:
    """Tests for is_worktree function."""

    def test_returns_false_for_main_repo(self, git_repo: Path) -> None:
        """Test that is_worktree returns False for main repository."""
        assert is_worktree(git_repo) is False

    def test_returns_true_for_worktree(self, git_repo_with_worktree: tuple[Path, Path]) -> None:
        """Test that is_worktree returns True for worktree."""
        _, worktree = git_repo_with_worktree
        assert is_worktree(worktree) is True


class TestIsSubmodule:
    """Tests for is_submodule function."""

    def test_returns_false_for_main_repo(self, git_repo: Path) -> None:
        """Test that is_submodule returns False for main repository."""
        assert is_submodule(git_repo) is False

    def test_returns_false_for_worktree(self, git_repo_with_worktree: tuple[Path, Path]) -> None:
        """Test that is_submodule returns False for worktree (.git points to worktrees)."""
        _, worktree = git_repo_with_worktree
        assert is_submodule(worktree) is False

    def test_returns_true_for_submodule(
        self, git_repo: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """Test that is_submodule returns True for a git submodule."""
        # Create a second repo to use as submodule
        sub_repo = tmp_path_factory.mktemp("sub_repo")
        subprocess.run(["git", "init"], cwd=sub_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=sub_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=sub_repo,
            check=True,
            capture_output=True,
        )
        (sub_repo / "file.txt").write_text("sub")
        subprocess.run(["git", "add", "."], cwd=sub_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial"],
            cwd=sub_repo,
            check=True,
            capture_output=True,
        )
        # Add as submodule to main repo (allow file protocol for local path)
        subprocess.run(
            ["git", "-c", "protocol.file.allow=always", "submodule", "add", str(sub_repo), "submod"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        submodule_path = git_repo / "submod"
        assert is_submodule(submodule_path) is True

    def test_returns_false_for_nonexistent_path(self, tmp_path: Path) -> None:
        """Test that is_submodule returns False for path without .git."""
        assert is_submodule(tmp_path) is False

    def test_returns_false_when_git_is_directory(self, git_repo: Path) -> None:
        """Test that is_submodule returns False when .git is a directory (main repo)."""
        assert is_submodule(git_repo) is False


class TestGetSourceRepository:
    """Tests for get_source_repository function (T033)."""

    def test_returns_source_from_worktree(self, git_repo_with_worktree: tuple[Path, Path]) -> None:
        """Test getting source repository from worktree."""
        source, worktree = git_repo_with_worktree

        result = get_source_repository(worktree)

        assert result == source.resolve()

    def test_returns_same_path_for_source_repo(self, git_repo: Path) -> None:
        """Test that source repository returns itself."""
        result = get_source_repository(git_repo)
        assert result == git_repo.resolve()

    def test_works_from_worktree_subdirectory(self, git_repo_with_worktree: tuple[Path, Path]) -> None:
        """Test getting source repository from worktree subdirectory."""
        source, worktree = git_repo_with_worktree
        subdir = worktree / "src"
        subdir.mkdir()

        result = get_source_repository(subdir)

        assert result == source.resolve()


class TestGetRemoteUri:
    """Tests for get_remote_uri function."""

    def test_returns_none_when_no_remote(self, git_repo: Path) -> None:
        """Test that get_remote_uri returns None when no remote."""
        uri = get_remote_uri(git_repo)
        assert uri is None

    def test_returns_uri_when_remote_exists(self, git_repo: Path) -> None:
        """Test getting remote URI when origin is configured."""
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/user/repo.git"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        uri = get_remote_uri(git_repo)

        assert uri == "https://github.com/user/repo.git"


class TestGetCurrentBranch:
    """Tests for get_current_branch function (T048)."""

    def test_returns_current_branch(self, git_repo: Path) -> None:
        """Test getting current branch name."""
        branch = get_current_branch(git_repo)
        assert branch in ("main", "master")

    def test_returns_feature_branch_after_checkout(self, git_repo: Path) -> None:
        """Test getting branch after checking out feature branch."""
        subprocess.run(
            ["git", "checkout", "-b", "feature/test"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        branch = get_current_branch(git_repo)

        assert branch == "feature/test"

    def test_raises_error_when_detached_head(self, git_repo: Path) -> None:
        """Test that error is raised when HEAD is detached."""
        # Get current commit and checkout detached
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        commit = result.stdout.strip()
        subprocess.run(
            ["git", "checkout", commit],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        with pytest.raises(GitCommandError, match="detached"):
            get_current_branch(git_repo)


class TestIsClean:
    """Tests for is_clean function."""

    def test_returns_true_for_clean_repo(self, git_repo: Path) -> None:
        """Test that is_clean returns True for clean repository."""
        assert is_clean(git_repo) is True

    def test_returns_false_for_modified_files(self, git_repo: Path) -> None:
        """Test that is_clean returns False for modified files."""
        (git_repo / "README.md").write_text("# Modified")

        assert is_clean(git_repo) is False

    def test_returns_false_for_untracked_files(self, git_repo: Path) -> None:
        """Test that is_clean returns False for untracked files."""
        (git_repo / "new_file.txt").write_text("new content")

        assert is_clean(git_repo) is False

    def test_returns_false_for_staged_changes(self, git_repo: Path) -> None:
        """Test that is_clean returns False for staged changes."""
        (git_repo / "staged.txt").write_text("staged content")
        subprocess.run(["git", "add", "staged.txt"], cwd=git_repo, check=True, capture_output=True)

        assert is_clean(git_repo) is False


class TestGetCurrentCommit:
    """Tests for get_current_commit function."""

    def test_returns_commit_hash(self, git_repo: Path) -> None:
        """Test getting current commit hash."""
        commit = get_current_commit(git_repo)

        # Should be a 40-character hex string
        assert len(commit) == 40
        assert all(c in "0123456789abcdef" for c in commit)

    def test_returns_different_commit_after_new_commit(self, git_repo: Path) -> None:
        """Test that commit hash changes after new commit."""
        original = get_current_commit(git_repo)

        # Create new commit
        (git_repo / "new.txt").write_text("new")
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "New"], cwd=git_repo, check=True, capture_output=True)

        new = get_current_commit(git_repo)

        assert new != original


class TestDetectRepository:
    """Tests for detect_repository function (T054 partial - repository detection)."""

    def test_detects_main_repository(self, git_repo: Path) -> None:
        """Test detecting main repository properties."""
        repo = detect_repository(git_repo)

        assert repo.path == git_repo.resolve()
        assert repo.is_worktree is False

    def test_detects_worktree(self, git_repo_with_worktree: tuple[Path, Path]) -> None:
        """Test detecting worktree properties."""
        _, worktree = git_repo_with_worktree

        repo = detect_repository(worktree)

        assert repo.path == worktree.resolve()
        assert repo.is_worktree is True

    def test_detects_remote_uri(self, git_repo: Path) -> None:
        """Test detecting remote URI."""
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/org/project.git"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        repo = detect_repository(git_repo)

        assert repo.remote_uri == "https://github.com/org/project.git"

    def test_raises_error_for_non_repo(self, tmp_path: Path) -> None:
        """Test that detect_repository raises error for non-git directory."""
        with pytest.raises(NotGitRepositoryError):
            detect_repository(tmp_path)


class TestRepositoryScanningAndUriExtraction:
    """Tests for repository scanning and URI extraction (T054)."""

    def test_extracts_uri_from_repository(self, git_repo: Path) -> None:
        """Test extracting URI from repository."""
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/vadimvolk/test.git"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        uri = get_remote_uri(git_repo)

        assert uri == "https://github.com/vadimvolk/test.git"

    def test_returns_none_for_repo_without_origin(self, git_repo: Path) -> None:
        """Test that None is returned when no origin remote."""
        uri = get_remote_uri(git_repo)
        assert uri is None

    def test_extracts_ssh_uri(self, git_repo: Path) -> None:
        """Test extracting SSH URI from repository."""
        subprocess.run(
            ["git", "remote", "add", "origin", "git@github.com:user/repo.git"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        uri = get_remote_uri(git_repo)

        assert uri == "git@github.com:user/repo.git"


class TestCloneRepository:
    """Tests for clone_repository function."""

    def test_clone_creates_directory_structure(self, git_repo: Path, tmp_path: Path) -> None:
        """Test that clone creates necessary directory structure."""
        target = tmp_path / "deep" / "nested" / "clone"

        # Note: We need a bare repo or use file:// protocol for local clone
        subprocess.run(
            ["git", "clone", "--bare", str(git_repo), str(tmp_path / "bare.git")],
            check=True,
            capture_output=True,
        )

        result = clone_repository(f"file://{tmp_path / 'bare.git'}", target)

        assert result == target
        assert target.exists()
        assert (target / ".git").exists()
