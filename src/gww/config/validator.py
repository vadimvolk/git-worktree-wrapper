"""Configuration validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


class ConfigValidationError(Exception):
    """Raised when config validation fails."""

    pass


@dataclass
class SourceRule:
    """Validated source routing rule.

    Attributes:
        name: Rule name/identifier.
        predicate: Expression evaluated against URI context.
        sources: Template string for source checkout location.
        worktrees: Template string for worktree location.
    """

    name: str
    predicate: str
    sources: Optional[str] = None
    worktrees: Optional[str] = None


@dataclass
class Action:
    """Validated project action.

    Attributes:
        action_type: One of "abs_copy", "rel_copy", "command".
        args: Action arguments.
    """

    action_type: str
    args: list[str]


@dataclass
class ProjectRule:
    """Validated project detection rule.

    Attributes:
        predicate: Expression evaluated against repository filesystem.
        source_actions: Actions executed after source checkout.
        worktree_actions: Actions executed when worktree is added.
    """

    predicate: str
    source_actions: list[Action] = field(default_factory=list)
    worktree_actions: list[Action] = field(default_factory=list)


@dataclass
class Config:
    """Validated configuration.

    Attributes:
        default_sources: Template string for default source location.
        default_worktrees: Template string for default worktree location.
        sources: Named source routing rules.
        projects: Project detection and action rules.
    """

    default_sources: str
    default_worktrees: str
    sources: dict[str, SourceRule] = field(default_factory=dict)
    projects: list[ProjectRule] = field(default_factory=list)


def _validate_string(value: Any, field_name: str) -> str:
    """Validate that value is a non-empty string.

    Args:
        value: Value to validate.
        field_name: Name of the field for error messages.

    Returns:
        Validated string.

    Raises:
        ConfigValidationError: If validation fails.
    """
    if not isinstance(value, str):
        raise ConfigValidationError(
            f"Field '{field_name}' must be a string, got {type(value).__name__}"
        )
    if not value.strip():
        raise ConfigValidationError(f"Field '{field_name}' cannot be empty")
    return value


def _validate_action(action_data: Any, context: str) -> Action:
    """Validate and parse a single action.

    Args:
        action_data: Action data from config (dict with single key).
        context: Context string for error messages.

    Returns:
        Validated Action object.

    Raises:
        ConfigValidationError: If validation fails.
    """
    if not isinstance(action_data, dict):
        raise ConfigValidationError(
            f"{context}: action must be a mapping, got {type(action_data).__name__}"
        )

    if len(action_data) != 1:
        raise ConfigValidationError(
            f"{context}: action must have exactly one key (action type)"
        )

    action_type = list(action_data.keys())[0]
    args = action_data[action_type]

    valid_types = {"abs_copy", "rel_copy", "command"}
    if action_type not in valid_types:
        raise ConfigValidationError(
            f"{context}: invalid action type '{action_type}'. "
            f"Must be one of: {', '.join(sorted(valid_types))}"
        )

    if isinstance(args, str):
        args = [args]
    elif not isinstance(args, list):
        raise ConfigValidationError(
            f"{context}: action arguments must be a string or list"
        )

    # Validate args are strings
    for i, arg in enumerate(args):
        if not isinstance(arg, str):
            raise ConfigValidationError(
                f"{context}: argument {i} must be a string, got {type(arg).__name__}"
            )

    return Action(action_type=action_type, args=list(args))


def _validate_source_rule(name: str, data: Any) -> SourceRule:
    """Validate and parse a source routing rule.

    Args:
        name: Rule name.
        data: Rule data from config.

    Returns:
        Validated SourceRule object.

    Raises:
        ConfigValidationError: If validation fails.
    """
    if not isinstance(data, dict):
        raise ConfigValidationError(
            f"Source rule '{name}' must be a mapping, got {type(data).__name__}"
        )

    if "predicate" not in data:
        raise ConfigValidationError(f"Source rule '{name}' missing required 'predicate'")

    predicate = _validate_string(data["predicate"], f"sources.{name}.predicate")

    sources = None
    if "sources" in data:
        sources = _validate_string(data["sources"], f"sources.{name}.sources")

    worktrees = None
    if "worktrees" in data:
        worktrees = _validate_string(data["worktrees"], f"sources.{name}.worktrees")

    return SourceRule(
        name=name,
        predicate=predicate,
        sources=sources,
        worktrees=worktrees,
    )


def _validate_project_rule(data: Any, index: int) -> ProjectRule:
    """Validate and parse a project detection rule.

    Args:
        data: Rule data from config.
        index: Index for error messages.

    Returns:
        Validated ProjectRule object.

    Raises:
        ConfigValidationError: If validation fails.
    """
    context = f"projects[{index}]"

    if not isinstance(data, dict):
        raise ConfigValidationError(
            f"{context} must be a mapping, got {type(data).__name__}"
        )

    if "predicate" not in data:
        raise ConfigValidationError(f"{context} missing required 'predicate'")

    predicate = _validate_string(data["predicate"], f"{context}.predicate")

    source_actions: list[Action] = []
    if "source_actions" in data:
        actions_data = data["source_actions"]
        if not isinstance(actions_data, list):
            raise ConfigValidationError(f"{context}.source_actions must be a list")
        for i, action_data in enumerate(actions_data):
            action = _validate_action(action_data, f"{context}.source_actions[{i}]")
            source_actions.append(action)

    worktree_actions: list[Action] = []
    if "worktree_actions" in data:
        actions_data = data["worktree_actions"]
        if not isinstance(actions_data, list):
            raise ConfigValidationError(f"{context}.worktree_actions must be a list")
        for i, action_data in enumerate(actions_data):
            action = _validate_action(action_data, f"{context}.worktree_actions[{i}]")
            worktree_actions.append(action)

    if not source_actions and not worktree_actions:
        raise ConfigValidationError(
            f"{context} must have at least one of: source_actions, worktree_actions"
        )

    return ProjectRule(
        predicate=predicate,
        source_actions=source_actions,
        worktree_actions=worktree_actions,
    )


def validate_config(data: dict[str, Any]) -> Config:
    """Validate and parse configuration data.

    Args:
        data: Raw configuration dictionary from YAML.

    Returns:
        Validated Config object.

    Raises:
        ConfigValidationError: If validation fails.
    """
    # Validate required fields
    if "default_sources" not in data:
        raise ConfigValidationError("Missing required field: default_sources")
    if "default_worktrees" not in data:
        raise ConfigValidationError("Missing required field: default_worktrees")

    default_sources = _validate_string(data["default_sources"], "default_sources")
    default_worktrees = _validate_string(data["default_worktrees"], "default_worktrees")

    # Validate optional sources
    sources: dict[str, SourceRule] = {}
    if "sources" in data:
        sources_data = data["sources"]
        if not isinstance(sources_data, dict):
            raise ConfigValidationError(
                f"'sources' must be a mapping, got {type(sources_data).__name__}"
            )
        for name, rule_data in sources_data.items():
            sources[name] = _validate_source_rule(name, rule_data)

    # Validate optional projects
    projects: list[ProjectRule] = []
    if "projects" in data:
        projects_data = data["projects"]
        if not isinstance(projects_data, list):
            raise ConfigValidationError(
                f"'projects' must be a list, got {type(projects_data).__name__}"
            )
        for i, rule_data in enumerate(projects_data):
            projects.append(_validate_project_rule(rule_data, i))

    return Config(
        default_sources=default_sources,
        default_worktrees=default_worktrees,
        sources=sources,
        projects=projects,
    )
