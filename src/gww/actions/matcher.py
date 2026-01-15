"""Project action matcher for detecting project types."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from gww.config.validator import ProjectRule
from gww.template.evaluator import TemplateError, evaluate_predicate


class MatcherError(Exception):
    """Raised when project matching fails."""

    pass


def _file_exists(path: str, base_path: Path) -> bool:
    """Check if a file exists relative to base path.

    Args:
        path: Relative path to check.
        base_path: Base directory path.

    Returns:
        True if file exists.
    """
    full_path = base_path / path
    return full_path.is_file()


def _dir_exists(path: str, base_path: Path) -> bool:
    """Check if a directory exists relative to base path.

    Args:
        path: Relative path to check.
        base_path: Base directory path.

    Returns:
        True if directory exists.
    """
    full_path = base_path / path
    return full_path.is_dir()


def _path_exists(path: str, base_path: Path) -> bool:
    """Check if a path exists (file or directory) relative to base path.

    Args:
        path: Relative path to check.
        base_path: Base directory path.

    Returns:
        True if path exists.
    """
    full_path = base_path / path
    return full_path.exists()


def _create_predicate_context(
    source_path: Path,
) -> dict[str, object]:
    """Create evaluation context for project predicates.

    Args:
        source_path: Path to source repository.

    Returns:
        Dictionary of context variables and functions.
    """
    # Create bound functions for file system checks
    def file_exists(path: str) -> bool:
        return _file_exists(path, source_path)

    def dir_exists(path: str) -> bool:
        return _dir_exists(path, source_path)

    def path_exists(path: str) -> bool:
        return _path_exists(path, source_path)

    return {
        "source_path": str(source_path),
        "file_exists": file_exists,
        "dir_exists": dir_exists,
        "path_exists": path_exists,
    }


def find_matching_projects(
    rules: list[ProjectRule],
    source_path: Path,
) -> list[ProjectRule]:
    """Find all project rules that match a repository.

    Args:
        rules: List of project rules to evaluate.
        source_path: Path to source repository.

    Returns:
        List of matching ProjectRule objects.

    Raises:
        MatcherError: If predicate evaluation fails.
    """
    matching: list[ProjectRule] = []
    context = _create_predicate_context(source_path)

    for i, rule in enumerate(rules):
        try:
            if evaluate_predicate(rule.predicate, context):
                matching.append(rule)
        except TemplateError as e:
            raise MatcherError(
                f"Error evaluating predicate for project rule {i}: {e}"
            ) from e

    return matching


def get_source_actions(
    rules: list[ProjectRule],
    source_path: Path,
) -> list[tuple[str, list[str]]]:
    """Get all source actions for matching project rules.

    Args:
        rules: List of project rules to evaluate.
        source_path: Path to source repository.

    Returns:
        List of (action_type, args) tuples.

    Raises:
        MatcherError: If predicate evaluation fails.
    """
    matching = find_matching_projects(rules, source_path)

    actions: list[tuple[str, list[str]]] = []
    for rule in matching:
        for action in rule.source_actions:
            actions.append((action.action_type, action.args))

    return actions


def get_worktree_actions(
    rules: list[ProjectRule],
    source_path: Path,
) -> list[tuple[str, list[str]]]:
    """Get all worktree actions for matching project rules.

    Args:
        rules: List of project rules to evaluate.
        source_path: Path to source repository.

    Returns:
        List of (action_type, args) tuples.

    Raises:
        MatcherError: If predicate evaluation fails.
    """
    matching = find_matching_projects(rules, source_path)

    actions: list[tuple[str, list[str]]] = []
    for rule in matching:
        for action in rule.worktree_actions:
            actions.append((action.action_type, action.args))

    return actions
