"""Integration tests for clone command end-to-end in tests/integration/test_clone_flow.py."""

import pytest
import subprocess
import os
from pathlib import Path
from unittest.mock import patch

from gww.cli.commands.clone import run_clone
from gww.config.loader import save_config
from gww.utils.xdg import get_config_path


@pytest.fixture
def bare_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a bare git repository for cloning."""
    # Create a temp repo first
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
    
    # Create bare clone
    bare = tmp_path_factory.mktemp("bare")
    bare_repo_path = bare / "test.git"
    subprocess.run(
        ["git", "clone", "--bare", str(source), str(bare_repo_path)],
        check=True,
        capture_output=True,
    )
    
    return bare_repo_path


@pytest.fixture
def config_dir(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary config directory and patch get_config_path."""
    config_path = tmp_path_factory.mktemp("config")
    test_config_file = config_path / "gww" / "config.yml"
    
    # Patch get_config_path in all modules that import it
    monkeypatch.setattr("gww.utils.xdg.get_config_path", lambda appname="gww": test_config_file)
    monkeypatch.setattr("gww.config.loader.get_config_path", lambda: test_config_file)
    
    return config_path


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
        # Create config
        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/sources/path(-1)
default_worktrees: {target_dir}/worktrees
""")

        # Create mock args
        class Args:
            uri = f"file://{bare_repo}"
            verbose = 0
            quiet = False

        # Run clone
        result = run_clone(Args())

        assert result == 0
        # Verify repository was cloned
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
        # Create config with source rule
        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/default/path(-1)
default_worktrees: {target_dir}/worktrees

sources:
  local:
    predicate: 'protocol == "file"'
    sources: {target_dir}/local/path(-1)
""")

        class Args:
            uri = f"file://{bare_repo}"
            verbose = 0
            quiet = False

        result = run_clone(Args())

        assert result == 0
        # Should use the local rule, not default
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

        class Args:
            uri = "not-a-valid-uri"
            verbose = 0
            quiet = False

        result = run_clone(Args())

        assert result == 1  # Error exit code

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

        # Pre-create the destination
        expected_path = target_dir / "sources" / "test"
        expected_path.mkdir(parents=True)

        class Args:
            uri = f"file://{bare_repo}"
            verbose = 0
            quiet = False

        result = run_clone(Args())

        assert result == 1  # Error because destination exists

    def test_clone_returns_config_error_when_no_config(
        self,
        bare_repo: Path,
        config_dir: Path,
    ) -> None:
        """Test that clone returns config error when no config file."""
        # Don't create config file

        class Args:
            uri = f"file://{bare_repo}"
            verbose = 0
            quiet = False

        result = run_clone(Args())

        assert result == 2  # Config error exit code

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

        class Args:
            uri = f"file://{bare_repo}"
            verbose = 1
            quiet = False

        result = run_clone(Args())

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

        class Args:
            uri = f"file://{bare_repo}"
            verbose = 0
            quiet = True

        result = run_clone(Args())

        assert result == 0
        captured = capsys.readouterr()
        # stdout should be empty with quiet
        assert captured.out == ""


class TestCloneWithProjectActions:
    """Integration tests for clone with project actions."""

    def test_clone_executes_source_actions(
        self,
        bare_repo: Path,
        config_dir: Path,
        target_dir: Path,
        tmp_path: Path,
    ) -> None:
        """Test that source actions are executed after clone."""
        # Create a marker file to copy
        marker_file = tmp_path / "marker.txt"
        marker_file.write_text("marker content")

        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/sources/path(-1)
default_worktrees: {target_dir}/worktrees

projects:
  - predicate: 'True'
    source_actions:
      - abs_copy: ["{marker_file}", "copied_marker.txt"]
""")

        class Args:
            uri = f"file://{bare_repo}"
            verbose = 0
            quiet = False

        result = run_clone(Args())

        assert result == 0
        # Verify action was executed
        expected_path = target_dir / "sources" / "test"
        copied_file = expected_path / "copied_marker.txt"
        assert copied_file.exists()
        assert copied_file.read_text() == "marker content"
