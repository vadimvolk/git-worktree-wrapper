"""Template function registry for path template evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Union

from gww.utils.uri import ParsedURI


@dataclass
class TemplateContext:
    """Context for template evaluation.

    Attributes:
        uri: Parsed URI object (for clone operations).
        branch: Git branch name (for worktree operations).
        source_path: Source repository path (for project predicates).
        tags: Dictionary of tag key-value pairs.
    """

    uri: Optional[ParsedURI] = None
    branch: Optional[str] = None
    source_path: Optional[Path] = None
    tags: dict[str, str] = field(default_factory=dict)


class FunctionRegistry:
    """Registry of template functions available during evaluation.

    Provides shared functions available in templates, URI predicates, and project predicates:
    - URI functions: host(), port(), protocol(), uri(), path(), path(index)
    - Branch functions: branch(), norm_branch(replacement)
    - Tag functions: tag(name), tag_exist(name)
    """

    def __init__(self, context: TemplateContext) -> None:
        """Initialize registry with evaluation context.

        Args:
            context: Template context with URI, branch, etc.
        """
        self._context = context
        self._functions: dict[str, Callable[..., Any]] = {}
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

    def _path(self, *args: int) -> Union[list[str], str]:
        """Get URI path segment(s).

        With no arguments: returns list of all path segments.
        With index argument: returns single path segment at index.

        Args:
            *args: Optional index (0-based, negative for reverse).

        Returns:
            List of path segments (no args) or single segment string (with index).

        Raises:
            ValueError: If no URI context or index out of range.
        """
        if self._context.uri is None:
            raise ValueError("No URI context available for path() function")

        if len(args) == 0:
            # path() with no args returns list of all segments
            return self._context.uri.path_segments
        else:
            # path(index) returns single segment
            index = args[0]
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


def create_function_registry(context: TemplateContext) -> dict[str, Callable[..., Any]]:
    """Create a function registry for template evaluation.

    Args:
        context: Template context with URI, branch, etc.

    Returns:
        Dictionary of functions to pass to simpleeval.
    """
    registry = FunctionRegistry(context)
    return registry.get_functions()


def create_project_functions(source_path: Path) -> dict[str, Callable[..., Any]]:
    """Create project-specific functions for project predicate evaluation.

    These functions are only available in project predicates, not in templates
    or URI predicates.

    Args:
        source_path: Path to source repository.

    Returns:
        Dictionary of project-specific functions.
    """

    def _source_path() -> str:
        """Get absolute path to source repository."""
        return str(source_path)

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
        "file_exists": _file_exists,
        "dir_exists": _dir_exists,
        "path_exists": _path_exists,
    }
