"""Integration tests for streaming git and external command output.

These tests cover the ``-q`` / ``--quiet`` flag's effect on subprocess output
in :mod:`gww.cli.commands`. The behavior is:

* Default (no ``-q``): git's stdout is streamed to the user's terminal so
  progress messages (``Cloning into …``, ``Receiving objects: 100%``,
  ``Already up to date.``) are visible in real time.
* With ``-q``: stdout is captured (the historic behavior); only the final
  ``say()``-emitted result line is suppressed as well.

We use :func:`pytest.CaptureFixture` (alias ``capfd``) rather than
:func:`pytest.CaptureFixture` (alias ``capsys``) because the subprocess
output lives at the OS file-descriptor level, not the Python ``sys``
level.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from gww.cli.commands.add import run_add
from gww.cli.commands.clone import run_clone
from gww.cli.commands.pull import run_pull
from gww.cli.commands.remove import run_remove
from tests.conftest import make_ctx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def bare_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A bare git repository suitable for cloning."""
    source = tmp_path_factory.mktemp("source")
    subprocess.run(["git", "init"], cwd=source, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t"],
        cwd=source,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "T"],
        cwd=source,
        check=True,
        capture_output=True,
    )
    (source / "README.md").write_text("# Source\n")
    subprocess.run(["git", "add", "."], cwd=source, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial"],
        cwd=source,
        check=True,
        capture_output=True,
    )

    bare = tmp_path_factory.mktemp("bare") / "test.git"
    subprocess.run(
        ["git", "clone", "--bare", str(source), str(bare)],
        check=True,
        capture_output=True,
    )
    return bare


@pytest.fixture
def local_clone(
    bare_repo: Path, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    """A local clone of ``bare_repo`` with a ``file://`` remote ``origin``.

    The URI scheme is required because :func:`run_add` parses the remote
    URI to resolve the worktree path.
    """
    local = tmp_path_factory.mktemp("local")
    subprocess.run(
        ["git", "clone", f"file://{bare_repo}", str(local)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "t@t"],
        cwd=local,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "T"],
        cwd=local,
        check=True,
        capture_output=True,
    )
    return local


# ---------------------------------------------------------------------------
# clone
# ---------------------------------------------------------------------------


class TestCloneStreamsGitOutput:
    """``gww clone`` must stream git's progress to the user by default."""

    def test_default_mode_streams_clone_progress_to_stdout(
        self,
        bare_repo: Path,
        config_dir: Path,
        tmp_path: Path,
        capfd: pytest.CaptureFixture[str],
    ) -> None:
        target = tmp_path / "sources"
        (config_dir / "gww" / "config.yml").parent.mkdir(parents=True, exist_ok=True)
        (config_dir / "gww" / "config.yml").write_text(
            f"default_sources: {target}/path(-1)\n"
            f"default_worktrees: {tmp_path}/worktrees\n"
        )

        result = run_clone(make_ctx(uri=f"file://{bare_repo}"))

        assert result == 0
        captured = capfd.readouterr()
        # git writes "Cloning into '…'" to stdout when it detects a terminal;
        # when stdout is captured it suppresses that line, but the
        # "Receiving objects" / "Resolving deltas" lines remain. The crucial
        # assertion is that *something* from git is present.
        combined = captured.out + captured.err
        assert "Cloning" in combined or "Receiving" in combined or "remote:" in combined

    def test_quiet_mode_captures_clone_progress(
        self,
        bare_repo: Path,
        config_dir: Path,
        tmp_path: Path,
        capfd: pytest.CaptureFixture[str],
    ) -> None:
        target = tmp_path / "sources"
        (config_dir / "gww" / "config.yml").parent.mkdir(parents=True, exist_ok=True)
        (config_dir / "gww" / "config.yml").write_text(
            f"default_sources: {target}/path(-1)\n"
            f"default_worktrees: {tmp_path}/worktrees\n"
        )

        result = run_clone(make_ctx(uri=f"file://{bare_repo}", quiet=True))

        assert result == 0
        captured = capfd.readouterr()
        # No git progress lines should leak through when quiet.
        assert "Receiving objects" not in captured.out
        assert "remote:" not in captured.out
        # And the say() result line is suppressed too.
        assert captured.out == ""


# ---------------------------------------------------------------------------
# pull
# ---------------------------------------------------------------------------


