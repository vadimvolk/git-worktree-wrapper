"""Unit tests for gww.migration.planner.plan_migration."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable

import pytest

from gww.config.validator import Config
from gww.migration import (
    Blocked,
    Migration,
    MigrationPlan,
    Skip,
    plan_migration,
)


def _init_repo(path: Path, remote: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t"], cwd=path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "T"], cwd=path, check=True, capture_output=True
    )
    (path / "README.md").write_text("# r")
    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "i"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", remote],
        cwd=path,
        check=True,
        capture_output=True,
    )


def _config(target_dir: Path) -> Config:
    """A config that maps everything to ``<target_dir>/<owner>/<name>``."""
    return Config(
        default_sources=f"{target_dir}/path(-2)/path(-1)",
        default_worktrees=f"{target_dir}/path(-2)/path(-1)/norm_branch()",
        sources={},
        actions=[],
    )


class TestPlanMigrationSourceRepos:
    """plan_migration handles source repos: ok / no remote / bad URI / already at target."""

    def test_returns_migration_with_plan_for_repo_with_remote(self, tmp_path: Path) -> None:
        old_dir = tmp_path / "old"
        new_dir = tmp_path / "new"
        repo = old_dir / "gh" / "user" / "repo1"
        _init_repo(repo, "https://github.com/user/repo1.git")

        result = plan_migration([repo], _config(new_dir), inplace=False)

        assert isinstance(result, Migration)
        assert len(result.plans) == 1
        plan = result.plans[0]
        assert plan.old_path == repo
        # default_sources uses path(-2)/path(-1): for
        # https://github.com/user/repo1.git that resolves to <new>/user/repo1.
        assert plan.new_path == new_dir / "user" / "repo1"
        assert plan.is_worktree is False
        assert result.info_skips == []

    def test_returns_skip_for_repo_without_remote(self, tmp_path: Path) -> None:
        repo = tmp_path / "no_remote_repo"
        _init_repo(repo, "")
        subprocess.run(
            ["git", "remote", "remove", "origin"],
            cwd=repo,
            check=False,
            capture_output=True,
        )

        result = plan_migration([repo], _config(tmp_path / "new"), inplace=False)

        assert isinstance(result, Migration)
        assert result.plans == []
        assert len(result.info_skips) == 1
        assert result.info_skips[0].reason == "no remote origin configured"

    def test_returns_skip_for_already_at_target(self, tmp_path: Path) -> None:
        new_dir = tmp_path / "new"
        # Place a repo where the config will resolve it to.
        # We use the "default" template path(-2)/path(-1), so the URI
        # https://github.com/user/repo1 resolves to .../user/repo1.
        repo = new_dir / "github.com" / "user" / "repo1"
        # macOS uses backslashes for path.resolve() — fall back to a relative
        # form by using the actual path the planner will compare against.
        _init_repo(repo, "https://github.com/user/repo1.git")

        # Override the target to match where we put the repo.
        cfg = Config(
            default_sources=str(repo),
            default_worktrees=str(repo / "wt"),
            sources={},
            actions=[],
        )

        result = plan_migration([repo], cfg, inplace=False)

        assert isinstance(result, Migration)
        assert result.plans == []
        assert repo.resolve() in result.already_at_target


class TestPlanMigrationCopyModeBlocking:
    """In copy mode, a destination-exists conflict produces a Blocked result."""

    def test_returns_blocked_when_destination_exists(self, tmp_path: Path) -> None:
        old_dir = tmp_path / "old"
        new_dir = tmp_path / "new"
        repo = old_dir / "gh" / "user" / "repo1"
        _init_repo(repo, "https://github.com/user/repo1.git")

        # Pre-create the resolved destination so it exists.
        expected = new_dir / "github.com" / "user" / "repo1"
        # We don't know exact path - match what the config produces. Let's
        # just check by URI: the planner will resolve based on path(-2)/path(-1)
        # which yields .../user/repo1.
        config = Config(
            default_sources=f"{new_dir}/path(-2)/path(-1)",
            default_worktrees=f"{new_dir}/wt",
            sources={},
            actions=[],
        )

        # Create the expected destination directory so the planner sees it as taken.
        # Find what it will be first.
        from gww.config.resolver import resolve_source_path
        from gww.utils.uri import parse_uri
        uri = parse_uri("https://github.com/user/repo1.git")
        expected = resolve_source_path(config, uri, {})
        expected.mkdir(parents=True)

        result = plan_migration([repo], config, inplace=False)

        assert isinstance(result, Blocked)
        assert expected.resolve() in [p.resolve() for p in result.destinations]

    def test_inplace_mode_treats_destination_exists_as_skip(self, tmp_path: Path) -> None:
        old_dir = tmp_path / "old"
        new_dir = tmp_path / "new"
        repo = old_dir / "gh" / "user" / "repo1"
        _init_repo(repo, "https://github.com/user/repo1.git")

        from gww.config.resolver import resolve_source_path
        from gww.utils.uri import parse_uri
        config = Config(
            default_sources=f"{new_dir}/path(-2)/path(-1)",
            default_worktrees=f"{new_dir}/wt",
            sources={},
            actions=[],
        )
        uri = parse_uri("https://github.com/user/repo1.git")
        expected = resolve_source_path(config, uri, {})
        expected.mkdir(parents=True)

        result = plan_migration([repo], config, inplace=True)

        assert isinstance(result, Migration)
        assert result.plans == []
        skips = [s.reason for s in result.info_skips]
        assert "destination exists" in skips


class TestPlanMigrationWorktrees:
    """Worktree handling: classify as worktree and resolve via the branch template."""

    def test_classifies_worktree(self, tmp_path: Path) -> None:
        worktrees_root = tmp_path / "wt"
        source = tmp_path / "src"
        new_dir = tmp_path / "new"

        _init_repo(source, "https://github.com/user/repo1.git")
        subprocess.run(["git", "branch", "feature"], cwd=source, check=True, capture_output=True)

        wt = worktrees_root / "feature"
        subprocess.run(
            ["git", "worktree", "add", str(wt), "feature"],
            cwd=source,
            check=True,
            capture_output=True,
        )
        # Give the worktree its own remote so it can be planned.
        subprocess.run(
            ["git", "remote", "set-url", "origin", "https://github.com/user/feature.git"],
            cwd=wt,
            check=True,
            capture_output=True,
        )

        config = Config(
            default_sources=f"{new_dir}/path(-2)/path(-1)",
            default_worktrees=f"{new_dir}/wt/path(-1)/norm_branch()",
            sources={},
            actions=[],
        )

        result = plan_migration([wt], config, inplace=False)

        assert isinstance(result, Migration)
        assert len(result.plans) == 1
        plan = result.plans[0]
        assert plan.is_worktree is True
        assert plan.source_path is not None
        assert plan.source_path.resolve() == source.resolve()

    def test_skips_detached_worktree(self, tmp_path: Path) -> None:
        worktrees_root = tmp_path / "wt"
        source = tmp_path / "src"
        new_dir = tmp_path / "new"

        _init_repo(source, "https://github.com/user/repo1.git")
        wt = worktrees_root / "detached"
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(wt), "HEAD"],
            cwd=source,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "remote", "set-url", "origin", "https://github.com/user/detached.git"],
            cwd=wt,
            check=True,
            capture_output=True,
        )

        config = Config(
            default_sources=f"{new_dir}/path(-2)/path(-1)",
            default_worktrees=f"{new_dir}/wt",
            sources={},
            actions=[],
        )

        result = plan_migration([wt], config, inplace=False)

        assert isinstance(result, Migration)
        assert result.plans == []
        assert any(s.reason == "detached HEAD" for s in result.info_skips)