"""Typed action objects executed by clone and add commands.

Each action is a small class that knows how to run itself against a target
directory. Actions are constructed by :func:`gww.actions.apply_actions`,
which evaluates any predicate and command-template context for them.

The three concrete action classes cover the supported ``abs_copy``,
``rel_copy``, and ``command`` action types from the YAML config.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional, Protocol


class ActionError(Exception):
    """Raised when an action fails to execute."""


class Action(Protocol):
    """Protocol every executable action implements.

    Actions are run by the clone/add commands inside a ``for`` loop; calling
    code is expected to wrap each invocation in its own try/except and decide
    whether to surface the failure or continue with the remaining actions.
    """

    def run(
        self,
        source_dir: Optional[Path],
        target_dir: Path,
        pass_through_stdout: bool = False,
    ) -> None:
        """Execute the action against ``target_dir``.

        Args:
            source_dir: Path to the source repository. ``None`` for
                ``abs_copy`` and source-only contexts; required for
                ``rel_copy`` and worktree commands.
            target_dir: Path to operate on (source repo for ``after_clone``,
                worktree for ``after_add``).
            pass_through_stdout: Only meaningful for :class:`CommandAction`.
                When ``True``, the external command's stdout is inherited from
                the parent (so the user sees its progress in real time) while
                stderr stays captured for the :class:`ActionError` message.

        Raises:
            ActionError: If the action fails for any reason.
        """
        ...


class AbsCopyAction:
    """Copy a file from an absolute source path into ``target_dir``.

    Attributes:
        source: Absolute source file path (may contain ``~``).
        destination: Destination path relative to ``target_dir``.
    """

    def __init__(self, source: str, destination: str) -> None:
        self.source = source
        self.destination = destination

    def run(
        self,
        source_dir: Optional[Path],
        target_dir: Path,
        pass_through_stdout: bool = False,
    ) -> None:
        """Copy ``source`` into ``target_dir / destination``.

        Raises:
            ActionError: If the source is missing, not a file, or cannot be
                copied.
        """
        del source_dir, pass_through_stdout  # unused for absolute copy
        source_path = Path(self.source).expanduser().resolve()
        dest_path = target_dir / self.destination

        if not source_path.exists():
            raise ActionError(f"Source file not found for abs_copy: {source_path}")
        if not source_path.is_file():
            raise ActionError(f"Source is not a file for abs_copy: {source_path}")

        dest_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            shutil.copy2(source_path, dest_path)
        except OSError as e:
            raise ActionError(
                f"Failed to copy {source_path} to {dest_path}: {e}"
            ) from e


class RelCopyAction:
    """Copy a file from ``source_dir`` into ``target_dir`` using relative paths.

    Attributes:
        source: Path relative to ``source_dir``.
        destination: Path relative to ``target_dir``; defaults to ``source``.
    """

    def __init__(self, source: str, destination: Optional[str] = None) -> None:
        self.source = source
        self.destination = destination

    def run(
        self,
        source_dir: Optional[Path],
        target_dir: Path,
        pass_through_stdout: bool = False,
    ) -> None:
        """Copy ``source_dir / source`` into ``target_dir / destination``.

        Raises:
            ActionError: If ``source_dir`` is missing, the source file does
                not exist, or the copy fails.
        """
        del pass_through_stdout  # unused for relative copy
        if source_dir is None:
            raise ActionError("rel_copy requires source_dir")

        source_path = source_dir / self.source
        dest_path = target_dir / (self.destination or self.source)

        if not source_path.exists():
            raise ActionError(f"Source file not found for rel_copy: {source_path}")
        if not source_path.is_file():
            raise ActionError(f"Source is not a file for rel_copy: {source_path}")

        dest_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            shutil.copy2(source_path, dest_path)
        except OSError as e:
            raise ActionError(
                f"Failed to copy {source_path} to {dest_path}: {e}"
            ) from e


class CommandAction:
    """Run an external command with ``target_dir`` as the working directory.

    Attributes:
        command: Executable name or path (already evaluated and shlex-split).
        args: Arguments to pass to the command.
    """

    def __init__(self, command: str, args: list[str]) -> None:
        self.command = command
        self.args = args

    def run(
        self,
        source_dir: Optional[Path],
        target_dir: Path,
        pass_through_stdout: bool = False,
    ) -> None:
        """Invoke the command in ``target_dir``.

        Raises:
            ActionError: If the command exits non-zero, the executable is
                missing, or the subprocess cannot be started.
        """
        del source_dir  # commands always run from target_dir
        cmd = [self.command] + self.args

        try:
            result = subprocess.run(
                cmd,
                cwd=target_dir,
                stdout=None if pass_through_stdout else subprocess.PIPE,
                stderr=None if pass_through_stdout else subprocess.PIPE,
                text=True,
                check=False,
            )
        except FileNotFoundError as e:
            raise ActionError(f"Command not found: {self.command}") from e
        except OSError as e:
            raise ActionError(f"Failed to execute command: {e}") from e

        if result.returncode != 0:
            raise ActionError(
                f"Command failed: {' '.join(cmd)}\n"
                f"Exit code: {result.returncode}\n"
                f"Stderr: {result.stderr.strip()}"
            )