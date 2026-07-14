"""Shared per-worktree removal primitive used by ``gww remove`` and ``gww clean``.

Runs the ``before_remove`` project actions for one worktree, then
``git worktree remove``, and reports the outcome. It never prints and never
raises ``CommandExit``: the two CLI commands apply their own exit-code and
output policy on top of the returned :class:`RemovalOutcome`.

:class:`MatcherError` from :func:`apply_actions` (a whole-invocation config
error, not a per-worktree outcome) is allowed to propagate unchanged; each
caller translates it to ``CommandExit(2)`` at its own call site.

The primitive lives in the actions package, not the CLI package, so it has no
dependency on :mod:`gww.cli` (CLI depends on actions, never the reverse).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from gww.actions import (
    Action,
    ActionError,
    RuleActions,
    apply_actions,
)
from gww.config.validator import ProjectRule
from gww.git.repository import GitCommandError
from gww.git.worktree import (
    WorktreeDirtyError,
    WorktreeNotFoundError,
    remove_worktree,
)
from gww.template.functions import TemplateContext


@dataclass
class RuleFailure:
    """A single failing action in a per-worktree action loop.

    Pairs the failing :class:`Action` with the :class:`RuleActions` bundle it
    came from and the :class:`ActionError` it raised. Used by
    :func:`gww.cli.context.print_action_failure_summary` to produce the grouped
    stderr block, and by the CLI to choose the exit code (any failure with
    ``bundle.critical`` set → exit 1).

    Attributes:
        bundle: The rule that produced the action.
        action: The action whose ``run()`` raised.
        error: The exception raised by ``action.run()``.
    """

    bundle: RuleActions
    action: Action
    error: ActionError


@dataclass(frozen=True)
class RemovalOutcome:
    """Result of attempting to remove one worktree.

    Attributes:
        removed: True iff ``git worktree remove`` succeeded.
        critical_failure: True iff a critical ``before_remove`` action failed,
            which stopped processing before the git step ran.
        failures: All action failures encountered (critical and non-critical),
            for the caller to feed to
            :func:`gww.cli.context.print_action_failure_summary`.
        error: Message from the ``git worktree remove`` failure (e.g. the
            dirty-worktree "uncommitted changes" text), or ``None`` when the
            git step succeeded or was never reached. Callers that want to
            surface it decide how; the primitive never prints.
    """

    removed: bool
    critical_failure: bool
    failures: list[RuleFailure] = field(default_factory=list)
    error: str | None = None


def remove_one_worktree(
    source_path: Path,
    worktree_path: Path,
    *,
    actions: list[ProjectRule],
    context: TemplateContext,
    force: bool,
    quiet: bool,
) -> RemovalOutcome:
    """Run before_remove actions then ``git worktree remove`` for one worktree.

    Args:
        source_path: Path to the source repository.
        worktree_path: Path of the worktree to remove.
        actions: Project rules from the validated config.
        context: Evaluation context for the ``before_remove`` actions.
        force: Whether to force ``git worktree remove`` past safety checks.
        quiet: Whether to suppress action/git pass-through output.

    Returns:
        A :class:`RemovalOutcome` describing whether the worktree was removed,
        whether a critical action failed, and every action failure seen.

    Raises:
        MatcherError: If a ``when`` predicate or command template cannot be
            evaluated. Propagated unchanged (whole-invocation config error).
    """
    failures: list[RuleFailure] = []

    if actions:
        # apply_actions may raise MatcherError; let it propagate.
        rule_bundles = apply_actions(actions, context, kind="before_remove")

        for bundle in rule_bundles:
            for action in bundle.actions:
                try:
                    action.run(
                        source_dir=source_path,
                        target_dir=worktree_path,
                        pass_through_stdout=not quiet,
                    )
                except ActionError as e:
                    failures.append(RuleFailure(bundle, action, e))
                    if bundle.critical:
                        break

    critical_failure = any(f.bundle.critical for f in failures)
    if critical_failure:
        return RemovalOutcome(
            removed=False, critical_failure=True, failures=failures,
        )

    try:
        remove_worktree(
            source_path,
            worktree_path,
            force=force,
            pass_through_stdout=not quiet,
        )
    except (WorktreeNotFoundError, WorktreeDirtyError, GitCommandError) as e:
        return RemovalOutcome(
            removed=False, critical_failure=False, failures=failures,
            error=str(e),
        )

    return RemovalOutcome(
        removed=True, critical_failure=False, failures=failures,
    )
