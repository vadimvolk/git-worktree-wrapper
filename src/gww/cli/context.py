"""Shared CLI command context: tag parsing, config loading, source resolution.

This module collects the boilerplate that every command used to inline:

* :class:`CommandContext` — small dataclass carrying the per-invocation state
  (``verbose``, ``quiet``, ``tags``) plus command-specific fields (URI,
  branch, …) that was previously pulled off ``argparse.Namespace`` with
  ``getattr`` calls.
* :class:`CommandExit` — control-flow exception used by ``…_or_exit``
  helpers to abort a command with a specific exit code.
* :func:`exit_on_error` — decorator that turns :class:`CommandExit` raised
  inside a command into a printed error + return-code, preserving the
  contract that ``run_<command>(ctx) -> int``.
* :func:`parse_tags` — turn a list of ``"key=value"`` strings into a dict.
* :func:`parse_uri_or_exit` — parse and validate a repository URI.
* :func:`load_config_or_exit` — load + validate the gww config, raising
  :class:`CommandExit(2, ...)` on any failure so callers do not have to repeat
  the tri-except pattern.
* :func:`resolve_source_repo_or_exit` — detect the current repo, walk from a
  worktree back to its source, and return ``(source_path, remote_uri)``. Raises
  :class:`CommandExit(1, ...)` on any failure so callers do not have to repeat
  the detect-or-walk pattern.
* :func:`resolve_source_repo` — same detect-or-walk pattern, but without the
  remote-origin requirement. Used by commands that only need the source path
  (e.g. ``pull``).

Commands still own their own control flow. They raise :class:`CommandExit`
when they want to bail out with a specific exit code; the ``@exit_on_error``
decorator on the public ``run_<command>`` entry points converts that exception
into the return code that the old ``return N`` pattern used to produce.
"""

from __future__ import annotations

import argparse
import functools
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

from gww.config.loader import ConfigLoadError, ConfigNotFoundError, load_config
from gww.config.validator import Config, ConfigValidationError, validate_config
from gww.git.repository import (
    GitCommandError,
    NotGitRepositoryError,
    detect_repository,
    get_source_repository,
)
from gww.utils.uri import ParsedURI, parse_uri


_F = TypeVar("_F", bound=Callable[..., Any])


