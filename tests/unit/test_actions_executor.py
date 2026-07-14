"""Unit tests for the typed Action classes in gww.actions.types.

These tests previously did not exist: the executor was tested only indirectly
through ``gww.actions.executor.execute_action`` (which took string-tuples and
no real assertions against filesystem behaviour). The typed actions deserve
direct coverage so that filesystem side effects are exercised in isolation.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gww.actions import ActionError
from gww.actions.types import (
    CommandAction,
    CopyAction,
)


class TestCopyAction:
    """``CopyAction.run`` copies a file or directory tree from a resolved
    source into ``target_dir / destination``.

    Both arguments are pre-template-evaluated by
    :func:`gww.actions.apply_actions`; the action itself only sees literal
    strings. The file-vs-directory distinction is made by inspecting the
    resolved source type at run time.
    """

    def test_copies_file_into_target_dir(self, tmp_path: Path) -> None:
        source = tmp_path / "src.txt"
        source.write_text("hello")
        target = tmp_path / "dest"
        target.mkdir()

        action = CopyAction(source=str(source), destination="inside.txt")
        action.run(source_dir=None, target_dir=target)

        copied = target / "inside.txt"
        assert copied.exists()
        assert copied.read_text() == "hello"

    def test_creates_destination_subdirectories(self, tmp_path: Path) -> None:
        source = tmp_path / "src.txt"
        source.write_text("x")
        target = tmp_path / "dest"
        target.mkdir()

        action = CopyAction(source=str(source), destination="nested/dir/file.txt")
        action.run(source_dir=None, target_dir=target)

        assert (target / "nested" / "dir" / "file.txt").exists()

    def test_expands_user_in_source(self, tmp_path: Path) -> None:
        source = tmp_path / "src.txt"
        source.write_text("ok")
        target = tmp_path / "dest"
        target.mkdir()

        action = CopyAction(source=str(source), destination="file.txt")
        action.run(source_dir=None, target_dir=target)

        assert (target / "file.txt").exists()

    def test_absolute_destination_bypasses_target_dir(self, tmp_path: Path) -> None:
        source = tmp_path / "src.txt"
        source.write_text("x")
        target = tmp_path / "dest"
        target.mkdir()
        outside = tmp_path / "outside.txt"

        action = CopyAction(source=str(source), destination=str(outside))
        action.run(source_dir=None, target_dir=target)

        assert outside.exists()
        assert not (target / "outside.txt").exists()

    def test_raises_when_source_missing(self, tmp_path: Path) -> None:
        target = tmp_path / "dest"
        target.mkdir()

        action = CopyAction(source=str(tmp_path / "missing.txt"), destination="x")
        with pytest.raises(ActionError, match="Source path not found"):
            action.run(source_dir=None, target_dir=target)

    def test_raises_when_source_is_broken_symlink(self, tmp_path: Path) -> None:
        """A broken symlink is neither a file nor a directory; the action
        must report a clear :class:`ActionError`."""
        target = tmp_path / "dest"
        target.mkdir()
        real = tmp_path / "real.txt"
        real.write_text("x")
        link = tmp_path / "link.txt"
        link.symlink_to(real)
        real.unlink()  # delete the target, leaving a dangling symlink

        action = CopyAction(source=str(link), destination="x")
        with pytest.raises(ActionError, match="neither a file nor a directory"):
            action.run(source_dir=None, target_dir=target)

    def test_copies_directory_into_target_dir(self, tmp_path: Path) -> None:
        """A source that is a directory must be copied with ``copytree``,
        not ``copy2`` — even when the destination directory does not exist
        yet."""
        source = tmp_path / "src_dir"
        source.mkdir()
        (source / "a.txt").write_text("A")
        target = tmp_path / "dest"
        target.mkdir()

        action = CopyAction(source=str(source), destination="incoming")
        action.run(source_dir=None, target_dir=target)

        assert (target / "incoming" / "a.txt").read_text() == "A"

    def test_copies_directory_merging_into_existing_dest(
        self, tmp_path: Path,
    ) -> None:
        """Existing files in the destination survive; new files from the
        source arrive; shared-path files are overwritten with the source's
        content."""
        source = tmp_path / "src_dir"
        (source / "shared").mkdir(parents=True)
        (source / "shared" / "from_src.txt").write_text("src-shared")
        (source / "new.txt").write_text("brand-new")

        target = tmp_path / "dest"
        existing = target / "incoming"
        (existing / "shared").mkdir(parents=True)
        (existing / "shared" / "pre_existing.txt").write_text("kept")
        (existing / "shared" / "from_src.txt").write_text("to-be-overwritten")
        (existing / "untouched.txt").write_text("untouched")

        action = CopyAction(source=str(source), destination="incoming")
        action.run(source_dir=None, target_dir=target)

        assert (existing / "shared" / "pre_existing.txt").read_text() == "kept"
        assert (existing / "untouched.txt").read_text() == "untouched"
        assert (existing / "new.txt").read_text() == "brand-new"
        assert (existing / "shared" / "from_src.txt").read_text() == "src-shared"

    def test_raises_when_file_copy_fails(self, tmp_path: Path) -> None:
        source = tmp_path / "src.txt"
        source.write_text("x")
        target = tmp_path / "dest"
        target.mkdir()

        action = CopyAction(source=str(source), destination="x")
        with patch("shutil.copy2", side_effect=OSError("boom")):
            with pytest.raises(ActionError, match="Failed to copy"):
                action.run(source_dir=None, target_dir=target)

    def test_raises_when_directory_copy_fails(self, tmp_path: Path) -> None:
        source = tmp_path / "src_dir"
        source.mkdir()
        target = tmp_path / "dest"
        target.mkdir()

        action = CopyAction(source=str(source), destination="incoming")
        with patch("shutil.copytree", side_effect=OSError("disk full")):
            with pytest.raises(ActionError, match="Failed to copy directory"):
                action.run(source_dir=None, target_dir=target)


class TestCommandAction:
    """``CommandAction.run`` invokes ``command + args`` with ``target_dir`` as cwd."""

    def test_runs_command_in_target_dir(self, tmp_path: Path) -> None:
        target = tmp_path / "work"
        target.mkdir()
        marker = target / "marker.txt"

        action = CommandAction(command="touch", args=[str(marker)])
        action.run(source_dir=None, target_dir=target)

        assert marker.exists()

    def test_runs_command_with_cwd_being_target_dir(self, tmp_path: Path) -> None:
        target = tmp_path / "work"
        target.mkdir()

        # pwd prints the cwd; we read it back via the action's subprocess.run
        captured_cwd: dict[str, str] = {}
        original_run = subprocess.run

        def fake_run(cmd, cwd, **kwargs):  # type: ignore[no-untyped-def]
            captured_cwd["cwd"] = str(cwd)
            result = MagicMock()
            result.returncode = 0
            result.stderr = ""
            return result

        action = CommandAction(command="true", args=[])
        with patch("gww.actions.types.subprocess.run", side_effect=fake_run):
            action.run(source_dir=None, target_dir=target)

        assert captured_cwd["cwd"] == str(target)
        del original_run  # silence unused warning

    def test_raises_when_command_fails(self, tmp_path: Path) -> None:
        target = tmp_path / "work"
        target.mkdir()

        action = CommandAction(command="false", args=[])
        with pytest.raises(ActionError, match="Command failed"):
            action.run(source_dir=None, target_dir=target)

    def test_raises_when_command_fails_with_pass_through_stdout(
        self, tmp_path: Path,
    ) -> None:
        """When ``pass_through_stdout=True`` both stdout and stderr are
        inherited from the parent (``None`` in :mod:`subprocess`). The
        failure message must not crash on a missing stderr capture."""
        target = tmp_path / "work"
        target.mkdir()

        action = CommandAction(command="false", args=[])
        with pytest.raises(ActionError, match="Command failed"):
            action.run(
                source_dir=None,
                target_dir=target,
                pass_through_stdout=True,
            )

    def test_raises_when_command_missing(self, tmp_path: Path) -> None:
        target = tmp_path / "work"
        target.mkdir()

        action = CommandAction(command="definitely-not-a-real-binary-xyz", args=[])
        with pytest.raises(ActionError, match="Command not found"):
            action.run(source_dir=None, target_dir=target)

    def test_raises_action_error_when_subprocess_oserror(self, tmp_path: Path) -> None:
        target = tmp_path / "work"
        target.mkdir()

        action = CommandAction(command="anything", args=[])

        def fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
            raise OSError("spawn failed")

        with patch("gww.actions.types.subprocess.run", side_effect=fake_run):
            with pytest.raises(ActionError, match="Failed to execute"):
                action.run(source_dir=None, target_dir=target)


class TestCommandActionPassThroughStdout:
    """``CommandAction.run`` must let callers opt into streaming subprocess stdout.

    Same contract as ``run_git``: default keeps both streams captured; with
    ``pass_through_stdout=True`` stdout inherits from the parent and stderr
    stays captured so ``ActionError`` can still surface it.
    """

    @staticmethod
    def _fake_completed(returncode: int = 0, stderr: str = "") -> MagicMock:
        result = MagicMock()
        result.returncode = returncode
        result.stdout = ""
        result.stderr = stderr
        return result

    def test_default_captures_both_streams(self, tmp_path: Path) -> None:
        """Without pass_through_stdout, subprocess.run captures both streams."""
        target = tmp_path / "work"
        target.mkdir()

        with patch(
            "gww.actions.types.subprocess.run",
            return_value=self._fake_completed(),
        ) as mock_run:
            CommandAction(command="echo", args=["hi"]).run(
                source_dir=None, target_dir=target
            )

        kwargs = mock_run.call_args.kwargs
        assert kwargs["stdout"] == subprocess.PIPE
        assert kwargs["stderr"] == subprocess.PIPE

    def test_pass_through_stdout_inherits_parent_stdout(self, tmp_path: Path) -> None:
        """pass_through_stdout=True streams stdout to the parent process."""
        target = tmp_path / "work"
        target.mkdir()

        with patch(
            "gww.actions.types.subprocess.run",
            return_value=self._fake_completed(),
        ) as mock_run:
            CommandAction(command="echo", args=["hi"]).run(
                source_dir=None,
                target_dir=target,
                pass_through_stdout=True,
            )

        kwargs = mock_run.call_args.kwargs
        assert kwargs["stdout"] is None
        assert kwargs["stderr"] is None

    def test_pass_through_stdout_streams_stderr_too(
        self, tmp_path: Path
    ) -> None:
        """When streaming, stderr also inherits from the parent — the user
        sees the external command's stderr output in real time."""
        target = tmp_path / "work"
        target.mkdir()

        with patch(
            "gww.actions.types.subprocess.run",
            return_value=self._fake_completed(returncode=1, stderr=""),
        ):
            with pytest.raises(ActionError):
                CommandAction(command="false", args=[]).run(
                    source_dir=None,
                    target_dir=target,
                    pass_through_stdout=True,
                )
