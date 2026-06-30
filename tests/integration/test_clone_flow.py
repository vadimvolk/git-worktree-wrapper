"""Integration tests for clone command end-to-end in tests/integration/test_clone_flow.py."""

import pytest
import subprocess
from pathlib import Path

from gww.cli.commands.clone import run_clone
from tests.conftest import make_ctx


@pytest.fixture
def bare_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a bare git repository for cloning."""
    source = tmp_path_factory.mktemp("source")
    subprocess.run(["git", "init"], cwd=source, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=source,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=source,
        check=True,
        capture_output=True,
    )
    (source / "README.md").write_text("# Test")
    subprocess.run(["git", "add", "."], cwd=source, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=source, check=True, capture_output=True)

    bare = tmp_path_factory.mktemp("bare")
    bare_repo_path = bare / "test.git"
    subprocess.run(
        ["git", "clone", "--bare", str(source), str(bare_repo_path)],
        check=True,
        capture_output=True,
    )

    return bare_repo_path


@pytest.fixture
def target_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a temporary target directory for clones."""
    return tmp_path_factory.mktemp("clones")


class TestCloneCommand:
    """Integration tests for clone command (T026)."""

    def test_clone_repository_to_configured_location(
        self,
        bare_repo: Path,
        config_dir: Path,
        target_dir: Path,
    ) -> None:
        """Test cloning a repository to the configured location."""
        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/sources/path(-1)
default_worktrees: {target_dir}/worktrees
""")

        result = run_clone(make_ctx(uri=f"file://{bare_repo}"))

        assert result == 0
        expected_path = target_dir / "sources" / "test"
        assert expected_path.exists()
        assert (expected_path / ".git").exists()

    def test_clone_with_github_source_rule(
        self,
        bare_repo: Path,
        config_dir: Path,
        target_dir: Path,
    ) -> None:
        """Test cloning with a source rule matching the URI."""
        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/default/path(-1)
default_worktrees: {target_dir}/worktrees

sources:
  local:
    when: 'protocol() == "file"'
    sources: {target_dir}/local/path(-1)
""")

        result = run_clone(make_ctx(uri=f"file://{bare_repo}"))

        assert result == 0
        expected_path = target_dir / "local" / "test"
        assert expected_path.exists()

    def test_clone_fails_for_invalid_uri(
        self,
        config_dir: Path,
        target_dir: Path,
    ) -> None:
        """Test that clone fails for invalid URI."""
        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/sources
default_worktrees: {target_dir}/worktrees
""")

        result = run_clone(make_ctx(uri="not-a-valid-uri"))

        assert result == 1

    def test_clone_fails_when_destination_exists(
        self,
        bare_repo: Path,
        config_dir: Path,
        target_dir: Path,
    ) -> None:
        """Test that clone fails when destination already exists."""
        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/sources/path(-1)
default_worktrees: {target_dir}/worktrees
""")

        expected_path = target_dir / "sources" / "test"
        expected_path.mkdir(parents=True)

        result = run_clone(make_ctx(uri=f"file://{bare_repo}"))

        assert result == 1

    def test_clone_returns_config_error_when_no_config(
        self,
        bare_repo: Path,
        config_dir: Path,
    ) -> None:
        """Test that clone returns config error when no config file."""
        result = run_clone(make_ctx(uri=f"file://{bare_repo}"))

        assert result == 2

    def test_clone_with_verbose_output(
        self,
        bare_repo: Path,
        config_dir: Path,
        target_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test clone with verbose output."""
        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/sources/path(-1)
default_worktrees: {target_dir}/worktrees
""")

        result = run_clone(make_ctx(uri=f"file://{bare_repo}", verbose=1))

        assert result == 0
        captured = capsys.readouterr()
        assert "Cloning" in captured.err

    def test_clone_with_quiet_output(
        self,
        bare_repo: Path,
        config_dir: Path,
        target_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test clone with quiet output."""
        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/sources/path(-1)
default_worktrees: {target_dir}/worktrees
""")

        result = run_clone(make_ctx(uri=f"file://{bare_repo}", quiet=True))

        assert result == 0
        captured = capsys.readouterr()
        assert captured.out == ""


class TestCloneWithProjectActions:
    """Integration tests for clone with project actions."""

    def test_clone_executes_after_clone_actions(
        self,
        bare_repo: Path,
        config_dir: Path,
        target_dir: Path,
        tmp_path: Path,
    ) -> None:
        """Test that after_clone actions are executed after clone."""
        marker_file = tmp_path / "marker.txt"
        marker_file.write_text("marker content")

        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/sources/path(-1)