def exit_on_error(func: _F) -> _F:
    """Decorator that converts :class:`CommandExit` into a return code.

    The command's body can freely ``raise CommandExit(code, message)``;
    the wrapper prints ``message`` to stderr and returns ``code``. Any
    other exception propagates unchanged so the global handler in
    :func:`gww.cli.main:main` (or the test framework) sees it.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> int:
        try:
            result = func(*args, **kwargs)
        except CommandExit as e:
            if e.message:
                print(e.message, file=sys.stderr)
            return e.code
        return int(result)

    return wrapper  # type: ignore[return-value]


class CommandExit(Exception):
    """Raised when a command needs to terminate early with a specific exit code.

    Attributes:
        code: Exit code to return from the CLI. ``1`` for a runtime error,
            ``2`` for a configuration error.
        message: Human-readable error message. Written to stderr by
            :func:`gww.cli.main:main` before the process exits.
    """

    def __init__(self, code: int, message: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def parse_tags(tag_args: Optional[list[str]]) -> dict[str, str]:
    """Parse ``--tag key=value`` arguments into a dictionary.

    Args:
        tag_args: List of tag strings in format ``"key=value"`` or ``"key"``.

    Returns:
        Dictionary mapping tag keys to values (empty string if no value).
    """
    tags: dict[str, str] = {}
    for tag_arg in tag_args or []:
        if "=" in tag_arg:
            key, value = tag_arg.split("=", 1)
            tags[key] = value
        else:
            tags[tag_arg] = ""
    return tags


def parse_uri_or_exit(uri_str: str) -> ParsedURI:
    """Parse a repository URI, raising :class:`CommandExit` on failure.

    Args:
        uri_str: Raw URI string from the command line.

    Returns:
        Validated :class:`ParsedURI` object.

    Raises:
        CommandExit: With code ``1`` if the URI is malformed.
    """
    try:
        return parse_uri(uri_str)
    except ValueError as e:
        raise CommandExit(1, f"Error: Invalid repository URI: {e}") from e


@dataclass
class CommandContext:
    """Per-invocation context shared by all CLI commands.

    Replaces the ``getattr(args, "verbose", 0)`` / ``getattr(args, "quiet", False)``
    pattern with a typed container. Built once from the parsed
    :class:`argparse.Namespace` and threaded into helpers and commands.

    Command-specific fields (``uri``, ``branch``, ``branch_or_path``, …) are
    optional and only populated for the commands that need them.

    Attributes:
        verbose: Verbosity level (``-v`` count).
        quiet: Whether to suppress non-error output (``-q``).
        tags: Tag key-value pairs from ``--tag`` options.
        uri: Source URI string (clone command).
        branch: Branch name (add command).
        branch_or_path: Branch name or worktree path (remove command).
        create_branch: Whether to create the branch if missing (add command).
        force: Whether to force the operation past safety checks.
        old_repos: Source directories to scan for migration (migrate command).
        dry_run: Whether to only report what would happen (migrate command).
        inplace: Whether to move in place instead of copying (migrate command).
        init_command: ``"config"`` or ``"shell"`` for ``gww init``.
        shell: Shell name for ``gww init shell``.
    """

    verbose: int = 0
    quiet: bool = False
    tags: dict[str, str] = field(default_factory=dict)
    uri: Optional[str] = None
    branch: Optional[str] = None
    branch_or_path: Optional[str] = None
    create_branch: bool = False
    force: bool = False
    old_repos: list[str] = field(default_factory=list)
    dry_run: bool = False
    inplace: bool = False
    init_command: Optional[str] = None
    shell: Optional[str] = None

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> CommandContext:
        """Build a :class:`CommandContext` from parsed argparse args.

        Args:
            args: Parsed command-line arguments.

        Returns:
            Populated context.
        """
        old_repos_raw = getattr(args, "old_repos", None) or []
        if isinstance(old_repos_raw, str):
            old_repos = [old_repos_raw]
        else:
            old_repos = list(old_repos_raw)
        return cls(
            verbose=getattr(args, "verbose", 0),
            quiet=getattr(args, "quiet", False),
            tags=parse_tags(getattr(args, "tag", None)),
            uri=getattr(args, "uri", None),
            branch=getattr(args, "branch", None),
            branch_or_path=getattr(args, "branch_or_path", None),
            create_branch=getattr(args, "create_branch", False),
            force=getattr(args, "force", False),
            old_repos=old_repos,
            dry_run=getattr(args, "dry_run", False),
            inplace=getattr(args, "inplace", False),
            init_command=getattr(args, "init_command", None),
            shell=getattr(args, "shell", None),
        )

    def say(self, message: str) -> None:
        """Print a status message unless quiet mode is set.

        Args:
            message: Message to write to stdout.
        """
        if not self.quiet:
            print(message)

    def verbose_msg(self, message: str) -> None:
        """Print a verbose status message.

        Args:
            message: Message to write to stderr (only when ``verbose > 0``).
        """
        if self.verbose > 0 and not self.quiet:
            print(message, file=sys.stderr)


def load_config_or_exit() -> Config:
    """Load and validate the gww configuration.

    Returns:
        Validated :class:`Config` object.

    Raises:
        CommandExit: With code ``2`` if the config is missing, malformed, or
            fails validation.
    """
    try:
        raw_config = load_config()
    except ConfigNotFoundError as e:
        raise CommandExit(
            2,
            "Error: Config file not found. Run 'gww init config' to create one.",
        ) from e
    except ConfigLoadError as e:
        raise CommandExit(2, f"Error: {e}") from e

    try:
        return validate_config(raw_config)
    except ConfigValidationError as e:
        raise CommandExit(2, f"Config validation error: {e}") from e


def resolve_source_repo_or_exit(cwd: Path) -> tuple[Path, str]:
    """Detect the repo at ``cwd`` and walk back to its source.

    If ``cwd`` is inside a worktree, the source (main) repository path is
    returned along with that source repo's remote URI. If ``cwd`` is inside a
    source repository, that path and its remote URI are returned.

    Args:
        cwd: Directory to start the detection from.

    Returns:
        Tuple of ``(source_path, remote_uri)``.

    Raises:
        CommandExit: With code ``1`` if ``cwd`` is not in a git repository, the
            source cannot be found, or the repo has no remote ``origin``.
    """
    try:
        repo = detect_repository(cwd)
    except NotGitRepositoryError as e:
        raise CommandExit(1, "Error: Not in a git repository.") from e

    if repo.is_worktree:
        try:
            source_path = get_source_repository(repo.path)
        except (NotGitRepositoryError, GitCommandError) as e:
            raise CommandExit(1, f"Error finding source repository: {e}") from e
    else:
        source_path = repo.path

    if not repo.remote_uri:
        raise CommandExit(
            1,
            "Error: Repository has no remote origin. "
            "Cannot determine worktree path.",
        )

    return source_path, repo.remote_uri


def resolve_source_repo(cwd: Path) -> Path:
    """Detect repo at ``cwd`` and walk back to its source.

    Unlike :func:`resolve_source_repo_or_exit` this helper does not require
    a remote origin — it returns the source path regardless of remote state.
    Used by commands that operate on the local source (e.g. ``pull``).

    Args:
        cwd: Directory to start the detection from.

    Returns:
        Path to the source repository.

    Raises:
        CommandExit: With code ``1`` if ``cwd`` is not in a git repository or
            the source repo cannot be found.
    """
    try:
        repo = detect_repository(cwd)
    except NotGitRepositoryError as e:
        raise CommandExit(1, "Error: Not in a git repository.") from e

    if repo.is_worktree:
        try:
            return get_source_repository(repo.path)
        except (NotGitRepositoryError, GitCommandError) as e:
            raise CommandExit(1, f"Error finding source repository: {e}") from e
    return repo.path