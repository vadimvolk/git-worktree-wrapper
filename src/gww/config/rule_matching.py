"""Shared ``when``-predicate matching primitive.

Both ``sources:`` routing rules and ``providers:`` merged-check rules select
by evaluating a ``when`` predicate against a URI+tag context and taking the
first rule that matches, walking the map in config order. This module holds
that single primitive; :mod:`gww.config.resolver` wraps it with typed,
labelled entry points (:func:`~gww.config.resolver.find_matching_source_rule`
and :func:`~gww.config.resolver.find_matching_provider`).

:class:`ResolverError` lives here so the primitive can raise it directly
without importing :mod:`resolver` (which would be circular); ``resolver``
re-exports it under its historical name.
"""

from __future__ import annotations

from typing import Any, Callable, Optional, Protocol, TypeVar

from gww.template.evaluator import TemplateError, evaluate_predicate


class ResolverError(Exception):
    """Raised when rule/path resolution fails."""

    pass


class WhenRule(Protocol):
    """Any rule selected by a ``when`` predicate.

    Both :class:`~gww.config.validator.SourceRule` and
    :class:`~gww.config.validator.ProviderConfig` satisfy this.
    """

    when: str


R = TypeVar("R", bound=WhenRule)


def first_matching_rule(
    rules: dict[str, R],
    context: dict[str, Callable[..., Any]],
    *,
    label: str,
) -> Optional[R]:
    """Return the first rule whose ``when`` predicate matches ``context``.

    Walks ``rules`` in insertion (config) order — ruamel.yaml preserves it —
    and returns the first rule whose ``when`` evaluates truthy. First match
    wins; ``None`` if none match.

    Args:
        rules: Named rules to test, in config order.
        context: Function registry from ``_build_uri_context``.
        label: Human-readable rule-kind used in the error message (e.g.
            ``"source rule"`` or ``"provider"``).

    Returns:
        The first matching rule, or ``None`` if no ``when`` matches.

    Raises:
        ResolverError: If a ``when`` predicate fails to evaluate.
    """
    for name, rule in rules.items():
        try:
            if evaluate_predicate(rule.when, context):
                return rule
        except TemplateError as e:
            raise ResolverError(
                f"Error evaluating 'when' for {label} '{name}': {e}"
            ) from e
    return None


__all__ = ["ResolverError", "WhenRule", "first_matching_rule"]
