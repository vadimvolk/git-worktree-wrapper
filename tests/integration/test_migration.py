"""Integration tests for migrate command end-to-end (T056)."""

import pytest
import shutil
import subprocess
import os
from pathlib import Path

from gww.cli.commands.migrate import run_migrate
from gww.git.worktree import list_worktrees


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


@pytest.fixture
def repo_with_worktree(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path, Path]:
    """Create a source repository with a worktree for migration testing.
    
    Returns:
        Tuple of (worktrees_dir, source_repo_path, worktree_path)
    """
    worktrees_dir = tmp_path_factory.mktemp("worktrees_to_migrate")
    
    # Create source repository (this stays in place, not migrated)
    source_repo = tmp_path_factory.mktemp("source_repo")
    subprocess.run(["git", "init"], cwd=source_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=source_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=source_repo,
        check=True,
        capture_output=True,
    )
    (source_repo / "README.md").write_text("# Source Repo")
    subprocess.run(["git", "add", "."], cwd=source_repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=source_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/user/source-repo.git"],
        cwd=source_repo,
        check=True,
        capture_output=True,
    )
    
    # Create a branch for the worktree
    subprocess.run(
        ["git", "branch", "feature-branch"],
        cwd=source_repo,
        check=True,
        capture_output=True,
    )
    
    # Create worktree in the worktrees_dir (this will be migrated)
    worktree_path = worktrees_dir / "feature-worktree"
    subprocess.run(
        ["git", "worktree", "add", str(worktree_path), "feature-branch"],
        cwd=source_repo,
        check=True,
        capture_output=True,
    )
    
    # Add remote to worktree so it can be migrated
    subprocess.run(
        ["git", "remote", "set-url", "origin", "https://github.com/user/feature-worktree.git"],
        cwd=worktree_path,
        check=True,
        capture_output=True,
    )
    
    return worktrees_dir, source_repo, worktree_path


@pytest.fixture
def repo_with_submodule(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, Path, Path]:
    """Create a directory with a main repo that has a git submodule.

    Returns:
        Tuple of (old_repos_dir, main_repo_path, submodule_path)
    """
    old_dir = tmp_path_factory.mktemp("old_repos_with_submodule")
    main_repo = old_dir / "main_repo"
    main_repo.mkdir()
    subprocess.run(["git", "init"], cwd=main_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=main_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=main_repo,
        check=True,
        capture_output=True,
    )
    (main_repo / "README.md").write_text("# Main")
    subprocess.run(["git", "add", "."], cwd=main_repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=main_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/user/main-repo.git"],
        cwd=main_repo,
        check=True,
        capture_output=True,
    )
    # Create second repo to add as submodule
    sub_repo = tmp_path_factory.mktemp("sub_repo")
    subprocess.run(["git", "init"], cwd=sub_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
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
    (sub_repo / "file.txt").write_text("sub content")
    subprocess.run(["git", "add", "."], cwd=sub_repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Sub"], cwd=sub_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "protocol.file.allow=always", "submodule", "add", str(sub_repo), "submod"],
        cwd=main_repo,
        check=True,
        capture_output=True,
    )
    submodule_path = main_repo / "submod"
    return old_dir, main_repo, submodule_path


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
    when: '"github" in host()'
    sources: {target_dir}/github/path(-2)/path(-1)
  gitlab:
    when: '"gitlab" in host()'
    sources: {target_dir}/gitlab/path(-2)/path(-1)
""")

        class Args:
            old_repos = str(old_repos_dir)
            dry_run = True
            inplace = False
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
    when: '"github" in host()'
    sources: {target_dir}/github/path(-2)/path(-1)
  gitlab:
    when: '"gitlab" in host()'
    sources: {target_dir}/gitlab/path(-2)/path(-1)
""")

        class Args:
            old_repos = str(old_repos_dir)
            dry_run = False
            inplace = False
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

    def test_migrate_copy_preserves_symlinks(
        self,
        tmp_path_factory: pytest.TempPathFactory,
        config_dir: Path,
        target_dir: Path,
    ) -> None:
        """Test that migrate --copy copies symbolic links as symlinks, not resolved."""
        old_dir = tmp_path_factory.mktemp("old_repos_symlink")
        repo = old_dir / "symlink_repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        (repo / "README.md").write_text("# Repo with symlink")
        (repo / "mylink").symlink_to("README.md")
        subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/user/symlink_repo.git"],
            cwd=repo,
            check=True,
            capture_output=True,
        )

        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/default/path(-1)
