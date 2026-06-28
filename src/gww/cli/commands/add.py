"""Add worktree command implementation."""

from __future__ import annotations

import sys
from pathlib import Path

from gww.actions import ActionError, apply_actions
from gww.cli.context import (
    CommandContext,
    CommandExit,
    exit_on_error,
    load_config_or_exit,
    parse_uri_or_exit,
    resolve_source_repo_or_exit,
)
from gww.config.resolver import ResolverError, resolve_worktree_path
from gww.git.branch import (
    BranchExistsError,
    branch_exists,
    create_branch,
)
from gww.git.repository import (
    GitCommandError,
    get_current_commit,
)
from gww.git.worktree import WorktreeExistsError, add_worktree


@exit_on_error
def run_add(ctx: CommandContext) -> int:
    """Execute the add worktree command.

    Args:
        ctx: Per-invocation command context.

    Returns:
        Exit code (0 for success, 1 for error, 2 for config error).
    """
    if ctx.branch is None:
        raise CommandExit(1, "Error: Missing branch name.")

    cwd = Path.cwd()
    source_path, remote_uri = resolve_source_repo_or_exit(cwd)
    uri = parse_uri_or_exit(remote_uri)
    config = load_config_or_exit()

    if not branch_exists(source_path, ctx.branch):
        if ctx.create_branch:
            try:
                current_commit = get_current_commit(cwd)
                create_branch(source_path, ctx.branch, current_commit)
                ctx.verbose_msg(
                    f"Created branch '{ctx.branch}' from {current_commit[:8]}"
                )
            except (GitCommandError, BranchExistsError) as e:
                raise CommandExit(1, f"Error creating branch: {e}") from e
        else:
            raise CommandExit(
                1,
                f"Error: Branch '{ctx.branch}' not found. "
                "Use --create-branch to create from current commit.",
            )

    try:
        worktree_path = resolve_worktree_path(config, uri, ctx.branch, ctx.tags)
    except ResolverError as e:
        raise CommandExit(2, f"Error resolving worktree path: {e}") from e

    ctx.verbose_msg(f"Adding worktree for '{ctx.branch}' at {worktree_path}...")

    try:
        add_worktree(
            source_path,
            worktree_path,
            ctx.branch,
            pass_through_stdout=not ctx.quiet,
        )
    except (WorktreeExistsError, GitCommandError) as e:
        raise CommandExit(1, f"Error adding worktree: {e}") from e

    if config.actions:
        try:
            actions = apply_actions(
                config.actions,
                source_path,
                ctx.tags,
                dest_path=worktree_path,
                kind="after_add",
            )
        except Exception as e:
            print(f"Error matching project rules: {e}", file=sys.stderr)
            actions = []

        if actions:
            ctx.verbose_msg(f"Executing {len(actions)} worktree action(s)...")
            for action in actions:
                try:
                    action.run(
                        source_dir=source_path,
                        target_dir=worktree_path,
                        pass_through_stdout=not ctx.quiet,
                    )
                except ActionError as e:
                    print(f"Error executing worktree action: {e}", file=sys.stderr)

    ctx.say(str(worktree_path))

    return 0