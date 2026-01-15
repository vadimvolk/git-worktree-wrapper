"""Unit tests for git branch operations in src/sgw/git/branch.py."""

import pytest
import subprocess
from pathlib import Path

from sgw.git.branch import (
    BranchError,
    BranchExistsError,
    BranchNotFoundError,
    branch_exists,
    local_branch_exists,
    remote_branch_exists,
    create_branch,
    delete_branch,
    list_local_branches,
    is_main_branch,
    get_default_branch,
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


class TestBranchExists:
    """Tests for branch_exists function."""

    def test_returns_true_for_existing_local_branch(self, git_repo: Path) -> None:
        """Test that branch_exists returns True for existing local branch."""
        # Get the current branch name (could be 'main' or 'master')
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        current_branch = result.stdout.strip()

        assert branch_exists(git_repo, current_branch) is True

    def test_returns_false_for_nonexistent_branch(self, git_repo: Path) -> None:
        """Test that branch_exists returns False for nonexistent branch."""
        assert branch_exists(git_repo, "nonexistent-branch") is False

    def test_returns_true_for_created_branch(self, git_repo: Path) -> None:
        """Test branch_exists after creating a branch."""
        subprocess.run(
            ["git", "branch", "feature-test"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        assert branch_exists(git_repo, "feature-test") is True


class TestLocalBranchExists:
    """Tests for local_branch_exists function."""

    def test_returns_true_for_local_branch(self, git_repo: Path) -> None:
        """Test that local_branch_exists returns True for local branches."""
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        current_branch = result.stdout.strip()

        assert local_branch_exists(git_repo, current_branch) is True

    def test_returns_false_for_nonexistent_local_branch(self, git_repo: Path) -> None:
        """Test local_branch_exists returns False for nonexistent branch."""
        assert local_branch_exists(git_repo, "does-not-exist") is False


class TestRemoteBranchExists:
    """Tests for remote_branch_exists function."""

    def test_returns_false_when_no_remote(self, git_repo: Path) -> None:
        """Test remote_branch_exists returns False when no remote exists."""
        # No remote configured, so any remote branch should not exist
        assert remote_branch_exists(git_repo, "main") is False


class TestCreateBranch:
    """Tests for create_branch function."""

    def test_creates_new_branch(self, git_repo: Path) -> None:
        """Test creating a new branch."""
        create_branch(git_repo, "new-feature")

        assert local_branch_exists(git_repo, "new-feature") is True

    def test_raises_error_for_existing_branch(self, git_repo: Path) -> None:
        """Test that creating existing branch raises BranchExistsError."""
        create_branch(git_repo, "existing-branch")

        with pytest.raises(BranchExistsError, match="already exists"):
            create_branch(git_repo, "existing-branch")

    def test_creates_branch_from_start_point(self, git_repo: Path) -> None:
        """Test creating branch from specific start point."""
        # Get current commit
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        commit = result.stdout.strip()

        create_branch(git_repo, "from-commit", start_point=commit[:7])

        assert local_branch_exists(git_repo, "from-commit") is True


class TestDeleteBranch:
    """Tests for delete_branch function."""

    def test_deletes_existing_branch(self, git_repo: Path) -> None:
        """Test deleting an existing branch."""
        create_branch(git_repo, "to-delete")
        assert local_branch_exists(git_repo, "to-delete") is True

        delete_branch(git_repo, "to-delete")

        assert local_branch_exists(git_repo, "to-delete") is False

    def test_raises_error_for_nonexistent_branch(self, git_repo: Path) -> None:
        """Test that deleting nonexistent branch raises BranchNotFoundError."""
        with pytest.raises(BranchNotFoundError, match="not found"):
            delete_branch(git_repo, "nonexistent")

    def test_force_deletes_unmerged_branch(self, git_repo: Path) -> None:
        """Test force deleting an unmerged branch."""
        # Create branch with unmerged changes
        create_branch(git_repo, "unmerged")
        subprocess.run(["git", "checkout", "unmerged"], cwd=git_repo, check=True, capture_output=True)
        (git_repo / "new_file.txt").write_text("content")
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Unmerged commit"], cwd=git_repo, check=True, capture_output=True)
        
        # Get original branch and switch back
        result = subprocess.run(
            ["git", "branch", "--format=%(refname:short)"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        branches = result.stdout.strip().split("\n")
        main_branch = [b for b in branches if b in ("main", "master")][0]
        subprocess.run(["git", "checkout", main_branch], cwd=git_repo, check=True, capture_output=True)

        # Force delete should succeed
        delete_branch(git_repo, "unmerged", force=True)

        assert local_branch_exists(git_repo, "unmerged") is False


class TestListLocalBranches:
    """Tests for list_local_branches function."""

    def test_lists_all_local_branches(self, git_repo: Path) -> None:
        """Test listing all local branches."""
        create_branch(git_repo, "feature-1")
        create_branch(git_repo, "feature-2")

        branches = list_local_branches(git_repo)

        assert "feature-1" in branches
        assert "feature-2" in branches
        # Should have at least the default branch plus our two
        assert len(branches) >= 3

    def test_returns_empty_for_no_branches(self, tmp_path: Path) -> None:
        """Test listing branches in repo with only initial branch."""
        # Create fresh repo without extra branches
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        (tmp_path / "README.md").write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, check=True, capture_output=True)

        branches = list_local_branches(tmp_path)

        # Should have exactly one branch (main or master)
        assert len(branches) == 1


class TestIsMainBranch:
    """Tests for is_main_branch function."""

    def test_returns_true_for_main(self) -> None:
        """Test that is_main_branch returns True for 'main'."""
        assert is_main_branch("main") is True

    def test_returns_true_for_master(self) -> None:
        """Test that is_main_branch returns True for 'master'."""
        assert is_main_branch("master") is True

    def test_returns_false_for_other_branches(self) -> None:
        """Test that is_main_branch returns False for other branches."""
        assert is_main_branch("develop") is False
        assert is_main_branch("feature/test") is False
        assert is_main_branch("release-1.0") is False
        assert is_main_branch("Main") is False  # Case sensitive


class TestGetDefaultBranch:
    """Tests for get_default_branch function."""

    def test_returns_main_or_master(self, git_repo: Path) -> None:
        """Test that get_default_branch returns 'main' or 'master'."""
        default = get_default_branch(git_repo)

        assert default in ("main", "master")

    def test_raises_error_when_neither_exists(self, tmp_path: Path) -> None:
        """Test that error is raised when neither main nor master exists."""
        # Create repo with custom branch name
        subprocess.run(["git", "init", "--initial-branch=develop"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        (tmp_path / "README.md").write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=tmp_path, check=True, capture_output=True)

        with pytest.raises(BranchError, match="Could not determine default branch"):
            get_default_branch(tmp_path)
