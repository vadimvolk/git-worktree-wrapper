"""Migrate command implementation.

Thin wrapper over :mod:`gww.migration`: the command validates inputs,
calls the planner, prints the result, and delegates execution to the
executor. All planning and movement logic lives in the migration package
where it can be unit-tested directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

from gww.cli.context import CommandContext, CommandExit, exit_on_error, load_config_or_exit
from gww.migration import (
    Blocked,
    Migration,
    Mode,
    collect_repositories,
    execute,
    plan_migration,
)


@exit_on_error
def run_migrate(ctx: CommandContext) -> int:
    """Execute the migrate command.

    Args:
        ctx: Per-invocation command context.

    Returns:
        Exit code (0 for success, 1 for error, 2 for config error).
    """
    input_paths = [Path(p).expanduser().resolve() for p in ctx.old_repos]

    for p in input_paths:
        if not p.exists():
            raise CommandExit(1, f"Error: Path does not exist: {p}")
        if not p.is_dir():
            raise CommandExit(1, f"Error: Not a directory: {p}")

    config = load_config_or_exit()

    repos, input_roots = collect_repositories(input_paths)
    ctx.verbose_msg(f"Scanning {len(input_paths)} path(s) for repositories...")

    result = plan_migration(
        repos,
        config,
        inplace=ctx.inplace,
        verbose=ctx.verbose,
        tags=ctx.tags,
    )

    if isinstance(result, Blocked):
        for path in result.destinations:
            print(f"Error: Destination already exists: {path}", file=sys.stderr)
        count = len(result.destinations)
        print(
            f"Cannot proceed: {count} destination(s) already exist in copy mode",
            file=sys.stderr,
        )
        return 1

    migration: Migration = result

    if not migration.plans and not migration.info_skips and not migration.already_at_target:
        if not ctx.quiet:
            print("No repositories to migrate.")
        return 0

    mode: Mode = "inplace" if ctx.inplace else "copy"
    return execute(
        migration,
        input_roots=input_roots,
        mode=mode,
        dry_run=ctx.dry_run,
        quiet=ctx.quiet,
        verbose=ctx.verbose,
    )