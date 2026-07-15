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
        when: Expression evaluated against URI context.
        sources: Template string for source checkout location.
        worktrees: Template string for worktree location.
    """

    name: str
    when: str
    sources: Optional[str] = None
    worktrees: Optional[str] = None


@dataclass
class Action:
    """Validated project action.

    Attributes:
        action_type: One of "copy", "command".
        args: Action arguments.
    """

    action_type: str
    args: list[str]


@dataclass
class ProjectRule:
    """Validated project detection rule.

    Attributes:
        when: Expression evaluated against the :class:`TemplateContext`
            populated by the calling command (``clone``, ``add``, or
            ``remove``). Sees URI, branch, tags, source path, and
            destination path.
        after_clone: Actions executed after source checkout.
        after_add: Actions executed when worktree is added.
        before_remove: Actions executed before a worktree is removed by
            ``gww remove``. Allows cleanup (archive, notify, stash) before
            ``git worktree remove`` deletes the worktree. ADR-0011.
        critical: Whether failures in this rule abort the command with exit 1.
            Defaults to ``True`` so that a fresh rule behaves like a setup
            step that must succeed. Set to ``False`` for best-effort rules
            whose failures should be reported but not block the command.
    """

    when: str
    after_clone: list[Action] = field(default_factory=list)
    after_add: list[Action] = field(default_factory=list)
    before_remove: list[Action] = field(default_factory=list)
    critical: bool = True


@dataclass
class ProviderConfig:
    """Validated provider block from ``providers:`` in the config.

    A provider is a named filter-check rule selected by a ``when`` predicate
    over the source's origin URI (same mechanism as ``sources:``; ADR-0021).
    Its ``filter`` command template is evaluated per-branch by ``gww clean``
    (see ADR-0018).

    Attributes:
        name: Provider name — the key under ``providers:`` in the config.
            Free-form; parallels :attr:`SourceRule.name`.
        when: Expression evaluated against the URI+tag context. The first
            provider whose ``when`` matches wins (ADR-0021).
        filter: Command template evaluated per-branch; exit code 0 means
            "the branch is cleanable" (e.g., merged MR/PR exists) and the
            worktree is removed.
    """

    name: str
    when: str
    filter: str



@dataclass
class Config:
    """Validated configuration.

    Attributes:
        default_sources: Template string for default source location.
        default_worktrees: Template string for default worktree location.
        sources: Named source routing rules.
        actions: Action rules for project detection.
        providers: Provider rules keyed by name, selected by a ``when``
            predicate. Used by ``gww clean`` (ADR-0021).
    """

    default_sources: str
    default_worktrees: str
    sources: dict[str, SourceRule] = field(default_factory=dict)
    actions: list[ProjectRule] = field(default_factory=list)
    providers: dict[str, ProviderConfig] = field(default_factory=dict)


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

    if "critical" in action_data:
        raise ConfigValidationError(
            f"{context}: 'critical' is only valid at the rule level, "
            f"not on individual actions"
        )

    if len(action_data) != 1:
        raise ConfigValidationError(
            f"{context}: action must have exactly one key (action type)"
        )

    action_type = list(action_data.keys())[0]
    args = action_data[action_type]

    valid_types = {"copy", "command"}
    if action_type not in valid_types:
        raise ConfigValidationError(
            f"{context}: invalid action type '{action_type}'. "
            f"Must be one of: {', '.join(sorted(valid_types))}"
        )

    # Command action requires a single string (can contain template functions)
    if action_type == "command":
        if not isinstance(args, str):
            raise ConfigValidationError(
                f"{context}: command action must be a single string, "
                f"got {type(args).__name__}"
            )
        if not args.strip():
            raise ConfigValidationError(f"{context}: command string cannot be empty")
        # Store as single-element list for consistency
        args = [args]
    else:
        # copy accepts a string or list of two template-evaluated strings
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

    if "when" not in data:
        raise ConfigValidationError(f"Source rule '{name}' missing required 'when'")

    when = _validate_string(data["when"], f"sources.{name}.when")

    sources = None
    if "sources" in data:
        sources = _validate_string(data["sources"], f"sources.{name}.sources")

    worktrees = None
    if "worktrees" in data:
        worktrees = _validate_string(data["worktrees"], f"sources.{name}.worktrees")

    return SourceRule(
        name=name,
        when=when,
        sources=sources,
        worktrees=worktrees,
    )


def _validate_provider(name: str, data: Any) -> ProviderConfig:
    """Validate and parse a single provider block.

    Args:
        name: Provider name — the key under ``providers:``.
        data: Provider data from config.

    Returns:
        Validated :class:`ProviderConfig` object.

    Raises:
        ConfigValidationError: If validation fails.
    """
    if not isinstance(data, dict):
        raise ConfigValidationError(
            f"Provider '{name}' must be a mapping, got {type(data).__name__}"
        )

    if "when" not in data:
        raise ConfigValidationError(f"Provider '{name}' missing required 'when'")

    when = _validate_string(data["when"], f"providers.{name}.when")

    filter_data = data.get("filter")
    if not isinstance(filter_data, str):
        raise ConfigValidationError(
            f"Provider '{name}' requires a 'filter' template string, "
            f"got {type(filter_data).__name__}"
        )
    if not filter_data.strip():
        raise ConfigValidationError(f"Provider '{name}'.filter cannot be empty")

    return ProviderConfig(
        name=name,
        when=when,
        filter=filter_data,
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
    context = f"actions[{index}]"

    if not isinstance(data, dict):
        raise ConfigValidationError(
            f"{context} must be a mapping, got {type(data).__name__}"
        )

    if "when" not in data:
        raise ConfigValidationError(f"{context} missing required 'when'")

    when = _validate_string(data["when"], f"{context}.when")

    critical: bool = True
    if "critical" in data:
        critical_value = data["critical"]
        if not isinstance(critical_value, bool):
            raise ConfigValidationError(
                f"{context}.critical must be a boolean, "
                f"got {type(critical_value).__name__}"
            )
        critical = critical_value

    after_clone: list[Action] = []
    if "after_clone" in data:
        actions_data = data["after_clone"]
        if not isinstance(actions_data, list):
            raise ConfigValidationError(f"{context}.after_clone must be a list")
        for i, action_data in enumerate(actions_data):
            action = _validate_action(action_data, f"{context}.after_clone[{i}]")
            after_clone.append(action)

    after_add: list[Action] = []
    if "after_add" in data:
        actions_data = data["after_add"]
        if not isinstance(actions_data, list):
            raise ConfigValidationError(f"{context}.after_add must be a list")
        for i, action_data in enumerate(actions_data):
            action = _validate_action(action_data, f"{context}.after_add[{i}]")
            after_add.append(action)

    before_remove: list[Action] = []
    if "before_remove" in data:
        actions_data = data["before_remove"]
        if not isinstance(actions_data, list):
            raise ConfigValidationError(f"{context}.before_remove must be a list")
        for i, action_data in enumerate(actions_data):
            action = _validate_action(action_data, f"{context}.before_remove[{i}]")
            before_remove.append(action)

    if not after_clone and not after_add and not before_remove:
        raise ConfigValidationError(
            f"{context} must have at least one of: after_clone, after_add, "
            f"before_remove"
        )

    return ProjectRule(
        when=when,
        after_clone=after_clone,
        after_add=after_add,
        before_remove=before_remove,
        critical=critical,
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

    # Validate optional actions
    actions: list[ProjectRule] = []
    if "actions" in data:
        actions_data = data["actions"]
        if not isinstance(actions_data, list):
            raise ConfigValidationError(
                f"'actions' must be a list, got {type(actions_data).__name__}"
            )
        for i, rule_data in enumerate(actions_data):
            actions.append(_validate_project_rule(rule_data, i))

    # Validate optional providers (used by `gww clean`, ADR-0021)
    providers: dict[str, ProviderConfig] = {}
    if "providers" in data:
        providers_data = data["providers"]
        if not isinstance(providers_data, dict):
            raise ConfigValidationError(
                f"'providers' must be a mapping, got {type(providers_data).__name__}"
            )
        for name, provider_data in providers_data.items():
            providers[name] = _validate_provider(name, provider_data)

    return Config(
        default_sources=default_sources,
        default_worktrees=default_worktrees,
        sources=sources,
        actions=actions,
        providers=providers,
    )