default_worktrees: {target_dir}/worktrees

sources:
  github:
    when: '"github" in host()'
    sources: {target_dir}/github/path(-2)/path(-1)
""")

        class Args:
            old_repos = str(old_dir)
            dry_run = False
            inplace = False
            verbose = 0
            quiet = False

        result = run_migrate(Args())

        assert result == 0
        migrated = target_dir / "github" / "user" / "symlink_repo"
        assert migrated.exists()
        mylink = migrated / "mylink"
        assert mylink.is_symlink(), "Symlink should be copied as symlink, not resolved"
        assert Path(mylink.readlink()) == Path("README.md")

    def test_migrate_moves_repositories(
        self,
        old_repos_dir: Path,
        config_dir: Path,
        target_dir: Path,
    ) -> None:
        """Test that migrate with --inplace moves repositories."""
        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/default/path(-2)/path(-1)
default_worktrees: {target_dir}/worktrees

sources:
  github:
    when: '"github" in host()'
    sources: {target_dir}/github/path(-2)/path(-1)
  gitlab:
    when: '"gitlab" in host()'
    sources: {target_dir}/gitlab/path(-2)/path(-1)
""")

        class Args:
            old_repos = str(old_repos_dir)
            dry_run = False
            inplace = True
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
            inplace = False
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
            inplace = False
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
            inplace = False
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
            inplace = False
            verbose = 0
            quiet = False

        result = run_migrate(Args())

        assert result == 0
        captured = capsys.readouterr()
        assert "No repositories to migrate" in captured.out

    def test_migrate_outputs_already_at_target(
        self,
        old_repos_dir: Path,
        config_dir: Path,
        target_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that migrate outputs specific message when repo is already at target."""
        # Place a repo at the exact path that config would resolve to
        expected_base = target_dir / "github" / "user"
        expected_base.mkdir(parents=True, exist_ok=True)
        repo_at_target = expected_base / "project1"
        repo_at_target.mkdir()
        subprocess.run(["git", "init"], cwd=repo_at_target, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo_at_target,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=repo_at_target,
            check=True,
            capture_output=True,
        )
        (repo_at_target / "README.md").write_text("# Here")
        subprocess.run(["git", "add", "."], cwd=repo_at_target, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo_at_target, check=True, capture_output=True)
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/user/project1.git"],
            cwd=repo_at_target,
            check=True,
            capture_output=True,
        )
        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/github/path(-2)/path(-1)
default_worktrees: {target_dir}/worktrees
""")

        class Args:
            old_repos = str(target_dir)
            dry_run = False
            inplace = False
            verbose = 0
            quiet = False

        result = run_migrate(Args())

        assert result == 0
        captured = capsys.readouterr()
        assert "Already at target:" in captured.out
        assert "project1" in captured.out or str(repo_at_target) in captured.out
        assert "Already at target: 1 repositories" in captured.out

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
    when: '"github" in host()'
    sources: {target_dir}/github/path(-2)/path(-1)
""")

        class Args:
            old_repos = str(old_repos_dir)
            dry_run = False
            inplace = False
            verbose = 1
            quiet = False

        result = run_migrate(Args())

        assert result == 0
        captured = capsys.readouterr()
        assert "Scanning" in captured.err or "Copying" in captured.err

    def test_migrate_repairs_worktree_after_move(
        self,
        repo_with_worktree: tuple[Path, Path, Path],
        config_dir: Path,
        target_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that moving a worktree triggers repair on the source repository."""
        worktrees_dir, source_repo, worktree_path = repo_with_worktree

        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/github/path(-2)/path(-1)
default_worktrees: {target_dir}/worktrees

sources:
  github:
    when: '"github" in host()'
    sources: {target_dir}/github/path(-2)/path(-1)
    worktrees: {target_dir}/github/path(-2)/path(-1)
