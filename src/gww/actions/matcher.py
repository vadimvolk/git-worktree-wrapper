"""Project action matcher for detecting project types."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any, Optional

from gww.config.validator import Action, ProjectRule
from gww.template.evaluator import (
    TemplateError,
    evaluate_command_template,
    evaluate_predicate,
)
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
    dest_path: Optional[Path] = None,
) -> dict[str, object]:
    """Create evaluation context for project predicates.

    Uses the unified FunctionRegistry for shared functions and adds
    project-specific functions (source_path, dest_path, file_exists, dir_exists, path_exists).

    Args:
        source_path: Path to source repository.
        tags: Optional dictionary of tag key-value pairs.
        dest_path: Optional destination path. For clone operations, this is the same
            as source_path. For add operations, this is the worktree path.

    Returns:
        Dictionary of context functions including:
        - Shared functions: tag(), tag_exist() (URI and branch functions available but may raise if no context)
        - Project-specific functions: source_path(), dest_path(), file_exists(), dir_exists(), path_exists()
    """
    # Create shared functions from unified registry (tags only, no URI/branch)
    context = TemplateContext(source_path=source_path, tags=tags)
    functions: dict[str, object] = create_function_registry(context)

    # Add project-specific functions
    project_functions = create_project_functions(source_path, dest_path)
    functions.update(project_functions)

    return functions


def _process_action(
    action: Action,
    context: dict[str, Any],
) -> tuple[str, list[str]]:
    """Process an action, evaluating command templates if needed.

    For command actions, evaluates the template functions in the command string
    and parses the result with shlex.split() for proper argument handling.

    For other action types (abs_copy, rel_copy), returns args as-is.

    Args:
        action: The action to process.
        context: Evaluation context with functions for template evaluation.

    Returns:
        Tuple of (action_type, processed_args).

    Raises:
        MatcherError: If command template evaluation fails.
    """
    if action.action_type == "command":
        # Command has single string in args[0] that may contain template functions
        command_template = action.args[0]
        try:
            evaluated_command = evaluate_command_template(command_template, context)
        except TemplateError as e:
            raise MatcherError(
                f"Error evaluating command template '{command_template}': {e}"
            ) from e

        # Parse the evaluated command string with shlex for proper argument handling
        try:
            parsed_args = shlex.split(evaluated_command)
        except ValueError as e:
            raise MatcherError(
                f"Error parsing command '{evaluated_command}': {e}"
            ) from e

        return (action.action_type, parsed_args)
    else:
        # For abs_copy and rel_copy, return args as-is
        return (action.action_type, action.args)


def find_matching_projects(
    rules: list[ProjectRule],
    source_path: Path,
    tags: dict[str, str] = {},
    dest_path: Optional[Path] = None,
) -> list[ProjectRule]:
    """Find all project rules that match a repository.

    Args:
        rules: List of project rules to evaluate.
        source_path: Path to source repository.
        tags: Optional dictionary of tag key-value pairs.
        dest_path: Optional destination path. For clone operations, this is the same
            as source_path. For add operations, this is the worktree path.

    Returns:
        List of matching ProjectRule objects.

    Raises:
        MatcherError: If predicate evaluation fails.
    """
    matching: list[ProjectRule] = []
    context = _create_predicate_context(source_path, tags, dest_path)

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
    dest_path: Optional[Path] = None,
) -> list[tuple[str, list[str]]]:
    """Get all source actions for matching project rules.

    For command actions, evaluates template functions in the command string
    and parses with shlex.split() for proper argument handling.

    Args:
        rules: List of project rules to evaluate.
        source_path: Path to source repository.
        tags: Optional dictionary of tag key-value pairs.
        dest_path: Optional destination path. For clone operations, this should be
            the same as source_path (the cloned repository location).

    Returns:
        List of (action_type, args) tuples. Command actions have their templates
        evaluated and parsed into separate arguments.

    Raises:
        MatcherError: If predicate evaluation or command template evaluation fails.
    """
    context = _create_predicate_context(source_path, tags, dest_path)
    matching = find_matching_projects(rules, source_path, tags, dest_path)

    actions: list[tuple[str, list[str]]] = []
    for rule in matching:
        for action in rule.after_clone:
            actions.append(_process_action(action, context))

    return actions


def get_worktree_actions(
    rules: list[ProjectRule],
    source_path: Path,
    tags: dict[str, str] = {},
    dest_path: Optional[Path] = None,
) -> list[tuple[str, list[str]]]:
    """Get all worktree actions for matching project rules.

    For command actions, evaluates template functions in the command string
    and parses with shlex.split() for proper argument handling.

    Args:
        rules: List of project rules to evaluate.
        source_path: Path to source repository.
        tags: Optional dictionary of tag key-value pairs.
        dest_path: Optional destination path. For add operations, this should be
            the worktree path.

    Returns:
        List of (action_type, args) tuples. Command actions have their templates
        evaluated and parsed into separate arguments.

    Raises:
        MatcherError: If predicate evaluation or command template evaluation fails.
    """
    context = _create_predicate_context(source_path, tags, dest_path)
    matching = find_matching_projects(rules, source_path, tags, dest_path)

    actions: list[tuple[str, list[str]]] = []
    for rule in matching:
        for action in rule.after_add:
            actions.append(_process_action(action, context))

    return actions
