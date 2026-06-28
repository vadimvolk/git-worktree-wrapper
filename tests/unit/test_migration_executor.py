"""Unit tests for gww.migration.executor.execute and fix_copied_worktree_gitfile.

These tests exercise the executor against real on-disk files in a tmp
directory so the shutil-move/copytree branches and the post-move repair
logic are covered without needing to spin up an end-to-end git fixture
(that's the integration suite's job).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from gww.git.worktree import read_gitdir
from gww.migration import (
    Migration,
    MigrationPlan,
    Skip,
    execute,
    fix_copied_worktree_gitfile,
)


def _make_plan(old_path: Path, new_path: Path, **kwargs: object) -> MigrationPlan:
    return MigrationPlan(
        old_path=old_path,
        new_path=new_path,
        uri=kwargs.pop("uri", "https://example.com/owner/repo.git"),
        is_worktree=kwargs.pop("is_worktree", False),
        source_path=kwargs.pop("source_path", None),
    )


class TestExecuteDryRun:
    """Dry-run mode reports what would happen without moving anything."""

    def test_dry_run_does_not_move_files(self, tmp_path: Path) -> None:
        old = tmp_path / "old"
        new = tmp_path / "new" / "repo"
        old.mkdir(parents=True)
        (old / "file.txt").write_text("data")

        migration = Migration(plans=[_make_plan(old, new)])
        rc = execute(
            migration,
            input_roots=[tmp_path / "in"],
            mode="copy",
            dry_run=True,
            quiet=True,
            verbose=0,
        )

        assert rc == 0
        assert old.exists()
        assert (old / "file.txt").exists()
        assert not new.exists()

    def test_dry_run_summarises_plan_count(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        old = tmp_path / "old"
        new = tmp_path / "new" / "repo"
        old.mkdir(parents=True)
        (old / "file.txt").write_text("x")

        migration = Migration(plans=[_make_plan(old, new)])
        execute(
            migration,
            input_roots=[],
            mode="copy",
            dry_run=True,
            quiet=False,
            verbose=0,
        )

        captured = capsys.readouterr()
        assert "Would migrate 1 repositories" in captured.out


class TestExecuteCopy:
    """Copy mode uses shutil.copytree and leaves the source in place."""

    def test_copy_moves_content_to_new_path(self, tmp_path: Path) -> None:
        old = tmp_path / "old"
        new = tmp_path / "new" / "repo"
        old.mkdir(parents=True)
        (old / "file.txt").write_text("payload")
        (old / "sub").mkdir()
        (old / "sub" / "nested.txt").write_text("nested")

        migration = Migration(plans=[_make_plan(old, new)])
        rc = execute(
            migration,
            input_roots=[],
            mode="copy",
            dry_run=False,
            quiet=True,
            verbose=0,
        )

        assert rc == 0
        assert old.exists(), "copy mode must leave the source in place"
        assert (new / "file.txt").read_text() == "payload"
        assert (new / "sub" / "nested.txt").read_text() == "nested"


class TestExecuteInplace:
    """Inplace mode uses shutil.move and cleans up empty source folders."""

    def test_inplace_moves_and_removes_empty_parent(self, tmp_path: Path) -> None:
        old_parent = tmp_path / "old_parent"
        old = old_parent / "owner" / "repo"
        new = tmp_path / "new" / "repo"
        old.mkdir(parents=True)
        (old / "file.txt").write_text("data")

        migration = Migration(plans=[_make_plan(old, new)])
        rc = execute(
            migration,
            input_roots=[old_parent],
            mode="inplace",
            dry_run=False,
            quiet=True,
            verbose=0,
        )

        assert rc == 0
        assert not old.exists()
        assert not (old_parent / "owner").exists(), "empty source folders should be cleaned"
        assert (new / "file.txt").read_text() == "data"

    def test_inplace_keeps_non_empty_folders(self, tmp_path: Path) -> None:
        old_parent = tmp_path / "old_parent"
        old = old_parent / "owner" / "repo"
        sibling = old_parent / "owner" / "sibling"
        new = tmp_path / "new" / "repo"

        old.mkdir(parents=True)
        (old / "f.txt").write_text("x")
        sibling.mkdir(parents=True)
        (sibling / "other.txt").write_text("kept")

        migration = Migration(plans=[_make_plan(old, new)])
        execute(
            migration,
            input_roots=[old_parent],
            mode="inplace",
            dry_run=False,
            quiet=True,
            verbose=0,
        )

        assert not old.exists()
        assert sibling.exists(), "non-empty sibling dir must not be removed"
        assert (sibling / "other.txt").exists()


class TestExecuteEmptyMigration:
    """An empty Migration (no plans, no skips) is a no-op."""

    def test_empty_migration_returns_zero(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        migration = Migration()

        rc = execute(
            migration,
            input_roots=[],
            mode="copy",
            dry_run=False,
            quiet=False,
            verbose=0,
        )

        assert rc == 0
        captured = capsys.readouterr()
        assert "No repositories to migrate" in captured.out


class TestExecuteSkipReporting:
    """Skips are reported in the summary, grouped by reason."""

    def test_skips_are_printed_grouped_by_reason(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        migration = Migration(
            info_skips=[
                Skip(reason="no remote origin configured", path=tmp_path / "a", is_worktree=False),
                Skip(reason="no remote origin configured", path=tmp_path / "b", is_worktree=False),
            ],
        )

        rc = execute(
            migration,
            input_roots=[],
            mode="copy",
            dry_run=False,
            quiet=False,
            verbose=0,
        )

        assert rc == 0
        captured = capsys.readouterr()
        assert "no remote origin configured" in captured.out
        assert "2 sources" in captured.out


class TestFixCopiedWorktreeGitfile:
    """fix_copied_worktree_gitfile rewrites the .git pointer of a copied worktree."""

    def test_rewrites_pointer_to_new_source(self, tmp_path: Path) -> None:
        old_source = tmp_path / "old_source"
        new_source = tmp_path / "new_source"
        new_wt = tmp_path / "new_wt"
        new_wt.mkdir()
        new_source.mkdir()

        git_file = new_wt / ".git"
        git_file.write_text(
            f"gitdir: {old_source}/.git/worktrees/feature-x\n"
        )

        fix_copied_worktree_gitfile(new_wt, new_source)

        new_gitdir = read_gitdir(git_file)
        assert new_gitdir == str(new_source / ".git" / "worktrees" / "feature-x")

    def test_noop_when_gitfile_missing(self, tmp_path: Path) -> None:
        new_wt = tmp_path / "new_wt"
        new_wt.mkdir()

        # Must not raise.
        fix_copied_worktree_gitfile(new_wt, tmp_path / "new_source")

    def test_noop_when_gitfile_lacks_gitdir_prefix(self, tmp_path: Path) -> None:
        new_wt = tmp_path / "new_wt"
        new_wt.mkdir()
        git_file = new_wt / ".git"
        git_file.write_text("random content\n")

        fix_copied_worktree_gitfile(new_wt, tmp_path / "new_source")

        # File unchanged.
        assert git_file.read_text() == "random content\n"

    def test_noop_when_path_lacks_worktrees_segment(self, tmp_path: Path) -> None:
        new_wt = tmp_path / "new_wt"
        new_wt.mkdir()
        git_file = new_wt / ".git"
        git_file.write_text("gitdir: /some/random/path\n")

        fix_copied_worktree_gitfile(new_wt, tmp_path / "new_source")

        # File unchanged.
        assert "gitdir: /some/random/path" in git_file.read_text()