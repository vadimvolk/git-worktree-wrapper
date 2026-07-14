"""Remove worktree command implementation."""

from __future__ import annotations

from pathlib import Path

from gww.actions import MatcherError
from gww.actions.removal import remove_one_worktree
from gww.cli.context import (
    CommandContext,
    CommandExit,
    exit_on_error,
    load_config_or_exit,
    parse_uri_or_exit,
    print_action_failure_summary,
    resolve_source_repo,
)
from gww.git.repository import (
    GitCommandError,
    NotGitRepositoryError,
    detect_repository,
    get_source_repository,
    try_get_current_branch,
)
from gww.git.worktree import find_worktree_by_branch
from gww.template.functions import TemplateContext


@exit_on_error
def run_remove(ctx: CommandContext) -> int:
    """Execute the remove worktree command.

    Resolves the target worktree (by branch or absolute path), runs any
    ``before_remove`` actions from project rules against the worktree, and
    finally invokes ``git worktree remove``. A critical ``before_remove``
    failure aborts before ``git worktree remove`` is called and exits with
    code 1; a non-critical failure is reported but the remove proceeds.

    Args:
        ctx: Per-invocation command context.

    Returns:
        Exit code (0 for success, 1 for runtime/action failure, 2 for config
        error).
    """
    if ctx.branch_or_path is None:
        raise CommandExit(1, "Error: Missing branch or path.")

    branch_or_path = ctx.branch_or_path
    is_path = "/" in branch_or_path and Path(branch_or_path).is_absolute()

    if is_path:
        worktree_path = Path(branch_or_path).resolve()

        try:
            repo = detect_repository(worktree_path)
        except NotGitRepositoryError as e:
            raise CommandExit(1, f"Error: Not a git repository: {worktree_path}") from e

        if not repo.is_worktree:
            raise CommandExit(1, f"Error: Not a worktree: {worktree_path}")

        try:
            source_path = get_source_repository(worktree_path)
        except (NotGitRepositoryError, GitCommandError) as e:
            raise CommandExit(1, f"Error finding source repository: {e}") from e
    else:
        branch = branch_or_path
        source_path = resolve_source_repo(Path.cwd())

        wt = find_worktree_by_branch(source_path, branch)
        if not wt:
            raise CommandExit(1, f"Error: No worktree found for branch '{branch}'")
        worktree_path = wt.path

    config = load_config_or_exit()

    # Resolve branch + URI for the template context.
    if is_path:
        branch = try_get_current_branch(worktree_path)
    else:
        branch = branch_or_path

    try:
        source_repo = detect_repository(source_path)
    except NotGitRepositoryError:
        remote_uri_str = None
    else:
        remote_uri_str = source_repo.remote_uri

    uri = parse_uri_or_exit(remote_uri_str) if remote_uri_str else None

    if ctx.verbose > 0:
        if ctx.force:
            ctx.verbose_msg(f"Force removing worktree: {worktree_path}...")
        else:
            ctx.verbose_msg(f"Removing worktree: {worktree_path}...")

    context = TemplateContext(
        uri=uri,
        branch=branch,
        source_path=source_path,
        dest_path=worktree_path,
        tags=ctx.tags,
    )
    try:
        outcome = remove_one_worktree(
            source_path,
            worktree_path,
            actions=config.actions,
            context=context,
            force=ctx.force,
            quiet=ctx.quiet,
        )
    except MatcherError as e:
        raise CommandExit(2, f"Config error: {e}") from e

    if outcome.failures:
        print_action_failure_summary(outcome.failures)

    if outcome.critical_failure:
        raise CommandExit(1, "")

    if not outcome.removed:
        # git worktree remove failed; surface its message (dirty-worktree,
        # not-found, etc.) on stderr, matching the pre-refactor behaviour.
        raise CommandExit(1, f"Error: {outcome.error}" if outcome.error else "")

    ctx.say(f"Removed worktree: {worktree_path}")

    return 0