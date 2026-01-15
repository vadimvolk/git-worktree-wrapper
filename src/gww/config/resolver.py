"""Configuration resolver for path template evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from gww.config.validator import Config, SourceRule
from gww.template.evaluator import TemplateError, evaluate_predicate, evaluate_template
from gww.template.functions import TemplateContext
from gww.utils.uri import ParsedURI


class ResolverError(Exception):
    """Raised when path resolution fails."""

    pass


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


def _build_uri_context(uri: ParsedURI) -> dict[str, object]:
    """Build evaluation context for URI predicates.

    Args:
        uri: Parsed URI object.

    Returns:
        Dictionary of context variables for predicate evaluation.
    """
    return {
        "host": uri.host,
        "port": uri.port,
        "protocol": uri.protocol,
        "path": uri.path_segments,
        "uri": uri.uri,
    }


def find_matching_source_rule(
    config: Config,
    uri: ParsedURI,
) -> Optional[SourceRule]:
    """Find the first matching source rule for a URI.

    Args:
        config: Validated configuration.
        uri: Parsed URI to match against.

    Returns:
        Matching SourceRule, or None if no match.

    Raises:
        ResolverError: If predicate evaluation fails.
    """
    context = _build_uri_context(uri)

    for name, rule in config.sources.items():
        try:
            if evaluate_predicate(rule.predicate, context):
                return rule
        except TemplateError as e:
            raise ResolverError(
                f"Error evaluating predicate for source rule '{name}': {e}"
            ) from e

    return None


def resolve_source_path(
    config: Config,
    uri: ParsedURI,
) -> Path:
    """Resolve the source checkout path for a URI.

    Args:
        config: Validated configuration.
        uri: Parsed URI for the repository.

    Returns:
        Absolute path where repository should be cloned.

    Raises:
        ResolverError: If path resolution fails.
    """
    # Find matching rule or use default
    rule = find_matching_source_rule(config, uri)

    if rule and rule.sources:
        template = rule.sources
    else:
        template = config.default_sources

    # Create context and evaluate template
    context = TemplateContext(uri=uri)

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
    worktree_name: Optional[str] = None,
) -> Path:
    """Resolve the worktree path for a branch.

    Args:
        config: Validated configuration.
        uri: Parsed URI for the repository.
        branch: Branch name for the worktree.
        worktree_name: Optional worktree name.

    Returns:
        Absolute path where worktree should be created.

    Raises:
        ResolverError: If path resolution fails.
    """
    # Find matching rule or use default
    rule = find_matching_source_rule(config, uri)

    if rule and rule.worktrees:
        template = rule.worktrees
    else:
        template = config.default_worktrees

    # Create context and evaluate template
    context = TemplateContext(
        uri=uri,
        branch=branch,
        worktree_name=worktree_name,
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
) -> Path:
    """Get the source path that corresponds to a worktree's repository.

    This is useful when working from a worktree to find its source repository.

    Args:
        config: Validated configuration.
        uri: Parsed URI for the repository.

    Returns:
        Absolute path to the source repository.

    Raises:
        ResolverError: If path resolution fails.
    """
    return resolve_source_path(config, uri)
