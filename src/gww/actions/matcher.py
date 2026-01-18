"""Project action matcher for detecting project types."""

from __future__ import annotations

from pathlib import Path

from gww.config.validator import ProjectRule
from gww.template.evaluator import TemplateError, evaluate_predicate
from gww.template.functions import (
    TemplateContext,
    create_function_registry,
    create_project_functions,
)


class MatcherError(Exception):
    """Raised when project matching fails."""

    pass


def _create_predicate_context(
    source_path: Path,
    tags: dict[str, str] = {},
) -> dict[str, object]:
    """Create evaluation context for project predicates.

    Uses the unified FunctionRegistry for shared functions and adds
    project-specific functions (source_path, file_exists, dir_exists, path_exists).

    Args:
        source_path: Path to source repository.
        tags: Optional dictionary of tag key-value pairs.

    Returns:
        Dictionary of context functions including:
        - Shared functions: tag(), tag_exist() (URI and branch functions available but may raise if no context)
        - Project-specific functions: source_path(), file_exists(), dir_exists(), path_exists()
    """
    # Create shared functions from unified registry (tags only, no URI/branch)
    context = TemplateContext(source_path=source_path, tags=tags)
    functions: dict[str, object] = create_function_registry(context)

    # Add project-specific functions
    project_functions = create_project_functions(source_path)
    functions.update(project_functions)

    return functions


def find_matching_projects(
    rules: list[ProjectRule],
    source_path: Path,
    tags: dict[str, str] = {},
) -> list[ProjectRule]:
    """Find all project rules that match a repository.

    Args:
        rules: List of project rules to evaluate.
        source_path: Path to source repository.
        tags: Optional dictionary of tag key-value pairs.

    Returns:
        List of matching ProjectRule objects.

    Raises:
        MatcherError: If predicate evaluation fails.
    """
    matching: list[ProjectRule] = []
    context = _create_predicate_context(source_path, tags)

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
    tags: dict[str, str] = {},
) -> list[tuple[str, list[str]]]:
    """Get all source actions for matching project rules.

    Args:
        rules: List of project rules to evaluate.
        source_path: Path to source repository.
        tags: Optional dictionary of tag key-value pairs.

    Returns:
        List of (action_type, args) tuples.

    Raises:
        MatcherError: If predicate evaluation fails.
    """
    matching = find_matching_projects(rules, source_path, tags)

    actions: list[tuple[str, list[str]]] = []
    for rule in matching:
        for action in rule.source_actions:
            actions.append((action.action_type, action.args))

    return actions


def get_worktree_actions(
    rules: list[ProjectRule],
    source_path: Path,
    tags: dict[str, str] = {},
) -> list[tuple[str, list[str]]]:
    """Get all worktree actions for matching project rules.

    Args:
        rules: List of project rules to evaluate.
        source_path: Path to source repository.
        tags: Optional dictionary of tag key-value pairs.

    Returns:
        List of (action_type, args) tuples.

    Raises:
        MatcherError: If predicate evaluation fails.
    """
    matching = find_matching_projects(rules, source_path, tags)

    actions: list[tuple[str, list[str]]] = []
    for rule in matching:
        for action in rule.worktree_actions:
            actions.append((action.action_type, action.args))

    return actions
