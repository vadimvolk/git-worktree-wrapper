"""Template function registry for path template evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from gww.utils.uri import ParsedURI


@dataclass
class TemplateContext:
    """Context for template evaluation.

    The same context object feeds every evaluation site that uses the unified
    function registry: source-rule ``when`` predicates, ``default_sources``
    and ``default_worktrees`` path templates, and project-rule ``when``
    predicates plus their command templates.

    Attributes:
        uri: Parsed URI object. Populated for ``clone`` (from CLI) and for
            ``add`` (from the source repo's ``origin`` remote — *not* the
            original clone URL if the user later changed remotes).
        branch: Git branch name. For ``add``, the user-supplied branch. For
            ``clone``, the branch git checked out by default (the remote's
            HEAD) after the clone operation completes; ``""`` if HEAD is
            detached.
        source_path: Source repository path. Always set for project-rule
            predicates; feeds the ``source_path(extra?)`` template function
            and the ``file_exists``/``dir_exists``/``path_exists`` helpers.
        dest_path: Destination path for project-rule actions — the worktree
            path for ``after_add`` and ``before_remove``, the source path
            for ``after_clone``. Feeds the ``current_worktree(extra?)``
            template function. ``None`` in non-project evaluation sites
            (URI predicates, path templates).
        tags: Dictionary of tag key-value pairs from the CLI.
    """

    uri: Optional[ParsedURI] = None
    branch: Optional[str] = None
    source_path: Optional[Path] = None
    dest_path: Optional[Path] = None
    tags: dict[str, str] = field(default_factory=dict)


class FunctionRegistry:
    """Registry of template functions available during evaluation.

    Provides shared functions available in templates, URI predicates, and project predicates:
    - URI functions: host(), port(), protocol(), uri(), path(index)
    - Branch functions: branch(), norm_branch(replacement)
    - Tag functions: tag(name), tag_exist(name)

    Template-only functions (not available in predicates):
    - Utility functions: time_id(fmt) - generates datetime-based identifier strings
    """

    def __init__(self, context: TemplateContext) -> None:
        """Initialize registry with evaluation context.

        Args:
            context: Template context with URI, branch, etc.
        """
        self._context = context
        self._functions: dict[str, Callable[..., Any]] = {}
        self._cached_datetime: Optional[datetime] = None
        self._register_builtin_functions()

    def _register_builtin_functions(self) -> None:
        """Register all built-in template functions."""
        # URI functions
        self._functions["host"] = self._host
        self._functions["port"] = self._port
        self._functions["protocol"] = self._protocol
        self._functions["uri"] = self._uri
        self._functions["path"] = self._path
        # Branch functions
        self._functions["branch"] = self._branch
        self._functions["norm_branch"] = self._norm_branch
        # Tag functions
        self._functions["tag"] = self._tag
        self._functions["tag_exist"] = self._tag_exist
        # Utility functions (template-only)
        self._functions["time_id"] = self._time_id

    def get_functions(self) -> dict[str, Callable[..., Any]]:
        """Return dictionary of all registered functions.

        Returns:
            Dictionary mapping function names to callables.
        """
        return self._functions.copy()

    # --- URI Functions ---

    def _host(self) -> str:
        """Get URI hostname.

        Returns:
            Hostname from URI (e.g., "github.com").

        Raises:
            ValueError: If no URI context available.
        """
        if self._context.uri is None:
            raise ValueError("No URI context available for host() function")
        return self._context.uri.host

    def _port(self) -> str:
        """Get URI port.

        Returns:
            Port from URI, empty string if not specified.

        Raises:
            ValueError: If no URI context available.
        """
        if self._context.uri is None:
            raise ValueError("No URI context available for port() function")
        return self._context.uri.port

    def _protocol(self) -> str:
        """Get URI protocol/scheme.

        Returns:
            Protocol from URI (e.g., "https", "ssh", "git").

        Raises:
            ValueError: If no URI context available.
        """
        if self._context.uri is None:
            raise ValueError("No URI context available for protocol() function")
        return self._context.uri.protocol

    def _uri(self) -> str:
        """Get full URI string.

        Returns:
            Full URI string.

        Raises:
            ValueError: If no URI context available.
        """
        if self._context.uri is None:
            raise ValueError("No URI context available for uri() function")
        return self._context.uri.uri

    def _path(self, index: int) -> str:
        """Get URI path segment by index.

        Args:
            index: Path segment index (0-based, negative for reverse).
                   Example: path(-1) returns last segment, path(0) returns first.

        Returns:
            Path segment string at the specified index.

        Raises:
            ValueError: If no URI context or index out of range.
        """
        if self._context.uri is None:
            raise ValueError("No URI context available for path() function")

        try:
            return self._context.uri.path(index)
        except IndexError:
            raise ValueError(
                f"Path segment index {index} out of range. "
                f"Available segments: {self._context.uri.path_segments}"
            )

    def _branch(self) -> str:
        """Get current branch name as-is.

        Returns:
            Branch name.

        Raises:
            ValueError: If no branch context available.
        """
        if self._context.branch is None:
            raise ValueError("No branch context available for branch() function")
        return self._context.branch

    def _norm_branch(self, replacement: str = "-") -> str:
        """Get branch name with '/' replaced.

        Args:
            replacement: Character to replace '/' with (default: '-').

        Returns:
            Normalized branch name.

        Raises:
            ValueError: If no branch context available.
        """
        if self._context.branch is None:
            raise ValueError("No branch context available for norm_branch() function")
        return self._context.branch.replace("/", replacement)

    def _tag(self, name: str) -> str:
        """Get tag value by name.

        Args:
            name: Tag name.

        Returns:
            Tag value if tag exists with a value, empty string otherwise.
        """
        return self._context.tags.get(name, "")

    def _tag_exist(self, name: str) -> bool:
        """Check if tag exists.

        Args:
            name: Tag name.

        Returns:
            True if tag exists (with or without value), False otherwise.
        """
        return name in self._context.tags

    # --- Utility Functions ---

    def _time_id(self, fmt: str = "%Y%m%d-%H%M.%S") -> str:
        """Generate a datetime-based identifier string.

        The datetime is captured on first call and cached for subsequent calls
        within the same template evaluation session. This ensures consistent
        timestamps when time_id() is called multiple times with different formats.

        Args:
            fmt: Optional strftime format string. If not provided, uses default
                 format "%Y%m%d-%H%M.%S" (e.g., "20260120-2134.03").

        Returns:
            Formatted datetime string.
        """
        if self._cached_datetime is None:
            self._cached_datetime = datetime.now()

        return self._cached_datetime.strftime(fmt)


def create_function_registry(context: TemplateContext) -> dict[str, Callable[..., Any]]:
    """Create a function registry for template evaluation.

    Args:
        context: Template context with URI, branch, etc.

    Returns:
        Dictionary of functions to pass to simpleeval.
    """
    registry = FunctionRegistry(context)
    return registry.get_functions()


def create_project_functions(
    context: TemplateContext,
) -> dict[str, Callable[..., Any]]:
    """Create project-specific functions for project predicate evaluation.

    These functions are only available in project predicates, not in templates
    or URI predicates. The path-bearing helpers follow a fixed mapping that
    does not vary by operation (ADR-0012 §"Uniform semantics across
    operations"):

    * ``source_path(extra?)`` is ``context.source_path`` (optionally joined
      with ``extra``).
    * ``current_worktree(extra?)`` is ``context.dest_path`` (optionally joined
      with ``extra``).

    Neither function aliases the other under any condition. They may resolve
    to the same path string during ``gww clone`` because the CLI populates
    *both* context fields with the clone target, but that is a CLI-side
    property of how the calling command populates the context — never an
    aliasing inside the helper itself.

    Args:
        context: Template context whose ``source_path`` and ``dest_path`` are
            used by the returned functions. ``source_path`` must be set;
            ``dest_path`` is required for ``current_worktree()`` to evaluate
            and raises ``ValueError`` when ``None``.

    Returns:
        Dictionary of project-specific functions.

    Raises:
        ValueError: If ``context.source_path`` is ``None``.
    """
    if context.source_path is None:
        raise ValueError(
            "create_project_functions requires context.source_path"
        )
    source_path = context.source_path
    dest_path = context.dest_path

    def _source_path(extra: str = "") -> str:
        """Get absolute path to source repository, optionally joined with ``extra``.

        Args:
            extra: Path segment to append to the source repository root. An
                empty string returns the bare source path.

        Returns:
            Absolute, resolved path to the source repository (or the joined
            path when ``extra`` is non-empty).
        """
        return str((source_path / extra).resolve())

    def _current_worktree(extra: str = "") -> str:
        """Get absolute path to the current worktree, optionally joined with ``extra``.

        Args:
            extra: Path segment to append to the worktree root. An empty
                string returns the bare worktree path.

        Returns:
            Absolute, resolved path to the worktree (or the joined path when
            ``extra`` is non-empty).

        Raises:
            ValueError: If ``context.dest_path`` is ``None``. The function
                does not fall back to ``source_path()`` — that would re-
                introduce the per-operation aliasing the uniform-mapping
                principle rules out (ADR-0012).
        """
        if dest_path is None:
            raise ValueError(
                "current_worktree() requires context.dest_path"
            )
        return str((dest_path / extra).resolve())

    def _file_exists(path: str) -> bool:
        """Check if a file exists relative to source repository.

        Args:
            path: Relative path to check.

        Returns:
            True if file exists.
        """
        full_path = source_path / path
        return full_path.is_file()

    def _dir_exists(path: str) -> bool:
        """Check if a directory exists relative to source repository.

        Args:
            path: Relative path to check.

        Returns:
            True if directory exists.
        """
        full_path = source_path / path
        return full_path.is_dir()

    def _path_exists(path: str) -> bool:
        """Check if a path exists (file or directory) relative to source repository.

        Args:
            path: Relative path to check.

        Returns:
            True if path exists.
        """
        full_path = source_path / path
        return full_path.exists()

    return {
        "source_path": _source_path,
        "current_worktree": _current_worktree,
        "file_exists": _file_exists,
        "dir_exists": _dir_exists,
        "path_exists": _path_exists,
    }