default_worktrees: {target_dir}/worktrees

actions:
  - when: 'True'
    after_clone:
      - copy: ["{marker_file}", "copied_marker.txt"]
""")

        result = run_clone(make_ctx(uri=f"file://{bare_repo}"))

        assert result == 0
        expected_path = target_dir / "sources" / "test"
        copied_file = expected_path / "copied_marker.txt"
        assert copied_file.exists()
        assert copied_file.read_text() == "marker content"


class TestCloneActionFailureHandling:
    """Integration tests for ADR-0010: per-rule criticality in clone's action loop.

    Verifies exit codes, success-line suppression, and grouped summary on stderr
    for the four documented outcomes: clean run, non-critical failure,
    critical failure, and matcher failure.
    """

    def _write_config(
        self, config_dir: Path, target_dir: Path, actions_block: str,
    ) -> None:
        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/sources/path(-1)
default_worktrees: {target_dir}/worktrees

actions:
{actions_block}
""")

    def test_clean_run_prints_success_line_and_no_summary(
        self,
        bare_repo: Path,
        config_dir: Path,
        target_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._write_config(
            config_dir, target_dir,
            "  - when: 'True'\n"
            "    after_clone:\n"
            "      - command: 'true'\n",
        )

        result = run_clone(make_ctx(uri=f"file://{bare_repo}"))

        assert result == 0
        captured = capsys.readouterr()
        expected_path = target_dir / "sources" / "test"
        assert str(expected_path) in captured.out
        assert "Action execution summary" not in captured.err

    def test_critical_rule_failure_exits_one_and_prints_summary(
        self,
        bare_repo: Path,
        config_dir: Path,
        target_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._write_config(
            config_dir, target_dir,
            "  - when: 'True'\n"
            "    after_clone:\n"
            "      - command: 'false'\n",
        )

        result = run_clone(make_ctx(uri=f"file://{bare_repo}"))

        assert result == 1
        captured = capsys.readouterr()
        expected_path = target_dir / "sources" / "test"
        assert str(expected_path) not in captured.out
        assert "Action execution summary" in captured.err
        assert "Rule 0 (critical" in captured.err
        assert "Command failed" in captured.err

    def test_non_critical_rule_failure_exits_zero_but_prints_summary(
        self,
        bare_repo: Path,
        config_dir: Path,
        target_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._write_config(
            config_dir, target_dir,
            "  - when: 'True'\n"
            "    critical: false\n"
            "    after_clone:\n"
            "      - command: 'false'\n",
        )

        result = run_clone(make_ctx(uri=f"file://{bare_repo}"))

        assert result == 0
        captured = capsys.readouterr()
        expected_path = target_dir / "sources" / "test"
        assert str(expected_path) not in captured.out
        assert "Action execution summary" in captured.err
        assert "Rule 0 (non-critical" in captured.err

    def test_critical_rule_aborts_remaining_actions(
        self,
        bare_repo: Path,
        config_dir: Path,
        target_dir: Path,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        marker = tmp_path / "marker.txt"
        marker.write_text("should not be copied")

        self._write_config(
            config_dir, target_dir,
            f"  - when: 'True'\n"
            f"    after_clone:\n"
            f"      - command: 'false'\n"
            f"      - copy: ['{marker}', 'should-not-copy.txt']\n",
        )

        result = run_clone(make_ctx(uri=f"file://{bare_repo}"))

        assert result == 1
        captured = capsys.readouterr()
        assert "Action execution summary" in captured.err
        # The copy after the failing command must NOT have run.
        expected_path = target_dir / "sources" / "test"
        assert not (expected_path / "should-not-copy.txt").exists()

    def test_matcher_failure_exits_two_with_no_actions_run(
        self,
        bare_repo: Path,
        config_dir: Path,
        target_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._write_config(
            config_dir, target_dir,
            "  - when: 'undefined_variable'\n"
            "    after_clone:\n"
            "      - command: 'true'\n",
        )

        result = run_clone(make_ctx(uri=f"file://{bare_repo}"))

        assert result == 2
        captured = capsys.readouterr()
        assert "Config error" in captured.err
        expected_path = target_dir / "sources" / "test"
        # Clone itself still succeeded; only the action loop bailed.
        assert expected_path.exists()
        # No success line either — we exited before reaching it.
        assert str(expected_path) not in captured.out