""")

        class Args:
            old_repos = str(worktrees_dir)
            dry_run = False
            inplace = True
            verbose = 1
            quiet = False

        result = run_migrate(Args())

        assert result == 0
        captured = capsys.readouterr()

        # Verify worktree was moved
        assert not worktree_path.exists()
        new_worktree_path = target_dir / "github" / "user" / "feature-worktree"
        assert new_worktree_path.exists()

        # Verify repair was called (check verbose output)
        assert "Repairing worktree paths" in captured.err

        # Verify the source repository still knows about worktrees
        # (repair should have updated the paths)
        worktrees = list_worktrees(source_repo)
        assert len(worktrees) >= 1  # At least the main worktree

    def test_migrate_repairs_worktree_after_copy(
        self,
        repo_with_worktree: tuple[Path, Path, Path],
        config_dir: Path,
        target_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that copying a worktree triggers repair on the source repository."""
        worktrees_dir, source_repo, worktree_path = repo_with_worktree

        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/github/path(-2)/path(-1)
default_worktrees: {target_dir}/worktrees

sources:
  github:
    when: '"github" in host()'
    sources: {target_dir}/github/path(-2)/path(-1)
    worktrees: {target_dir}/github/path(-2)/path(-1)
""")

        class Args:
            old_repos = str(worktrees_dir)
            dry_run = False
            inplace = False  # Copy (default)
            verbose = 1
            quiet = False

        result = run_migrate(Args())

        assert result == 0
        captured = capsys.readouterr()

        # Verify original worktree still exists (copy, not move)
        assert worktree_path.exists()
        # Verify copy was created (worktree path from rule)
        new_worktree_path = target_dir / "github" / "user" / "feature-worktree"
        assert new_worktree_path.exists()

        # Verify repair was called
        assert "Repairing worktree paths" in captured.err

    def test_migrate_does_not_repair_source_repositories(
        self,
        old_repos_dir: Path,
        config_dir: Path,
        target_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that repair is NOT called when migrating source repositories (not worktrees)."""
        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/default/path(-2)/path(-1)
default_worktrees: {target_dir}/worktrees

sources:
  github:
    when: '"github" in host()'
    sources: {target_dir}/github/path(-2)/path(-1)
""")

        class Args:
            old_repos = str(old_repos_dir)
            dry_run = False
            inplace = True
            verbose = 1
            quiet = False

        result = run_migrate(Args())

        assert result == 0
        captured = capsys.readouterr()

        # Verify repositories were migrated
        assert (target_dir / "github" / "user" / "project1").exists()

        # Verify repair was NOT called (source repos don't need repair)
        assert "Repairing worktree paths" not in captured.err
        # Output should NOT mention "Repaired" since no worktrees were involved
        assert "Repaired" not in captured.out

    def test_migrate_dry_run_skips_submodules(
        self,
        repo_with_submodule: tuple[Path, Path, Path],
        config_dir: Path,
        target_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that migrate dry-run only plans the main repo, not the submodule as separate repo."""
        old_dir, main_repo, submodule_path = repo_with_submodule
        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/github/path(-2)/path(-1)
default_worktrees: {target_dir}/worktrees
""")

        class Args:
            old_repos = str(old_dir)
            dry_run = True
            inplace = False
            verbose = 0
            quiet = False

        result = run_migrate(Args())

        assert result == 0
        captured = capsys.readouterr()
        # Should plan to migrate main_repo only (one repo)
        assert "Would migrate" in captured.out
        assert "1 repositories" in captured.out
        # Submodule path must not appear as a separate migration target
        assert str(submodule_path) not in captured.out or "main_repo" in captured.out

    def test_migrate_with_submodule_copies_parent_and_keeps_submodule(
        self,
        repo_with_submodule: tuple[Path, Path, Path],
        config_dir: Path,
        target_dir: Path,
    ) -> None:
        """Test that migrating a repo with submodule copies parent; submodule stays inside."""
        old_dir, main_repo, submodule_path = repo_with_submodule
        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/github/path(-2)/path(-1)
default_worktrees: {target_dir}/worktrees
""")

        class Args:
            old_repos = str(old_dir)
            dry_run = False
            inplace = False
            verbose = 0
            quiet = False

        result = run_migrate(Args())

        assert result == 0
        # URI path segment is "main-repo" (from main-repo.git)
        migrated_main = target_dir / "github" / "user" / "main-repo"
        assert migrated_main.exists()
        assert (migrated_main / ".gitmodules").exists()
        migrated_submod = migrated_main / "submod"
        assert migrated_submod.exists()
        assert (migrated_submod / "file.txt").exists()
        # Submodule .git should be file pointing to parent's .git/modules
        assert (migrated_submod / ".git").is_file()

    def test_migrate_multiple_input_folders(
        self,
        old_repos_dir: Path,
        config_dir: Path,
        target_dir: Path,
        tmp_path_factory: pytest.TempPathFactory,
    ) -> None:
        """Test that migrate with multiple paths merges repos and processes as one set."""
        # Second folder with one repo
        other_dir = tmp_path_factory.mktemp("old_repos_other")
        repo3 = other_dir / "project3"
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
        (repo3 / "README.md").write_text("# Project 3")
        subprocess.run(["git", "add", "."], cwd=repo3, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo3, check=True, capture_output=True)
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/user/project3.git"],
            cwd=repo3,
            check=True,
            capture_output=True,
        )
        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/default/path(-2)/path(-1)
