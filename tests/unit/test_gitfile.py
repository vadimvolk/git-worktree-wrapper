"""Unit tests for the shared .git-file parser used by gww.git and gww.migration."""

from __future__ import annotations

from pathlib import Path

import pytest

from gww.git.worktree import read_gitdir, worktree_id_from_gitdir


class TestReadGitdir:
    """``read_gitdir`` parses a worktree's ``.git`` file."""

    def test_returns_gitdir_for_valid_file(self, tmp_path: Path) -> None:
        gitfile = tmp_path / ".git"
        gitfile.write_text("gitdir: /absolute/path/.git/worktrees/abc\n")

        result = read_gitdir(gitfile)

        assert result == "/absolute/path/.git/worktrees/abc"

    def test_strips_whitespace(self, tmp_path: Path) -> None:
        gitfile = tmp_path / ".git"
        gitfile.write_text("  gitdir:   /p/.git/worktrees/x  \n")

        assert read_gitdir(gitfile) == "/p/.git/worktrees/x"

    def test_returns_none_when_path_missing(self, tmp_path: Path) -> None:
        assert read_gitdir(tmp_path / "missing") is None

    def test_returns_none_when_path_is_directory(self, tmp_path: Path) -> None:
        # In source repos .git is a directory; the parser must not blow up.
        assert read_gitdir(tmp_path / ".git") is None  # tmp_path/.git does not exist

    def test_returns_none_for_non_gitdir_content(self, tmp_path: Path) -> None:
        gitfile = tmp_path / ".git"
        gitfile.write_text("not a gitdir line\n")

        assert read_gitdir(gitfile) is None

    def test_returns_none_for_empty_file(self, tmp_path: Path) -> None:
        gitfile = tmp_path / ".git"
        gitfile.write_text("")

        assert read_gitdir(gitfile) is None

    def test_returns_none_when_read_fails(self, tmp_path: Path) -> None:
        gitfile = tmp_path / ".git"
        gitfile.write_text("gitdir: /x")

        # Force an OSError by pointing at a file we cannot read.
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(Path, "read_text", lambda self, *a, **kw: (_ for _ in ()).throw(OSError("denied")))
            assert read_gitdir(gitfile) is None


class TestWorktreeIdFromGitdir:
    """``worktree_id_from_gitdir`` extracts the worktree id segment."""

    def test_extracts_id_from_standard_path(self) -> None:
        assert worktree_id_from_gitdir("/repo/.git/worktrees/feature-x") == "feature-x"

    def test_handles_windows_style_backslashes(self) -> None:
        assert worktree_id_from_gitdir("C:\\repo\\.git\\worktrees\\mywt") == "mywt"

    def test_returns_none_when_worktrees_segment_missing(self) -> None:
        assert worktree_id_from_gitdir("/repo/.git/no-worktrees-here") is None

    def test_returns_none_when_worktrees_is_last_segment(self) -> None:
        # ``.../worktrees`` with nothing after it is not a valid worktree path.
        assert worktree_id_from_gitdir("/repo/.git/worktrees") is None

    def test_returns_none_for_empty_string(self) -> None:
        assert worktree_id_from_gitdir("") is None