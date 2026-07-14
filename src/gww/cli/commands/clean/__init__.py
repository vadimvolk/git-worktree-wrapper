"""``gww clean`` command package.

Removes worktrees (and their local branches) whose branch satisfies the
active filter -- ``--merged`` (default) marks a worktree cleanable when
its branch has an upstream MR/PR in the merged state, ``--all`` skips
that check entirely. See ``docs/handoff-gww-clean-v2.md`` for the locked
contract and ``docs/adr/0015-cleanup-filter-polymorphism.md``,
``docs/adr/0017-cli-based-provider-no-direct-api.md``,
``docs/adr/0018-cleanup-exit-code-only-provider-contract.md`` and
``docs/adr/0019-provider-resolution-user-config-only.md`` for the
design rationale.

The command composes the shared :func:`gww.actions.removal.remove_one_worktree`
primitive so the per-worktree side-effect order (``before_remove`` actions,
``git worktree remove``, then ``git branch -d``) reuses the same criticality
semantics as ``gww remove``.
"""

from __future__ import annotations

from gww.cli.commands.clean.command import run_clean

__all__ = ["run_clean"]
