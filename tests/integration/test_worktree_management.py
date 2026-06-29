"""Integration tests for worktree management commands (add, remove, pull)."""

import pytest
import subprocess
from pathlib import Path

from gww.cli.commands.add import run_add
from gww.cli.commands.remove import run_remove
from gww.cli.commands.pull import run_pull
from tests.conftest import make_ctx


@pytest.fixture
def git_repo_with_remote(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Create a git repository with a remote for testing."""
    bare = tmp_path_factory.mktemp("bare")
    bare_repo = bare / "origin.git"
    subprocess.run(["git", "init", "--bare", str(bare_repo)], check=True, capture_output=True)

    local = tmp_path_factory.mktemp("local")
    subprocess.run(["git", "init"], cwd=local, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=local,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=local,
        check=True,
        capture_output=True,
    )
    (local / "README.md").write_text("# Test")
    subprocess.run(["git", "add", "."], cwd=local, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=local, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", f"file://{bare_repo}"],
        cwd=local,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "push", "-u", "origin", "HEAD"], cwd=local, check=True, capture_output=True)

    subprocess.run(["git", "branch", "feature-test"], cwd=local, check=True, capture_output=True)

    return local, bare_repo


@pytest.fixture
def worktree_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a temporary directory for worktrees."""
    return tmp_path_factory.mktemp("worktrees")


class TestAddWorktreeCommand:
    """Integration tests for add command (T034)."""

    def test_add_worktree_for_existing_branch(
        self,
        git_repo_with_remote: tuple[Path, Path],
        config_dir: Path,
        worktree_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test adding worktree for an existing branch."""
        local, _ = git_repo_with_remote

        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: ~/sources
default_worktrees: {worktree_dir}/norm_branch()
""")

        monkeypatch.chdir(local)

        result = run_add(make_ctx(branch="feature-test"))

        assert result == 0
        expected_path = worktree_dir / "feature-test"
        assert expected_path.exists()
        assert (expected_path / ".git").exists()

    def test_add_worktree_with_create_branch(
        self,
        git_repo_with_remote: tuple[Path, Path],
        config_dir: Path,
        worktree_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test adding worktree with branch creation."""
        local, _ = git_repo_with_remote

        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: ~/sources
default_worktrees: {worktree_dir}/norm_branch()
""")

        monkeypatch.chdir(local)

        result = run_add(make_ctx(branch="new-feature", create_branch=True))

        assert result == 0
        expected_path = worktree_dir / "new-feature"
        assert expected_path.exists()

    def test_add_fails_for_nonexistent_branch(
        self,
        git_repo_with_remote: tuple[Path, Path],
        config_dir: Path,
        worktree_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that add fails for nonexistent branch without --create-branch."""
        local, _ = git_repo_with_remote

        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: ~/sources
default_worktrees: {worktree_dir}/norm_branch()
""")

        monkeypatch.chdir(local)

        result = run_add(make_ctx(branch="nonexistent-branch"))

        assert result == 1

    def test_add_fails_outside_git_repo(
        self,
        config_dir: Path,
        worktree_dir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that add fails when not in a git repository."""
        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: ~/sources
default_worktrees: {worktree_dir}/norm_branch()
""")

        monkeypatch.chdir(tmp_path)

        result = run_add(make_ctx(branch="feature"))

        assert result == 1


class TestRemoveWorktreeCommand:
    """Integration tests for remove command (T042)."""

    def test_remove_worktree_by_branch(
        self,
        git_repo_with_remote: tuple[Path, Path],
        worktree_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test removing worktree by branch name."""
        local, _ = git_repo_with_remote

        worktree_path = worktree_dir / "feature-test"
        subprocess.run(
            ["git", "worktree", "add", str(worktree_path), "feature-test"],
            cwd=local,
            check=True,
            capture_output=True,
        )

        monkeypatch.chdir(local)

        result = run_remove(make_ctx(branch_or_path="feature-test"))

        assert result == 0
        assert not worktree_path.exists()

    def test_remove_worktree_by_path(
        self,
        git_repo_with_remote: tuple[Path, Path],
        worktree_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test removing worktree by absolute path."""
        local, _ = git_repo_with_remote

        worktree_path = worktree_dir / "feature-test"
        subprocess.run(
            ["git", "worktree", "add", str(worktree_path), "feature-test"],
            cwd=local,
            check=True,
            capture_output=True,
        )

        monkeypatch.chdir(local)

        result = run_remove(make_ctx(branch_or_path=str(worktree_path)))

        assert result == 0

    def test_remove_fails_for_dirty_worktree(
        self,
        git_repo_with_remote: tuple[Path, Path],
        worktree_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that remove fails for dirty worktree without --force."""
        local, _ = git_repo_with_remote

        worktree_path = worktree_dir / "feature-test"
        subprocess.run(
            ["git", "worktree", "add", str(worktree_path), "feature-test"],
            cwd=local,
            check=True,
            capture_output=True,
        )

        (worktree_path / "dirty.txt").write_text("dirty")

        monkeypatch.chdir(local)

        result = run_remove(make_ctx(branch_or_path="feature-test"))

        assert result == 1
        assert worktree_path.exists()

    def test_remove_force_dirty_worktree(
        self,
        git_repo_with_remote: tuple[Path, Path],
        worktree_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test force removing dirty worktree."""
        local, _ = git_repo_with_remote

        worktree_path = worktree_dir / "feature-test"
        subprocess.run(
            ["git", "worktree", "add", str(worktree_path), "feature-test"],
            cwd=local,
            check=True,
            capture_output=True,
        )

        (worktree_path / "dirty.txt").write_text("dirty")

        monkeypatch.chdir(local)

        result = run_remove(make_ctx(branch_or_path="feature-test", force=True))

        assert result == 0

    def test_remove_fails_for_nonexistent_worktree(
        self,
        git_repo_with_remote: tuple[Path, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that remove fails for nonexistent worktree."""
        local, _ = git_repo_with_remote
        monkeypatch.chdir(local)

        result = run_remove(make_ctx(branch_or_path="nonexistent"))

        assert result == 1


class TestPullCommand:
    """Integration tests for pull command (T049)."""

    def test_pull_updates_source_repository(
        self,
        git_repo_with_remote: tuple[Path, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test pulling updates to source repository."""
        local, bare = git_repo_with_remote

        tmp = Path(str(bare).replace("origin.git", "tmp_clone"))
        subprocess.run(
            ["git", "clone", f"file://{bare}", str(tmp)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp,
            check=True,
            capture_output=True,
        )
        (tmp / "upstream.txt").write_text("upstream change")
        subprocess.run(["git", "add", "."], cwd=tmp, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Upstream"], cwd=tmp, check=True, capture_output=True)
        subprocess.run(["git", "push"], cwd=tmp, check=True, capture_output=True)

        monkeypatch.chdir(local)

        result = run_pull(make_ctx())

        assert result == 0
        assert (local / "upstream.txt").exists()

    def test_pull_fails_when_not_on_main(
        self,
        git_repo_with_remote: tuple[Path, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that pull fails when not on main/master branch."""
        local, _ = git_repo_with_remote

        subprocess.run(
            ["git", "checkout", "feature-test"],
            cwd=local,
            check=True,
            capture_output=True,
        )

        monkeypatch.chdir(local)

        result = run_pull(make_ctx())

        assert result == 1

    def test_pull_fails_when_dirty(
        self,
        git_repo_with_remote: tuple[Path, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that pull fails when repository is dirty."""
        local, _ = git_repo_with_remote

        (local / "dirty.txt").write_text("dirty")

        monkeypatch.chdir(local)

        result = run_pull(make_ctx())

        assert result == 1

    def test_pull_from_worktree_updates_source(
        self,
        git_repo_with_remote: tuple[Path, Path],
        worktree_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test pulling from worktree updates source repository."""
        local, bare = git_repo_with_remote

        worktree_path = worktree_dir / "feature-test"
        subprocess.run(
            ["git", "worktree", "add", str(worktree_path), "feature-test"],
            cwd=local,
            check=True,
            capture_output=True,
        )

        tmp = Path(str(bare).replace("origin.git", "tmp_clone2"))
        subprocess.run(
            ["git", "clone", f"file://{bare}", str(tmp)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp,
            check=True,
            capture_output=True,
        )
        (tmp / "upstream2.txt").write_text("upstream2")
        subprocess.run(["git", "add", "."], cwd=tmp, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Upstream2"], cwd=tmp, check=True, capture_output=True)
        subprocess.run(["git", "push"], cwd=tmp, check=True, capture_output=True)

        monkeypatch.chdir(worktree_path)

        result = run_pull(make_ctx())

        assert result == 0
        assert (local / "upstream2.txt").exists()

    def test_pull_fails_outside_git_repo(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that pull fails when not in a git repository."""
        monkeypatch.chdir(tmp_path)

        result = run_pull(make_ctx())

        assert result == 1


class TestAddActionFailureHandling:
    """Integration tests for ADR-0010: per-rule criticality in add's action loop.

    Mirrors :class:`TestCloneActionFailureHandling` but for ``gww add`` —
    the action kind is ``after_add`` and the actions run inside the new
    worktree, not the source repo.
    """

    def _write_config(
        self, config_dir: Path, worktree_dir: Path, actions_block: str,
    ) -> None:
        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: ~/sources
default_worktrees: {worktree_dir}/norm_branch()

actions:
{actions_block}
""")

    def test_clean_run_prints_success_line_and_no_summary(
        self,
        git_repo_with_remote: tuple[Path, Path],
        config_dir: Path,
        worktree_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        local, _ = git_repo_with_remote
        self._write_config(
            config_dir, worktree_dir,
            "  - when: 'True'\n"
            "    after_add:\n"
            "      - command: 'true'\n",
        )
        monkeypatch.chdir(local)

        result = run_add(make_ctx(branch="feature-test"))

        assert result == 0
        captured = capsys.readouterr()
        assert str(worktree_dir / "feature-test") in captured.out
        assert "Action execution summary" not in captured.err

    def test_critical_rule_failure_exits_one_and_prints_summary(
        self,
        git_repo_with_remote: tuple[Path, Path],
        config_dir: Path,
        worktree_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        local, _ = git_repo_with_remote
        self._write_config(
            config_dir, worktree_dir,
            "  - when: 'True'\n"
            "    after_add:\n"
            "      - command: 'false'\n",
        )
        monkeypatch.chdir(local)

        result = run_add(make_ctx(branch="feature-test"))

        assert result == 1
        captured = capsys.readouterr()
        assert str(worktree_dir / "feature-test") not in captured.out
        assert "Action execution summary" in captured.err
        assert "Rule 0 (critical" in captured.err
        assert "Command failed" in captured.err

    def test_non_critical_rule_failure_exits_zero_but_prints_summary(
        self,
        git_repo_with_remote: tuple[Path, Path],
        config_dir: Path,
        worktree_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        local, _ = git_repo_with_remote
        self._write_config(
            config_dir, worktree_dir,
            "  - when: 'True'\n"
            "    critical: false\n"
            "    after_add:\n"
            "      - command: 'false'\n",
        )
        monkeypatch.chdir(local)

        result = run_add(make_ctx(branch="feature-test"))

        assert result == 0
        captured = capsys.readouterr()
        assert str(worktree_dir / "feature-test") not in captured.out
        assert "Action execution summary" in captured.err
        assert "Rule 0 (non-critical" in captured.err

    def test_matcher_failure_exits_two_with_no_actions_run(
        self,
        git_repo_with_remote: tuple[Path, Path],
        config_dir: Path,
        worktree_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        local, _ = git_repo_with_remote
        self._write_config(
            config_dir, worktree_dir,
            "  - when: 'undefined_variable'\n"
            "    after_add:\n"
            "      - command: 'true'\n",
        )
        monkeypatch.chdir(local)

        result = run_add(make_ctx(branch="feature-test"))

        assert result == 2
        captured = capsys.readouterr()
        assert "Config error" in captured.err
        # The worktree was created before the action loop ran.
        assert (worktree_dir / "feature-test").exists()
        # But the success line was suppressed.
        assert str(worktree_dir / "feature-test") not in captured.out