class TestPullStreamsGitOutput:
    """``gww pull`` must stream git's progress to the user by default."""

    def _push_upstream_change(
        self, bare_repo: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        tmp = tmp_path_factory.mktemp("upstream") / "push"
        subprocess.run(
            ["git", "clone", str(bare_repo), str(tmp)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "t@t"],
            cwd=tmp,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "T"],
            cwd=tmp,
            check=True,
            capture_output=True,
        )
        (tmp / "upstream.txt").write_text("new")
        subprocess.run(["git", "add", "."], cwd=tmp, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Upstream"],
            cwd=tmp,
            check=True,
            capture_output=True,
        )
        subprocess.run(["git", "push"], cwd=tmp, check=True, capture_output=True)

    def test_default_mode_streams_pull_progress_to_stdout(
        self,
        local_clone: Path,
        bare_repo: Path,
        tmp_path_factory: pytest.TempPathFactory,
        monkeypatch: pytest.MonkeyPatch,
        capfd: pytest.CaptureFixture[str],
    ) -> None:
        self._push_upstream_change(bare_repo, tmp_path_factory)
        monkeypatch.chdir(local_clone)

        result = run_pull(make_ctx())

        assert result == 0
        captured = capfd.readouterr()
        # git's "Already" / "Fast-forward" / "Updating" lines land on stdout.
        combined = captured.out + captured.err
        assert (
            "Already" in combined
            or "Fast-forward" in combined
            or "Updating" in combined
        )

    def test_quiet_mode_captures_pull_progress(
        self,
        local_clone: Path,
        bare_repo: Path,
        tmp_path_factory: pytest.TempPathFactory,
        monkeypatch: pytest.MonkeyPatch,
        capfd: pytest.CaptureFixture[str],
    ) -> None:
        self._push_upstream_change(bare_repo, tmp_path_factory)
        monkeypatch.chdir(local_clone)

        result = run_pull(make_ctx(quiet=True))

        assert result == 0
        captured = capfd.readouterr()
        assert "Already" not in captured.out
        assert "Fast-forward" not in captured.out
        # say() line is also suppressed.
        assert captured.out == ""


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------


class TestAddStreamsGitOutput:
    """``gww add`` must stream ``git worktree add`` progress by default."""

    def test_default_mode_streams_worktree_add_progress(
        self,
        local_clone: Path,
        config_dir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capfd: pytest.CaptureFixture[str],
    ) -> None:
        (config_dir / "gww" / "config.yml").parent.mkdir(parents=True, exist_ok=True)
        (config_dir / "gww" / "config.yml").write_text(
            f"default_sources: {tmp_path}/sources\n"
            f"default_worktrees: {tmp_path}/worktrees\n"
        )
        monkeypatch.chdir(local_clone)

        result = run_add(make_ctx(branch="feature", create_branch=True))

        assert result == 0
        captured = capfd.readouterr()
        combined = captured.out + captured.err
        # git writes "Preparing worktree (new branch 'feature')" to stderr;
        # it must reach the user via stderr streaming.
        assert "Preparing worktree" in combined

    def test_quiet_mode_captures_worktree_add_progress(
        self,
        local_clone: Path,
        config_dir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capfd: pytest.CaptureFixture[str],
    ) -> None:
        (config_dir / "gww" / "config.yml").parent.mkdir(parents=True, exist_ok=True)
        (config_dir / "gww" / "config.yml").write_text(
            f"default_sources: {tmp_path}/sources\n"
            f"default_worktrees: {tmp_path}/worktrees\n"
        )
        monkeypatch.chdir(local_clone)

        result = run_add(make_ctx(branch="feature", create_branch=True, quiet=True))

        assert result == 0
        captured = capfd.readouterr()
        assert "Preparing worktree" not in captured.out
        assert captured.out == ""


# ---------------------------------------------------------------------------
# remove (silent on success — test the wiring instead)
# ---------------------------------------------------------------------------


class TestRemovePassesPassThroughToWorktreeRemove:
    """``gww remove`` forwards ``pass_through_stdout`` to the worktree op."""

    @staticmethod
    def _fake_run_git(args, cwd, check=True, pass_through_stdout=False):  # type: ignore[no-untyped-def]
        from gww.git.repository import subprocess as _subprocess

        result = _subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        return result

    def _setup_worktree(self, local_clone: Path) -> Path:
        wt_path = local_clone.parent / "wt"
        subprocess.run(
            ["git", "worktree", "add", str(wt_path), "-b", "feature"],
            cwd=local_clone,
            check=True,
            capture_output=True,
        )
        return wt_path

    def test_default_mode_passes_pass_through_stdout_true(
        self,
        local_clone: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._setup_worktree(local_clone)
        monkeypatch.chdir(local_clone)

        with patch(
            "gww.git.worktree.run_git", side_effect=self._fake_run_git
        ) as mock_run:
            result = run_remove(make_ctx(branch_or_path="feature"))

        assert result == 0
        remove_calls = [
            call
            for call in mock_run.call_args_list
            if call.args and "remove" in call.args[0]
        ]
        assert remove_calls, "expected a 'git worktree remove' call"
        kwargs = remove_calls[-1].kwargs
        assert kwargs.get("pass_through_stdout") is True

    def test_quiet_mode_passes_pass_through_stdout_false(
        self,
        local_clone: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._setup_worktree(local_clone)
        monkeypatch.chdir(local_clone)

        with patch(
            "gww.git.worktree.run_git", side_effect=self._fake_run_git
        ) as mock_run:
            result = run_remove(make_ctx(branch_or_path="feature", quiet=True))

        assert result == 0
        remove_calls = [
            call
            for call in mock_run.call_args_list
            if call.args and "remove" in call.args[0]
        ]
        assert remove_calls
        kwargs = remove_calls[-1].kwargs
        assert kwargs.get("pass_through_stdout") is False
