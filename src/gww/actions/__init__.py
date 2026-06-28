"""Project action matching and execution.

This package replaces the old ``actions/matcher.py`` and ``actions/executor.py``
split with a single entry point (:func:`apply_actions`) that returns typed
:class:`Action` objects. Commands iterate over the returned actions and call
:meth:`Action.run` for each.

Public surface:

* :class:`Action` protocol and concrete :class:`AbsCopyAction`,
  :class:`RelCopyAction`, :class:`CommandAction` (in :mod:`gww.actions.types`)
* :class:`ActionError` raised by ``run()`` on failure
* :class:`MatcherError` raised by :func:`apply_actions` when a rule predicate
  or command template cannot be evaluated
* :func:`apply_actions` — match rules and return executable actions
* :data:`ActionKind` — literal distinguishing ``after_clone`` vs ``after_add``
"""

from __future__ import annotations

import shlex
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


__all__ = [
    "AbsCopyAction",
    "Action",
    "ActionError",
    "ActionKind",
    "CommandAction",
    "MatcherError",
    "RelCopyAction",
    "apply_actions",
]


def _create_predicate_context(
    source_path: Path,
    tags: dict[str, str],
    dest_path: Optional[Path],
) -> dict[str, object]:
    """Build the evaluation context shared by ``when`` predicates and command
    templates. Adds project-specific functions (``source_path``,
    ``dest_path``, ``file_exists``, ``dir_exists``, ``path_exists``) on top
    of the unified URI/branch/tag registry.
    """
    context = TemplateContext(source_path=source_path, tags=tags)
    functions: dict[str, object] = dict(create_function_registry(context))
    functions.update(create_project_functions(source_path, dest_path))
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
    source_path: Path,
    tags: dict[str, str],
    dest_path: Path,
    kind: ActionKind,
) -> list[Action]:
    """Match rules and return executable actions for the given ``kind``.

    Args:
        rules: Project rules from the validated config.
        source_path: Path to the source repository.
        tags: Tag key-value pairs from the CLI.
        dest_path: Destination path (equals ``source_path`` for ``after_clone``,
            equals the worktree path for ``after_add``).
        kind: Which action list to read — ``"after_clone"`` or ``"after_add"``.

    Returns:
        Typed actions in execution order, ready to be passed to
        :meth:`Action.run`.

    Raises:
        MatcherError: If a ``when`` predicate or a ``command`` template fails
            to evaluate.
    """
    context = _create_predicate_context(source_path, tags, dest_path)

    matched: list[ProjectRule] = []
    for i, rule in enumerate(rules):
        try:
            if evaluate_predicate(rule.when, context):
                matched.append(rule)
        except TemplateError as e:
            raise MatcherError(
                f"Error evaluating 'when' for project rule {i}: {e}"
            ) from e

    actions: list[Action] = []
    for rule in matched:
        source_actions = (
            rule.after_clone if kind == "after_clone" else rule.after_add
        )
        for raw in source_actions:
            actions.append(_build_action(raw, context))

    return actions