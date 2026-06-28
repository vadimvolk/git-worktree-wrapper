"""Migration planning and execution split out of ``gww.cli.commands.migrate``.

Public surface:

* :func:`plan_migration` — match repo roots against the config and produce
  either a :class:`Migration` or a :class:`Blocked` result.
* :func:`execute` — run the plan in copy or inplace mode.
* :func:`collect_repositories` — directory scan helper used by the CLI.
* :func:`fix_copied_worktree_gitfile` — repair ``.git`` pointer after copy.

See :mod:`gww.migration.planner` and :mod:`gww.migration.executor` for the
detailed contracts of each function.
"""

from gww.migration.executor import (
    Mode,
    execute,
    fix_copied_worktree_gitfile,
)
from gww.migration.planner import (
    Blocked,
    Migration,
    MigrationPlan,
    MigrationResult,
    Skip,
    collect_repositories,
    find_git_repositories,
    plan_migration,
)


__all__ = [
    "Blocked",
    "Migration",
    "MigrationPlan",
    "MigrationResult",
    "Mode",
    "Skip",
    "collect_repositories",
    "execute",
    "find_git_repositories",
    "fix_copied_worktree_gitfile",
    "plan_migration",
]