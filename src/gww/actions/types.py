"""Typed action objects executed by clone and add commands.

Each action is a small class that knows how to run itself against a target
directory. Actions are constructed by :func:`gww.actions.apply_actions`,
which evaluates any predicate and command-template context for them.

The concrete action classes cover the supported ``copy`` and ``command``
action types from the YAML config (ADR-0012).
"""

from __future__ import annotations

import os
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
            source_dir: Path to the source repository. Currently unused by
                the shipped action types but retained on the protocol to
                avoid touching every call site (ADR-0012 §"Notes for future
                readers").
            target_dir: Path to operate on (source repo for ``after_clone``,
                worktree for ``after_add`` and ``before_remove``).
            pass_through_stdout: Only meaningful for :class:`CommandAction`.
                When ``True``, the external command's stdout is inherited from
                the parent (so the user sees its progress in real time) while
                stderr stays captured for the :class:`ActionError` message.

        Raises:
            ActionError: If the action fails for any reason.
        """
        ...


class CopyAction:
    """Copy a file or directory tree from a resolved source into ``target_dir``.

    The two constructor arguments are *template-evaluated* strings supplied
    by :func:`gww.actions.apply_actions` (i.e. any ``source_path(extra)``,
    ``current_worktree(extra)``, or absolute-literal reference has already
    been resolved before the action is constructed). The operation itself
    is selected by the resolved source's filesystem type — ``shutil.copy2``
    (silent overwrite) for files, ``shutil.copytree(src, dst,
    dirs_exist_ok=True)`` (merge into an existing directory) for directory
    trees. The destination's parent is created with
    ``mkdir(parents=True, exist_ok=True)`` before either operation runs.

    Attributes:
        source: Absolute source path (file or directory) as returned by the
            template engine — no further template substitution happens here.
        destination: Destination path relative to ``target_dir``. An absolute
            destination bypasses the relative resolution and is used as-is.
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
        """Copy ``source`` to ``target_dir / destination``.

        Raises:
            ActionError: If the source is missing, is neither a file nor a
                directory, or the copy operation fails.
        """
        del source_dir, pass_through_stdout  # unused for copy
        literal = Path(self.source).expanduser()
        dest_path = Path(self.destination)
        if not dest_path.is_absolute():
            dest_path = target_dir / dest_path

        if not os.path.lexists(literal):
            raise ActionError(f"Source path not found for copy: {literal}")

        # A broken symlink has ``is_symlink() == True`` but ``exists() ==
        # False`` (the latter follows the link). ``Path.resolve()`` follows
        # symlinks too, so a broken link resolves to its (non-existent)
        # target — that would land in the "not found" branch above if we
        # resolved first. Detect the broken-symlink case here so the error
        # points at the symlink, not the missing target.
        if literal.is_symlink() and not literal.exists():
            raise ActionError(
                f"Source is neither a file nor a directory for copy: {literal}"
            )

        source_path = literal.resolve()

        if source_path.is_file():
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(source_path, dest_path)
            except OSError as e:
                raise ActionError(
                    f"Failed to copy {source_path} to {dest_path}: {e}"
                ) from e
            return

        if source_path.is_dir():
            try:
                shutil.copytree(source_path, dest_path, dirs_exist_ok=True)
            except OSError as e:
                raise ActionError(
                    f"Failed to copy directory {source_path} to {dest_path}: {e}"
                ) from e
            return

        raise ActionError(
            f"Source is neither a file nor a directory for copy: {source_path}"
        )


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
            stderr_text = (result.stderr or "").strip()
            raise ActionError(
                f"Command failed: {' '.join(cmd)}\n"
                f"Exit code: {result.returncode}\n"
                f"Stderr: {stderr_text}"
            )
