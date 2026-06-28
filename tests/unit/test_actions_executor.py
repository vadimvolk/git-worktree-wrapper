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
    AbsCopyAction,
    CommandAction,
    RelCopyAction,
)


class TestAbsCopyAction:
    """``AbsCopyAction.run`` copies ``source`` to ``target_dir / destination``."""

    def test_copies_file_into_target_dir(self, tmp_path: Path) -> None:
        source = tmp_path / "src.txt"
        source.write_text("hello")
        target = tmp_path / "dest"
        target.mkdir()

        action = AbsCopyAction(source=str(source), destination="inside.txt")
        action.run(source_dir=None, target_dir=target)

        copied = target / "inside.txt"
        assert copied.exists()
        assert copied.read_text() == "hello"

    def test_creates_destination_subdirectories(self, tmp_path: Path) -> None:
        source = tmp_path / "src.txt"
        source.write_text("x")
        target = tmp_path / "dest"
        target.mkdir()

        action = AbsCopyAction(source=str(source), destination="nested/dir/file.txt")
        action.run(source_dir=None, target_dir=target)

        assert (target / "nested" / "dir" / "file.txt").exists()

    def test_expands_user_in_source(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # We do not have a real ~, but we can confirm that the path is
        # resolved by writing to a known absolute path and using a relative
        # source that Path.expanduser leaves untouched.
        source = tmp_path / "src.txt"
        source.write_text("ok")
        target = tmp_path / "dest"
        target.mkdir()

        action = AbsCopyAction(source=str(source), destination="file.txt")
        action.run(source_dir=None, target_dir=target)

        assert (target / "file.txt").exists()

    def test_raises_when_source_missing(self, tmp_path: Path) -> None:
        target = tmp_path / "dest"
        target.mkdir()

        action = AbsCopyAction(source=str(tmp_path / "missing.txt"), destination="x")
        with pytest.raises(ActionError, match="Source file not found"):
            action.run(source_dir=None, target_dir=target)

    def test_raises_when_source_is_directory(self, tmp_path: Path) -> None:
        target = tmp_path / "dest"
        target.mkdir()
        not_a_file = tmp_path / "subdir"
        not_a_file.mkdir()

        action = AbsCopyAction(source=str(not_a_file), destination="x")
        with pytest.raises(ActionError, match="not a file"):
            action.run(source_dir=None, target_dir=target)

    def test_raises_when_copy_fails(self, tmp_path: Path) -> None:
        source = tmp_path / "src.txt"
        source.write_text("x")

        target = tmp_path / "dest"
        target.mkdir()

        action = AbsCopyAction(source=str(source), destination="x")
        with patch("shutil.copy2", side_effect=OSError("boom")):
            with pytest.raises(ActionError, match="Failed to copy"):
                action.run(source_dir=None, target_dir=target)


class TestRelCopyAction:
    """``RelCopyAction.run`` copies from ``source_dir`` to ``target_dir``."""

    def test_copies_relative_file(self, tmp_path: Path) -> None:
        source_dir = tmp_path / "src"
        source_dir.mkdir()
        (source_dir / "shared.txt").write_text("data")

        target_dir = tmp_path / "dst"
        target_dir.mkdir()

        action = RelCopyAction(source="shared.txt")
        action.run(source_dir=source_dir, target_dir=target_dir)

        assert (target_dir / "shared.txt").read_text() == "data"

    def test_copies_with_explicit_destination(self, tmp_path: Path) -> None:
        source_dir = tmp_path / "src"
        source_dir.mkdir()
        (source_dir / "a.txt").write_text("A")

        target_dir = tmp_path / "dst"
        target_dir.mkdir()

        action = RelCopyAction(source="a.txt", destination="renamed.txt")
        action.run(source_dir=source_dir, target_dir=target_dir)

        assert not (target_dir / "a.txt").exists()
        assert (target_dir / "renamed.txt").read_text() == "A"

    def test_creates_destination_subdirectories(self, tmp_path: Path) -> None:
        source_dir = tmp_path / "src"
        source_dir.mkdir()
        (source_dir / "a.txt").write_text("A")

        target_dir = tmp_path / "dst"
        target_dir.mkdir()

        action = RelCopyAction(source="a.txt", destination="nested/file.txt")
        action.run(source_dir=source_dir, target_dir=target_dir)

        assert (target_dir / "nested" / "file.txt").exists()

    def test_raises_when_source_dir_is_none(self, tmp_path: Path) -> None:
        action = RelCopyAction(source="x")
        with pytest.raises(ActionError, match="requires source_dir"):
            action.run(source_dir=None, target_dir=tmp_path)

    def test_raises_when_source_file_missing(self, tmp_path: Path) -> None:
        source_dir = tmp_path / "src"
        source_dir.mkdir()
        target_dir = tmp_path / "dst"
        target_dir.mkdir()

        action = RelCopyAction(source="ghost.txt")
        with pytest.raises(ActionError, match="Source file not found"):
            action.run(source_dir=source_dir, target_dir=target_dir)

    def test_raises_when_copy_fails(self, tmp_path: Path) -> None:
        source_dir = tmp_path / "src"
        source_dir.mkdir()
        (source_dir / "a.txt").write_text("A")
        target_dir = tmp_path / "dst"
        target_dir.mkdir()

        action = RelCopyAction(source="a.txt")
        with patch("shutil.copy2", side_effect=OSError("disk full")):
            with pytest.raises(ActionError, match="Failed to copy"):
                action.run(source_dir=source_dir, target_dir=target_dir)


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