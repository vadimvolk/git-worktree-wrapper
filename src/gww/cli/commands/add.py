"""Add worktree command implementation."""

from __future__ import annotations

from pathlib import Path

from gww.actions import ActionError, MatcherError, apply_actions
from gww.cli.context import (
    CommandContext,
    CommandExit,
    RuleFailure,
    exit_on_error,
    load_config_or_exit,
    parse_uri_or_exit,
    print_action_failure_summary,
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
from gww.template.functions import TemplateContext


@exit_on_error
def run_add(ctx: CommandContext) -> int:
    """Execute the add worktree command.

    Args:
        ctx: Per-invocation command context.

    Returns:
        Exit code (0 for success, 1 for runtime/action failure, 2 for config
        error).
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
                "Use -c/--create-branch to create from current commit.",
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

    failures: list[RuleFailure] = []
    if config.actions:
        context = TemplateContext(
            uri=uri,
            branch=ctx.branch,
            source_path=source_path,
            dest_path=worktree_path,
            tags=ctx.tags,
        )
        try:
            rule_bundles = apply_actions(config.actions, context, kind="after_add")
        except MatcherError as e:
            raise CommandExit(2, f"Config error: {e}") from e

        if rule_bundles:
            ctx.verbose_msg(f"Executing {len(rule_bundles)} rule(s)...")
            for bundle in rule_bundles:
                for action in bundle.actions:
                    try:
                        action.run(
                            source_dir=source_path,
                            target_dir=worktree_path,
                            pass_through_stdout=not ctx.quiet,
                        )
                    except ActionError as e:
                        failures.append(RuleFailure(bundle, action, e))
                        if bundle.critical:
                            break

    if failures:
        print_action_failure_summary(failures)

    if not failures:
        ctx.say(str(worktree_path))

    if any(f.bundle.critical for f in failures):
        raise CommandExit(1, "")
    return 0