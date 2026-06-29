"""Project action matching and execution.

This package replaces the old ``actions/matcher.py`` and ``actions/executor.py``
split with a single entry point (:func:`apply_actions`) that returns typed
:class:`Action` objects grouped per matched rule. Commands iterate over the
returned bundles and call :meth:`Action.run` for each action.

Public surface:

* :class:`Action` protocol and concrete :class:`AbsCopyAction`,
  :class:`RelCopyAction`, :class:`CommandAction` (in :mod:`gww.actions.types`)
* :class:`ActionError` raised by ``run()`` on failure
* :class:`MatcherError` raised by :func:`apply_actions` when a rule predicate
  or command template cannot be evaluated
* :class:`RuleActions` — a rule that matched, its index/predicate/criticality,
  and the executable actions for the requested kind
* :func:`apply_actions` — match rules and return executable bundles
* :data:`ActionKind` — literal distinguishing ``after_clone`` vs ``after_add``
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

from gww.actions.types import (
    AbsCopyAction,
    Action,
    ActionError,
    CommandAction,
    RelCopyAction,
)
from gww.config.validator import Action as RawAction
from gww.config.validator import ProjectRule
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
    """Raised when project matching or command-template evaluation fails."""


ActionKind = Literal["after_clone", "after_add"]


@dataclass
class RuleActions:
    """A matched project rule plus the actions to execute for one kind.

    Carries enough context (index, predicate text, criticality flag) for the
    CLI loop to attribute per-action failures back to the rule that produced
    them, and to decide whether the command should exit 1.

    Attributes:
        index: Position of the rule in ``config.actions`` — used as the rule's
            identifier in error messages.
        predicate: The ``when:`` expression as it appears in the config; kept
            verbatim for diagnostics.
        critical: Per-rule criticality flag from :class:`ProjectRule`. When
            ``True``, a failing action aborts the rule's remaining actions
            and causes the command to exit 1.
        actions: Executable actions for the requested ``kind``, in the order
            they appear in the rule's ``after_clone`` or ``after_add`` list.
    """

    index: int
    predicate: str
    critical: bool
    actions: list[Action] = field(default_factory=list)


__all__ = [
    "AbsCopyAction",
    "Action",
    "ActionError",
    "ActionKind",
    "CommandAction",
    "MatcherError",
    "RelCopyAction",
    "RuleActions",
    "apply_actions",
]


def _create_predicate_context(context: TemplateContext) -> dict[str, object]:
    """Build the evaluation context shared by ``when`` predicates and command
    templates.

    Adds project-specific functions (``source_path``, ``dest_path``,
    ``file_exists``, ``dir_exists``, ``path_exists``) on top of the unified
    URI/branch/tag registry seeded by ``context``.
    """
    functions: dict[str, object] = dict(create_function_registry(context))
    functions.update(create_project_functions(context))
    return functions


def _build_action(
    raw: RawAction,
    context: dict[str, object],
) -> Action:
    """Turn a config-level :class:`Action` into a typed executable.

    For ``command`` actions the template is evaluated against ``context`` and
    parsed with :mod:`shlex` so the resulting :class:`CommandAction` already
    holds the resolved argv. For copy actions the args pass through.
    """
    if raw.action_type == "abs_copy":
        if len(raw.args) < 2:
            raise MatcherError("abs_copy requires source and destination arguments")
        return AbsCopyAction(source=raw.args[0], destination=raw.args[1])

    if raw.action_type == "rel_copy":
        if len(raw.args) < 1:
            raise MatcherError("rel_copy requires at least source argument")
        destination = raw.args[1] if len(raw.args) > 1 else None
        return RelCopyAction(source=raw.args[0], destination=destination)

    if raw.action_type == "command":
        template = raw.args[0] if raw.args else ""
        try:
            evaluated = evaluate_command_template(template, context)
        except TemplateError as e:
            raise MatcherError(
                f"Error evaluating command template '{template}': {e}"
            ) from e
        try:
            parsed = shlex.split(evaluated)
        except ValueError as e:
            raise MatcherError(f"Error parsing command '{evaluated}': {e}") from e
        if not parsed:
            raise MatcherError("command requires at least command name")
        return CommandAction(command=parsed[0], args=parsed[1:])

    raise MatcherError(f"Unknown action type: {raw.action_type}")


def apply_actions(
    rules: list[ProjectRule],
    context: TemplateContext,
    kind: ActionKind,
) -> list[RuleActions]:
    """Match rules and return executable bundles for the given ``kind``.

    A :class:`RuleActions` bundle is produced for every rule whose ``when``
    predicate evaluates truthy, even when that rule has no actions for the
    requested ``kind`` — the bundle's ``actions`` list is simply empty. This
    keeps the CLI loop's failure-tracking symmetric: a rule that ran zero
    actions still has a known index/criticality for the summary.

    The ``context`` carries the URI, branch, tags, source path, and
    destination path that ``when`` predicates and command templates evaluate
    against. Callers (``clone``, ``add``) populate it from the operation in
    progress; see :class:`TemplateContext` for the field-level contract.

    Args:
        rules: Project rules from the validated config.
        context: Evaluation context — see :class:`TemplateContext`.
        kind: Which action list to read — ``"after_clone"`` or ``"after_add"``.

    Returns:
        Matched rules paired with their typed actions, in config order. Each
        bundle carries the rule's index, predicate text, and criticality so
        the CLI can attribute failures and choose exit codes.

    Raises:
        MatcherError: If a ``when`` predicate or a ``command`` template fails
            to evaluate. The CLI converts this to a config-error exit (2);
            it is never swallowed.
    """
    eval_context = _create_predicate_context(context)

    bundles: list[RuleActions] = []
    for i, rule in enumerate(rules):
        try:
            matched = evaluate_predicate(rule.when, eval_context)
        except TemplateError as e:
            raise MatcherError(
                f"Error evaluating 'when' for project rule {i}: {e}"
            ) from e
        if not matched:
            continue

        source_actions = (
            rule.after_clone if kind == "after_clone" else rule.after_add
        )
        actions: list[Action] = []
        for raw in source_actions:
            actions.append(_build_action(raw, eval_context))

        bundles.append(
            RuleActions(
                index=i,
                predicate=rule.when,
                critical=rule.critical,
                actions=actions,
            )
        )

    return bundles