"""Project action executor for abs_copy, rel_copy, and command actions."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional


class ActionError(Exception):
    """Raised when an action fails to execute."""

    pass


def _expand_path(path: str) -> Path:
    """Expand ~ in path and resolve to absolute.

    Args:
        path: Path string that may contain ~.

    Returns:
        Expanded and resolved Path.
    """
    return Path(path).expanduser().resolve()


def execute_abs_copy(
    source: str,
    destination: str,
    target_dir: Path,
) -> None:
    """Execute an absolute copy action.

    Copies a file from an absolute source path to a relative destination
    in the target directory.

    Args:
        source: Absolute source file path.
        destination: Relative destination path from target_dir.
        target_dir: Target directory (source repo or worktree).

    Raises:
        ActionError: If copy fails.
    """
    source_path = _expand_path(source)
    dest_path = target_dir / destination

    if not source_path.exists():
        raise ActionError(f"Source file not found for abs_copy: {source_path}")

    if not source_path.is_file():
        raise ActionError(f"Source is not a file for abs_copy: {source_path}")

    # Ensure destination directory exists
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        shutil.copy2(source_path, dest_path)
    except OSError as e:
        raise ActionError(f"Failed to copy {source_path} to {dest_path}: {e}") from e


def execute_rel_copy(
    source: str,
    destination: Optional[str],
    source_dir: Path,
    target_dir: Path,
) -> None:
    """Execute a relative copy action.

    Copies a file from source repository to worktree (relative paths).

    Args:
        source: Relative source path from source_dir.
        destination: Relative destination path (defaults to same as source).
        source_dir: Source repository path.
        target_dir: Target worktree path.

    Raises:
        ActionError: If copy fails.
    """
    source_path = source_dir / source
    dest_path = target_dir / (destination or source)

    if not source_path.exists():
        raise ActionError(f"Source file not found for rel_copy: {source_path}")

    if not source_path.is_file():
        raise ActionError(f"Source is not a file for rel_copy: {source_path}")

    # Ensure destination directory exists
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        shutil.copy2(source_path, dest_path)
    except OSError as e:
        raise ActionError(f"Failed to copy {source_path} to {dest_path}: {e}") from e


def execute_command(
    command: str,
    args: list[str],
    working_dir: Path,
) -> None:
    """Execute a command action.

    Commands always execute with dest_path as the current working directory:
    - For clone operations: working_dir is the cloned repository path
    - For add operations: working_dir is the new worktree path

    Args:
        command: Command to execute.
        args: Command arguments.
        working_dir: Working directory for command (always dest_path).

    Raises:
        ActionError: If command fails.
    """
    cmd = [command] + args

    try:
        result = subprocess.run(
            cmd,
            cwd=working_dir,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise ActionError(
                f"Command failed: {' '.join(cmd)}\n"
                f"Exit code: {result.returncode}\n"
                f"Stderr: {result.stderr.strip()}"
            )
    except FileNotFoundError:
        raise ActionError(f"Command not found: {command}")
    except OSError as e:
        raise ActionError(f"Failed to execute command: {e}") from e


def execute_action(
    action_type: str,
    args: list[str],
    source_dir: Optional[Path],
    target_dir: Path,
) -> None:
    """Execute a single action.

    Args:
        action_type: One of "abs_copy", "rel_copy", "command".
        args: Action arguments.
        source_dir: Source repository path (required for rel_copy).
        target_dir: Target directory (source repo for source_actions, worktree for worktree_actions).

    Raises:
        ActionError: If action fails.
        ValueError: If action type is invalid.
    """
    if action_type == "abs_copy":
        if len(args) < 2:
            raise ActionError("abs_copy requires source and destination arguments")
        execute_abs_copy(args[0], args[1], target_dir)

    elif action_type == "rel_copy":
        if len(args) < 1:
            raise ActionError("rel_copy requires at least source argument")
        if source_dir is None:
            raise ActionError("rel_copy requires source_dir")
        destination = args[1] if len(args) > 1 else None
        execute_rel_copy(args[0], destination, source_dir, target_dir)

    elif action_type == "command":
        if len(args) < 1:
            raise ActionError("command requires at least command name")
        execute_command(args[0], args[1:], target_dir)

    else:
        raise ValueError(f"Unknown action type: {action_type}")


def execute_actions(
    actions: list[tuple[str, list[str]]],
    source_dir: Optional[Path],
    target_dir: Path,
) -> int:
    """Execute a list of actions.

    Args:
        actions: List of (action_type, args) tuples.
        source_dir: Source repository path (for rel_copy).
        target_dir: Target directory for actions.

    Returns:
        Number of actions executed successfully.

    Raises:
        ActionError: If any action fails (stops on first failure).
    """
    count = 0
    for action_type, args in actions:
        execute_action(action_type, args, source_dir, target_dir)
        count += 1
    return count
