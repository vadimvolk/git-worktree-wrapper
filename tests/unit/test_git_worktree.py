"""Unit tests for git worktree operations in src/sgw/git/worktree.py."""

import pytest
import subprocess
from pathlib import Path

from sgw.git.worktree import (
    WorktreeError,
    WorktreeNotFoundError,
    WorktreeDirtyError,
    WorktreeExistsError,
    Worktree,
    list_worktrees,
    find_worktree_by_branch,
    find_worktree_by_path,
    is_worktree_clean,
    add_worktree,
    remove_worktree,
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


class TestListWorktrees:
    """Tests for list_worktrees function."""

    def test_lists_main_worktree(self, git_repo: Path) -> None:
        """Test listing worktrees when only main exists."""
        worktrees = list_worktrees(git_repo)

        assert len(worktrees) >= 1
        # Main worktree should be listed
        main_wt = [w for w in worktrees if w.path == git_repo.resolve()]
        assert len(main_wt) == 1

    def test_lists_all_worktrees(self, git_repo_with_worktree: tuple[Path, Path]) -> None:
        """Test listing all worktrees including added ones."""
        source, worktree = git_repo_with_worktree

        worktrees = list_worktrees(source)

        assert len(worktrees) >= 2
        paths = [w.path.resolve() for w in worktrees]
        assert source.resolve() in paths
        assert worktree.resolve() in paths

    def test_worktree_has_correct_branch(self, git_repo_with_worktree: tuple[Path, Path]) -> None:
        """Test that worktree has correct branch information."""
        source, worktree = git_repo_with_worktree

        worktrees = list_worktrees(source)
        wt = [w for w in worktrees if w.path.resolve() == worktree.resolve()][0]

        assert wt.branch == "feature-branch"


class TestFindWorktreeByBranch:
    """Tests for find_worktree_by_branch function (T041)."""

    def test_finds_worktree_by_branch_name(self, git_repo_with_worktree: tuple[Path, Path]) -> None:
        """Test finding worktree by branch name."""
        source, worktree = git_repo_with_worktree

        found = find_worktree_by_branch(source, "feature-branch")

        assert found is not None
        assert found.path.resolve() == worktree.resolve()
        assert found.branch == "feature-branch"

    def test_returns_none_for_nonexistent_branch(self, git_repo: Path) -> None:
        """Test that None is returned for nonexistent branch."""
        found = find_worktree_by_branch(git_repo, "nonexistent-branch")
        assert found is None

    def test_finds_main_branch_worktree(self, git_repo: Path) -> None:
        """Test finding main branch worktree."""
        # Get main branch name
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        main_branch = result.stdout.strip()

        found = find_worktree_by_branch(git_repo, main_branch)

        assert found is not None
        assert found.branch == main_branch


class TestFindWorktreeByPath:
    """Tests for find_worktree_by_path function (T041)."""

    def test_finds_worktree_by_path(self, git_repo_with_worktree: tuple[Path, Path]) -> None:
        """Test finding worktree by path."""
        source, worktree = git_repo_with_worktree

        found = find_worktree_by_path(source, worktree)

        assert found is not None
        assert found.path.resolve() == worktree.resolve()

    def test_returns_none_for_invalid_path(self, git_repo: Path, tmp_path_factory: pytest.TempPathFactory) -> None:
        """Test that None is returned for path that's not a worktree."""
        invalid_path = tmp_path_factory.mktemp("not_worktree")

        found = find_worktree_by_path(git_repo, invalid_path)

        assert found is None

    def test_finds_source_repo_by_path(self, git_repo_with_worktree: tuple[Path, Path]) -> None:
        """Test finding source repository by its path."""
        source, _ = git_repo_with_worktree

        found = find_worktree_by_path(source, source)

        assert found is not None
        assert found.path.resolve() == source.resolve()


class TestIsWorktreeClean:
    """Tests for is_worktree_clean function (T040)."""

    def test_returns_true_for_clean_worktree(self, git_repo_with_worktree: tuple[Path, Path]) -> None:
        """Test that is_worktree_clean returns True for clean worktree."""
        _, worktree = git_repo_with_worktree

        assert is_worktree_clean(worktree) is True

    def test_returns_false_for_modified_file(self, git_repo_with_worktree: tuple[Path, Path]) -> None:
        """Test that is_worktree_clean returns False for modified files."""
        _, worktree = git_repo_with_worktree

        # Modify a file
        (worktree / "README.md").write_text("# Modified")

        assert is_worktree_clean(worktree) is False

    def test_returns_false_for_untracked_file(self, git_repo_with_worktree: tuple[Path, Path]) -> None:
        """Test that is_worktree_clean returns False for untracked files."""
        _, worktree = git_repo_with_worktree

        # Add untracked file
        (worktree / "new_file.txt").write_text("new content")

        assert is_worktree_clean(worktree) is False

    def test_returns_false_for_staged_changes(self, git_repo_with_worktree: tuple[Path, Path]) -> None:
        """Test that is_worktree_clean returns False for staged changes."""
        _, worktree = git_repo_with_worktree

        # Stage a new file
        (worktree / "staged.txt").write_text("staged")
        subprocess.run(["git", "add", "staged.txt"], cwd=worktree, check=True, capture_output=True)

        assert is_worktree_clean(worktree) is False

    def test_returns_false_for_deleted_file(self, git_repo_with_worktree: tuple[Path, Path]) -> None:
        """Test that is_worktree_clean returns False for deleted files."""
        _, worktree = git_repo_with_worktree

        # Delete tracked file
        (worktree / "README.md").unlink()

        assert is_worktree_clean(worktree) is False


class TestAddWorktree:
    """Tests for add_worktree function."""

    def test_adds_worktree_for_existing_branch(self, git_repo: Path, tmp_path_factory: pytest.TempPathFactory) -> None:
        """Test adding worktree for existing branch."""
        # Create branch first
        subprocess.run(
            ["git", "branch", "new-feature"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        worktree_path = tmp_path_factory.mktemp("worktree")
        result = add_worktree(git_repo, worktree_path, "new-feature")

        assert result == worktree_path
        assert worktree_path.exists()
        assert (worktree_path / ".git").exists()

    def test_raises_error_for_existing_worktree(self, git_repo_with_worktree: tuple[Path, Path], tmp_path_factory: pytest.TempPathFactory) -> None:
        """Test that adding worktree for branch with existing worktree raises error."""
        source, _ = git_repo_with_worktree

        new_path = tmp_path_factory.mktemp("new_worktree")
        with pytest.raises(WorktreeExistsError, match="already exists"):
            add_worktree(source, new_path, "feature-branch")

    def test_creates_branch_when_requested(self, git_repo: Path, tmp_path_factory: pytest.TempPathFactory) -> None:
        """Test adding worktree with branch creation."""
        worktree_path = tmp_path_factory.mktemp("worktree")

        result = add_worktree(
            git_repo,
            worktree_path,
            "brand-new-branch",
            create_branch=True,
        )

        assert result == worktree_path
        assert worktree_path.exists()

        # Verify branch was created
        branches = subprocess.run(
            ["git", "branch"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        assert "brand-new-branch" in branches.stdout


class TestRemoveWorktree:
    """Tests for remove_worktree function."""

    def test_removes_clean_worktree(self, git_repo_with_worktree: tuple[Path, Path]) -> None:
        """Test removing a clean worktree."""
        source, worktree = git_repo_with_worktree

        remove_worktree(source, worktree)

        assert not worktree.exists()

    def test_raises_error_for_dirty_worktree(self, git_repo_with_worktree: tuple[Path, Path]) -> None:
        """Test that removing dirty worktree raises error without force."""
        source, worktree = git_repo_with_worktree

        # Make worktree dirty
        (worktree / "dirty.txt").write_text("dirty")

        with pytest.raises(WorktreeDirtyError, match="uncommitted changes"):
            remove_worktree(source, worktree)

    def test_force_removes_dirty_worktree(self, git_repo_with_worktree: tuple[Path, Path]) -> None:
        """Test force removing dirty worktree."""
        source, worktree = git_repo_with_worktree

        # Make worktree dirty
        (worktree / "dirty.txt").write_text("dirty")

        remove_worktree(source, worktree, force=True)

        # Worktree should be removed even though it was dirty
        worktrees = list_worktrees(source)
        paths = [w.path.resolve() for w in worktrees]
        assert worktree.resolve() not in paths

    def test_raises_error_for_nonexistent_worktree(self, git_repo: Path, tmp_path_factory: pytest.TempPathFactory) -> None:
        """Test that removing nonexistent worktree raises error."""
        fake_path = tmp_path_factory.mktemp("fake")

        with pytest.raises(WorktreeNotFoundError, match="not found"):
            remove_worktree(git_repo, fake_path)


class TestWorktreeDataclass:
    """Tests for Worktree dataclass attributes."""

    def test_worktree_has_expected_attributes(self, git_repo_with_worktree: tuple[Path, Path]) -> None:
        """Test that Worktree has all expected attributes."""
        source, worktree = git_repo_with_worktree

        worktrees = list_worktrees(source)
        wt = [w for w in worktrees if w.path.resolve() == worktree.resolve()][0]

        assert hasattr(wt, "path")
        assert hasattr(wt, "branch")
        assert hasattr(wt, "commit")
        assert hasattr(wt, "is_bare")
        assert hasattr(wt, "is_detached")
        assert hasattr(wt, "is_locked")

    def test_worktree_branch_is_correct(self, git_repo_with_worktree: tuple[Path, Path]) -> None:
        """Test that worktree branch attribute is correct."""
        source, worktree = git_repo_with_worktree

        worktrees = list_worktrees(source)
        wt = [w for w in worktrees if w.path.resolve() == worktree.resolve()][0]

        assert wt.branch == "feature-branch"

    def test_worktree_commit_is_valid(self, git_repo_with_worktree: tuple[Path, Path]) -> None:
        """Test that worktree commit attribute is valid."""
        source, worktree = git_repo_with_worktree

        worktrees = list_worktrees(source)
        wt = [w for w in worktrees if w.path.resolve() == worktree.resolve()][0]

        # Commit should be a hex string
        assert len(wt.commit) >= 7  # At least short hash
        assert all(c in "0123456789abcdef" for c in wt.commit)
