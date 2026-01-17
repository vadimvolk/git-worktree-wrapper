"""Template function registry for path template evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from gww.utils.uri import ParsedURI


@dataclass
class TemplateContext:
    """Context for template evaluation.

    Attributes:
        uri: Parsed URI object (for clone operations).
        branch: Git branch name (for worktree operations).
        source_path: Source repository path (for worktree operations).
        tags: Dictionary of tag key-value pairs.
    """

    uri: Optional[ParsedURI] = None
    branch: Optional[str] = None
    source_path: Optional[str] = None
    tags: dict[str, str] = field(default_factory=dict)


class FunctionRegistry:
    """Registry of template functions available during evaluation."""

    def __init__(self, context: TemplateContext) -> None:
        """Initialize registry with evaluation context.

        Args:
            context: Template context with URI, branch, etc.
        """
        self._context = context
        self._functions: dict[str, Callable[..., str]] = {}
        self._register_builtin_functions()

    def _register_builtin_functions(self) -> None:
        """Register all built-in template functions."""
        self._functions["path"] = self._path
        self._functions["branch"] = self._branch
        self._functions["norm_branch"] = self._norm_branch
        self._functions["tag"] = self._tag
        self._functions["tag_exist"] = self._tag_exist

    def get_functions(self) -> dict[str, Callable[..., str]]:
        """Return dictionary of all registered functions.

        Returns:
            Dictionary mapping function names to callables.
        """
        return self._functions.copy()

    def _path(self, index: int) -> str:
        """Get URI path segment by index.

        Args:
            index: Segment index (0-based, negative for reverse).

        Returns:
            Path segment at the specified index.

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


def create_function_registry(context: TemplateContext) -> dict[str, Callable[..., Any]]:
    """Create a function registry for template evaluation.

    Args:
        context: Template context with URI, branch, etc.

    Returns:
        Dictionary of functions to pass to simpleeval.
    """
    registry = FunctionRegistry(context)
    return registry.get_functions()