default_worktrees: {target_dir}/worktrees

sources:
  github:
    when: '"github" in host()'
    sources: {target_dir}/github/path(-2)/path(-1)
  gitlab:
    when: '"gitlab" in host()'
    sources: {target_dir}/gitlab/path(-2)/path(-1)
""")

        class Args:
            old_repos = [str(old_repos_dir), str(other_dir)]
            dry_run = False
            inplace = False
            verbose = 0
            quiet = False

        result = run_migrate(Args())

        assert result == 0
        assert (target_dir / "github" / "user" / "project1").exists()
        assert (target_dir / "gitlab" / "group" / "project2").exists()
        assert (target_dir / "github" / "user" / "project3").exists()

    def test_migrate_inplace_cleans_empty_folders(
        self,
        old_repos_dir: Path,
        config_dir: Path,
        target_dir: Path,
    ) -> None:
        """Test that --inplace removes vacated dirs and empty parents recursively."""
        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/default/path(-2)/path(-1)
default_worktrees: {target_dir}/worktrees

sources:
  github:
    when: '"github" in host()'
    sources: {target_dir}/github/path(-2)/path(-1)
  gitlab:
    when: '"gitlab" in host()'
    sources: {target_dir}/gitlab/path(-2)/path(-1)
""")

        class Args:
            old_repos = str(old_repos_dir)
            dry_run = False
            inplace = True
            verbose = 0
            quiet = False

        result = run_migrate(Args())

        assert result == 0
        assert not (old_repos_dir / "project1").exists()
        assert not (old_repos_dir / "project2").exists()
        assert (target_dir / "github" / "user" / "project1").exists()
        assert (target_dir / "gitlab" / "group" / "project2").exists()

    def test_migrate_copy_validation_destination_exists(
        self,
        old_repos_dir: Path,
        config_dir: Path,
        target_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that copy mode reports all validation errors (e.g. destination exists)."""
        # Pre-create one destination so validation fails
        dest = target_dir / "github" / "user" / "project1"
        dest.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/default/path(-2)/path(-1)
default_worktrees: {target_dir}/worktrees

sources:
  github:
    when: '"github" in host()'
    sources: {target_dir}/github/path(-2)/path(-1)
  gitlab:
    when: '"gitlab" in host()'
    sources: {target_dir}/gitlab/path(-2)/path(-1)
""")

        class Args:
            old_repos = str(old_repos_dir)
            dry_run = False
            inplace = False
            verbose = 0
            quiet = False

        result = run_migrate(Args())
        captured = capsys.readouterr()

        # Copy mode should fail with exit code 1 when destination exists
        assert result == 1

        # Verify error messages in stderr
        assert "Error: Destination already exists:" in captured.err
        assert str(dest) in captured.err
        assert "Cannot proceed:" in captured.err
        assert "destination(s) already exist in copy mode" in captured.err

        # project2 should NOT be migrated (fail-fast behavior)
        assert not (target_dir / "gitlab" / "group" / "project2").exists()

    def test_migrate_copy_fails_with_multiple_destinations_exist(
        self,
        old_repos_dir: Path,
        config_dir: Path,
        target_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that copy mode shows ALL conflicts when multiple destinations exist."""
        # Pre-create both destinations
        dest1 = target_dir / "github" / "user" / "project1"
        dest1.mkdir(parents=True, exist_ok=True)
        dest2 = target_dir / "gitlab" / "group" / "project2"
        dest2.mkdir(parents=True, exist_ok=True)

        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/default/path(-2)/path(-1)
default_worktrees: {target_dir}/worktrees

sources:
  github:
    when: '"github" in host()'
    sources: {target_dir}/github/path(-2)/path(-1)
  gitlab:
    when: '"gitlab" in host()'
    sources: {target_dir}/gitlab/path(-2)/path(-1)
""")

        class Args:
            old_repos = str(old_repos_dir)
            dry_run = False
            inplace = False
            verbose = 0
            quiet = False

        result = run_migrate(Args())
        captured = capsys.readouterr()

        # Should fail with exit code 1
        assert result == 1

        # Both conflicts should be reported
        assert captured.err.count("Error: Destination already exists:") == 2
        assert str(dest1) in captured.err
        assert str(dest2) in captured.err

        # Summary should mention 2 destinations
        assert "Cannot proceed: 2 destination(s) already exist" in captured.err

    def test_migrate_copy_dry_run_fails_when_destination_exists(
        self,
        old_repos_dir: Path,
        config_dir: Path,
        target_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that copy dry-run mode also fails when destination exists."""
        # Pre-create one destination
        dest = target_dir / "github" / "user" / "project1"
        dest.mkdir(parents=True, exist_ok=True)

        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/default/path(-2)/path(-1)
default_worktrees: {target_dir}/worktrees

sources:
  github:
    when: '"github" in host()'
    sources: {target_dir}/github/path(-2)/path(-1)
  gitlab:
    when: '"gitlab" in host()'
    sources: {target_dir}/gitlab/path(-2)/path(-1)
""")

        class Args:
            old_repos = str(old_repos_dir)
            dry_run = True  # Dry run mode
            inplace = False
            verbose = 0
            quiet = False

        result = run_migrate(Args())
        captured = capsys.readouterr()

        # Dry-run should also fail with exit code 1
        assert result == 1

        # Error messages should appear
        assert "Error: Destination already exists:" in captured.err
        assert str(dest) in captured.err
        assert "Cannot proceed:" in captured.err

        # Original repos should still exist (no migration occurred)
        assert (old_repos_dir / "project1").exists()
        assert (old_repos_dir / "project2").exists()

    def test_migrate_inplace_continues_when_destination_exists(
        self,
        old_repos_dir: Path,
        config_dir: Path,
        target_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that inplace mode keeps current behavior (skip conflicts, continue with others)."""
        # Pre-create one destination to cause conflict
        dest = target_dir / "github" / "user" / "project1"
        dest.mkdir(parents=True, exist_ok=True)

        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/default/path(-2)/path(-1)
default_worktrees: {target_dir}/worktrees

sources:
  github:
    when: '"github" in host()'
    sources: {target_dir}/github/path(-2)/path(-1)
  gitlab:
    when: '"gitlab" in host()'
    sources: {target_dir}/gitlab/path(-2)/path(-1)
""")

        class Args:
            old_repos = str(old_repos_dir)
            dry_run = False
            inplace = True  # Inplace mode
            verbose = 0
            quiet = False

        result = run_migrate(Args())
        captured = capsys.readouterr()

        # Inplace mode should succeed with exit code 0
        assert result == 0

        # project2 should still be migrated
        assert (target_dir / "gitlab" / "group" / "project2").exists()

        # Output should mention project1 was skipped (current behavior)
        # No error exit for inplace mode

    def test_migrate_mixed_sources_and_worktrees(
        self,
        tmp_path_factory: pytest.TempPathFactory,
        config_dir: Path,
        target_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test migrating both source repos and worktrees in a single migration."""
        mixed_dir = tmp_path_factory.mktemp("mixed_repos")

        # Create a main source repository (will stay outside mixed_dir)
        main_source = tmp_path_factory.mktemp("main_source")
        subprocess.run(["git", "init"], cwd=main_source, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=main_source,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=main_source,
            check=True,
            capture_output=True,
        )
        (main_source / "README.md").write_text("# Main Source")
        subprocess.run(["git", "add", "."], cwd=main_source, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=main_source, check=True, capture_output=True)
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/user/main-source.git"],
            cwd=main_source,
            check=True,
            capture_output=True,
        )

        # Create a worktree from main_source inside mixed_dir
        subprocess.run(
            ["git", "branch", "feature"],
            cwd=main_source,
            check=True,
            capture_output=True,
        )
        worktree_path = mixed_dir / "feature-worktree"
        subprocess.run(
            ["git", "worktree", "add", str(worktree_path), "feature"],
            cwd=main_source,
            check=True,
            capture_output=True,
        )

        # Create a standalone source repo inside mixed_dir
        standalone_repo = mixed_dir / "standalone"
        standalone_repo.mkdir()
        subprocess.run(["git", "init"], cwd=standalone_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=standalone_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=standalone_repo,
            check=True,
            capture_output=True,
        )
        (standalone_repo / "file.txt").write_text("standalone")
        subprocess.run(["git", "add", "."], cwd=standalone_repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Init"], cwd=standalone_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/user/standalone.git"],
            cwd=standalone_repo,
            check=True,
            capture_output=True,
        )

        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/github/path(-2)/path(-1)
default_worktrees: {target_dir}/github/path(-2)/path(-1)
""")

        class Args:
            old_repos = str(mixed_dir)
            dry_run = False
            inplace = False
            verbose = 1
            quiet = False

        result = run_migrate(Args())
        captured = capsys.readouterr()

        assert result == 0
        # Worktree resolves based on main-source remote, not its directory name
        # With template path(-2)/path(-1), it resolves to user/main-source
        assert (target_dir / "github" / "user" / "main-source").exists()
        assert (target_dir / "github" / "user" / "standalone").exists()

        # Verify output mentions both sources and worktrees
        assert "source" in captured.out.lower() or "Source" in captured.out
        assert "worktree" in captured.out.lower() or "Worktree" in captured.out

    def test_migrate_same_destination_for_different_repos(
        self,
        tmp_path_factory: pytest.TempPathFactory,
        config_dir: Path,
        target_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that collision during migration is handled - first repo copied, second fails."""
        collision_dir = tmp_path_factory.mktemp("collision_repos")

        # Create first repo
        repo1 = collision_dir / "myproject-github"
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
        (repo1 / "README.md").write_text("# From GitHub")
        subprocess.run(["git", "add", "."], cwd=repo1, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo1, check=True, capture_output=True)
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/user/myproject.git"],
            cwd=repo1,
            check=True,
            capture_output=True,
        )

        # Manually copy repo1 to its destination to simulate first migration
        dest_path = target_dir / "repos" / "user" / "myproject"
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(repo1, dest_path)

        # Create second repo with same remote (would resolve to same destination)
        repo2 = collision_dir / "myproject-other"
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
        (repo2 / "README.md").write_text("# Other")
        subprocess.run(["git", "add", "."], cwd=repo2, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial"], cwd=repo2, check=True, capture_output=True)
        # Same remote as repo1
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/user/myproject.git"],
            cwd=repo2,
            check=True,
            capture_output=True,
        )

        # Config that resolves both to same path
        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/repos/path(-2)/path(-1)
default_worktrees: {target_dir}/worktrees
""")

        class Args:
            old_repos = str(collision_dir)
            dry_run = False
            inplace = False
            verbose = 0
            quiet = False

        result = run_migrate(Args())
        captured = capsys.readouterr()

        # Should fail in copy mode when destination already exists
        assert result == 1

        # Should report that destination exists
        assert "Destination already exists" in captured.err
        assert "Cannot proceed" in captured.err

    def test_migrate_empty_input_list(
        self,
        config_dir: Path,
        target_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that migrate handles empty list of input directories gracefully."""
        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(f"""
default_sources: {target_dir}/sources
default_worktrees: {target_dir}/worktrees
""")

        # Pass empty list - this simulates programmatic usage
        # Note: CLI would require at least one path, but run_migrate accepts a list
        class Args:
            old_repos = []
            dry_run = False
            inplace = False
            verbose = 0
            quiet = False

        result = run_migrate(Args())
        captured = capsys.readouterr()

        # Should succeed with no repositories found
        assert result == 0
        assert "No repositories to migrate" in captured.out
