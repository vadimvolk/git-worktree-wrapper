"""Configuration resolver for path template evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from gww.config.rule_matching import ResolverError, first_matching_rule
from gww.config.validator import Config, ProviderConfig, SourceRule
from gww.template.evaluator import TemplateError, evaluate_template
from gww.template.functions import TemplateContext, create_function_registry
from gww.utils.uri import ParsedURI

__all__ = [
    "ResolverError",
    "find_matching_source_rule",
    "find_matching_provider",
    "resolve_source_path",
    "resolve_worktree_path",
    "get_source_path_for_worktree",
]


def _expand_home(path: str) -> str:
    """Expand ~ to home directory in path string.

    Args:
        path: Path string that may contain ~.

    Returns:
        Path with ~ expanded to home directory.
    """
    if path.startswith("~"):
        return str(Path(path).expanduser())
    return path


def _build_uri_context(uri: ParsedURI, tags: dict[str, str] = {}) -> dict[str, Any]:
    """Build evaluation context for URI predicates.

    Uses the unified FunctionRegistry to provide shared functions:
    - URI functions: host(), port(), protocol(), uri(), path(index)
    - Tag functions: tag(name), tag_exist(name)

    Args:
        uri: Parsed URI object.
        tags: Optional dictionary of tag key-value pairs.

    Returns:
        Dictionary of context functions for predicate evaluation.
    """
    context = TemplateContext(uri=uri, tags=tags)
    return create_function_registry(context)


def find_matching_source_rule(
    config: Config,
    uri: ParsedURI,
    tags: dict[str, str] = {},
) -> Optional[SourceRule]:
    """Find the first matching source rule for a URI.

    Args:
        config: Validated configuration.
        uri: Parsed URI to match against.
        tags: Optional dictionary of tag key-value pairs.

    Returns:
        Matching SourceRule, or None if no match.

    Raises:
        ResolverError: If predicate evaluation fails.
    """
    context = _build_uri_context(uri, tags)
    return first_matching_rule(config.sources, context, label="source rule")


def find_matching_provider(
    config: Config,
    uri: ParsedURI,
    tags: dict[str, str] = {},
) -> Optional[ProviderConfig]:
    """Find the first matching provider for a URI (used by ``gww clean``).

    Providers select exactly like source rules — a ``when`` predicate over
    the URI+tag context, first match wins in config order (ADR-0021).

    Args:
        config: Validated configuration.
        uri: Parsed URI to match against.
        tags: Optional dictionary of tag key-value pairs.

    Returns:
        Matching ProviderConfig, or None if no provider matches.

    Raises:
        ResolverError: If predicate evaluation fails.
    """
    context = _build_uri_context(uri, tags)
    return first_matching_rule(config.providers, context, label="provider")


def resolve_source_path(
    config: Config,
    uri: ParsedURI,
    tags: dict[str, str] = {},
) -> Path:
    """Resolve the source checkout path for a URI.

    Args:
        config: Validated configuration.
        uri: Parsed URI for the repository.
        tags: Optional dictionary of tag key-value pairs.

    Returns:
        Absolute path where repository should be cloned.

    Raises:
        ResolverError: If path resolution fails.
    """
    # Find matching rule or use default
    rule = find_matching_source_rule(config, uri, tags)

    if rule and rule.sources:
        template = rule.sources
    else:
        template = config.default_sources

    # Create context and evaluate template
    context = TemplateContext(uri=uri, tags=tags)

    try:
        path_str = evaluate_template(template, context)
    except TemplateError as e:
        raise ResolverError(f"Error evaluating source path template: {e}") from e

    # Expand ~ and resolve to absolute path
    path_str = _expand_home(path_str)
    return Path(path_str).resolve()


def resolve_worktree_path(
    config: Config,
    uri: ParsedURI,
    branch: str,
    tags: dict[str, str] = {},
) -> Path:
    """Resolve the worktree path for a branch.

    Args:
        config: Validated configuration.
        uri: Parsed URI for the repository.
        branch: Branch name for the worktree.
        tags: Optional dictionary of tag key-value pairs.

    Returns:
        Absolute path where worktree should be created.

    Raises:
        ResolverError: If path resolution fails.
    """
    # Find matching rule or use default
    rule = find_matching_source_rule(config, uri, tags)

    if rule and rule.worktrees:
        template = rule.worktrees
    else:
        template = config.default_worktrees

    # Create context and evaluate template
    context = TemplateContext(
        uri=uri,
        branch=branch,
        tags=tags,
    )

    try:
        path_str = evaluate_template(template, context)
    except TemplateError as e:
        raise ResolverError(f"Error evaluating worktree path template: {e}") from e

    # Expand ~ and resolve to absolute path
    path_str = _expand_home(path_str)
    return Path(path_str).resolve()


def get_source_path_for_worktree(
    config: Config,
    uri: ParsedURI,
    tags: dict[str, str] = {},
) -> Path:
    """Get the source path that corresponds to a worktree's repository.

    This is useful when working from a worktree to find its source repository.

    Args:
        config: Validated configuration.
        uri: Parsed URI for the repository.
        tags: Optional dictionary of tag key-value pairs.

    Returns:
        Absolute path to the source repository.

    Raises:
        ResolverError: If path resolution fails.
    """
    return resolve_source_path(config, uri, tags)
