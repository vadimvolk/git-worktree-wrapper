"""Integration tests for migrate command end-to-end (T056)."""

import pytest
import subprocess
import os
from pathlib import Path

from gww.cli.commands.migrate import run_migrate


@pytest.fixture
def old_repos_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create directory with multiple git repositories for migration."""
    old_dir = tmp_path_factory.mktemp("old_repos")

    # Create first repo (simulating github repo)
    repo1 = old_dir / "project1"
    repo1.mkdir()
    subprocess.run(["git", "init"], cwd=repo1, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo1,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo1,
        check=True,
        capture_output=True,
    )
    (repo1 / "README.md").write_text("# Project 1")
    subprocess.run(["git", "add", "."], cwd=repo1, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo1, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/user/project1.git"],
        cwd=repo1,
        check=True,
        capture_output=True,
    )

    # Create second repo (simulating gitlab repo)
    repo2 = old_dir / "project2"
    repo2.mkdir()
    subprocess.run(["git", "init"], cwd=repo2, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo2,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo2,
        check=True,
        capture_output=True,
    )
    (repo2 / "README.md").write_text("# Project 2")
    subprocess.run(["git", "add", "."], cwd=repo2, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo2, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://gitlab.com/group/project2.git"],
        cwd=repo2,
        check=True,
        capture_output=True,
    )

    # Create repo without remote (should be skipped)
    repo3 = old_dir / "no_remote"
    repo3.mkdir()
    subprocess.run(["git", "init"], cwd=repo3, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo3,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo3,
        check=True,
        capture_output=True,
    )
    (repo3 / "README.md").write_text("# No Remote")
    subprocess.run(["git", "add", "."], cwd=repo3, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo3, check=True, capture_output=True)

    return old_dir


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
    """Create a temporary target directory for migrations."""
    return tmp_path_factory.mktemp("new_repos")


class TestMigrateCommand:
    """Integration tests for migrate command (T056)."""

    def test_migrate_dry_run_shows_plan(
        self,
        old_repos_dir: Path,
        config_dir: Path,
        target_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that dry run shows migration plan without making changes."""
        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/default/path(-2)/path(-1)
default_worktrees: {target_dir}/worktrees

sources:
  github:
    predicate: '"github" in host'
    sources: {target_dir}/github/path(-2)/path(-1)
  gitlab:
    predicate: '"gitlab" in host'
    sources: {target_dir}/gitlab/path(-2)/path(-1)
""")

        class Args:
            old_repos = str(old_repos_dir)
            dry_run = True
            move = False
            verbose = 0
            quiet = False

        result = run_migrate(Args())

        assert result == 0
        captured = capsys.readouterr()
        assert "Would migrate" in captured.out
        # Original repos should still exist
        assert (old_repos_dir / "project1").exists()
        assert (old_repos_dir / "project2").exists()

    def test_migrate_copies_repositories(
        self,
        old_repos_dir: Path,
        config_dir: Path,
        target_dir: Path,
    ) -> None:
        """Test that migrate copies repositories to new locations."""
        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/default/path(-2)/path(-1)
default_worktrees: {target_dir}/worktrees

sources:
  github:
    predicate: '"github" in host'
    sources: {target_dir}/github/path(-2)/path(-1)
  gitlab:
    predicate: '"gitlab" in host'
    sources: {target_dir}/gitlab/path(-2)/path(-1)
""")

        class Args:
            old_repos = str(old_repos_dir)
            dry_run = False
            move = False
            verbose = 0
            quiet = False

        result = run_migrate(Args())

        assert result == 0
        # Original repos should still exist (copy, not move)
        assert (old_repos_dir / "project1").exists()
        assert (old_repos_dir / "project2").exists()
        # New locations should exist
        assert (target_dir / "github" / "user" / "project1").exists()
        assert (target_dir / "gitlab" / "group" / "project2").exists()

    def test_migrate_moves_repositories(
        self,
        old_repos_dir: Path,
        config_dir: Path,
        target_dir: Path,
    ) -> None:
        """Test that migrate with --move moves repositories."""
        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/default/path(-2)/path(-1)
default_worktrees: {target_dir}/worktrees

sources:
  github:
    predicate: '"github" in host'
    sources: {target_dir}/github/path(-2)/path(-1)
  gitlab:
    predicate: '"gitlab" in host'
    sources: {target_dir}/gitlab/path(-2)/path(-1)
""")

        class Args:
            old_repos = str(old_repos_dir)
            dry_run = False
            move = True
            verbose = 0
            quiet = False

        result = run_migrate(Args())

        assert result == 0
        # Original repos should be moved (no longer exist)
        assert not (old_repos_dir / "project1").exists()
        assert not (old_repos_dir / "project2").exists()
        # New locations should exist
        assert (target_dir / "github" / "user" / "project1").exists()
        assert (target_dir / "gitlab" / "group" / "project2").exists()

    def test_migrate_skips_repos_without_remote(
        self,
        old_repos_dir: Path,
        config_dir: Path,
        target_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that migrate skips repositories without remote."""
        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/default/path(-1)
default_worktrees: {target_dir}/worktrees
""")

        class Args:
            old_repos = str(old_repos_dir)
            dry_run = False
            move = False
            verbose = 1  # Verbose to see skip messages
            quiet = False

        result = run_migrate(Args())

        assert result == 0
        captured = capsys.readouterr()
        # Repo without remote should be mentioned as skipped
        assert "no_remote" not in str(target_dir)

    def test_migrate_fails_for_nonexistent_path(
        self,
        config_dir: Path,
        target_dir: Path,
    ) -> None:
        """Test that migrate fails for nonexistent source path."""
        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/sources
default_worktrees: {target_dir}/worktrees
""")

        class Args:
            old_repos = "/nonexistent/path"
            dry_run = False
            move = False
            verbose = 0
            quiet = False

        result = run_migrate(Args())

        assert result == 1

    def test_migrate_fails_without_config(
        self,
        old_repos_dir: Path,
        config_dir: Path,
    ) -> None:
        """Test that migrate fails without config file."""
        # Don't create config

        class Args:
            old_repos = str(old_repos_dir)
            dry_run = False
            move = False
            verbose = 0
            quiet = False

        result = run_migrate(Args())

        assert result == 2

    def test_migrate_handles_empty_directory(
        self,
        tmp_path: Path,
        config_dir: Path,
        target_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that migrate handles empty directory gracefully."""
        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/sources
default_worktrees: {target_dir}/worktrees
""")

        class Args:
            old_repos = str(tmp_path)
            dry_run = False
            move = False
            verbose = 0
            quiet = False

        result = run_migrate(Args())

        assert result == 0
        captured = capsys.readouterr()
        assert "No repositories to migrate" in captured.out

    def test_migrate_verbose_output(
        self,
        old_repos_dir: Path,
        config_dir: Path,
        target_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test migrate with verbose output."""
        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/default/path(-2)/path(-1)
default_worktrees: {target_dir}/worktrees

sources:
  github:
    predicate: '"github" in host'
    sources: {target_dir}/github/path(-2)/path(-1)
""")

        class Args:
            old_repos = str(old_repos_dir)
            dry_run = False
            move = False
            verbose = 1
            quiet = False

        result = run_migrate(Args())

        assert result == 0
        captured = capsys.readouterr()
        assert "Scanning" in captured.err or "Copying" in captured.err
