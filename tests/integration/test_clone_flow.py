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
      - abs_copy: ["{marker_file}", "copied_marker.txt"]
""")

        result = run_clone(make_ctx(uri=f"file://{bare_repo}"))

        assert result == 0
        expected_path = target_dir / "sources" / "test"
        copied_file = expected_path / "copied_marker.txt"
        assert copied_file.exists()
        assert copied_file.read_text() == "marker content"