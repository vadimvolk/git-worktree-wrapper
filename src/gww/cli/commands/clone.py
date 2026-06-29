"""Clone command implementation."""

from __future__ import annotations

import sys

from gww.actions import ActionError, apply_actions
from gww.cli.context import (
    CommandContext,
    CommandExit,
    exit_on_error,
    load_config_or_exit,
    parse_uri_or_exit,
)
from gww.config.resolver import ResolverError, resolve_source_path
from gww.git.repository import (
    GitCommandError,
    clone_repository,
    try_get_current_branch,
)
from gww.template.functions import TemplateContext


@exit_on_error
def run_clone(ctx: CommandContext) -> int:
    """Execute the clone command.

    Args:
        ctx: Per-invocation command context.

    Returns:
        Exit code (0 for success, 1 for error, 2 for config error).
    """
    if ctx.uri is None:
        raise CommandExit(1, "Error: Missing repository URI.")

    uri = parse_uri_or_exit(ctx.uri)
    config = load_config_or_exit()

    try:
        source_path = resolve_source_path(config, uri, ctx.tags)
    except ResolverError as e:
        raise CommandExit(2, f"Error resolving source path: {e}") from e

    if source_path.exists():
        raise CommandExit(
            1,
            f"Error: Repository already exists at: {source_path}",
        )

    ctx.verbose_msg(f"Cloning {ctx.uri} to {source_path}...")

    try:
        clone_repository(ctx.uri, source_path, pass_through_stdout=not ctx.quiet)
    except GitCommandError as e:
        raise CommandExit(1, f"Error cloning repository: {e}") from e

    if config.actions:
        branch = try_get_current_branch(source_path)
        context = TemplateContext(
            uri=uri,
            branch=branch,
            source_path=source_path,
            dest_path=source_path,
            tags=ctx.tags,
        )
        try:
            actions = apply_actions(config.actions, context, kind="after_clone")
        except Exception as e:  # MatcherError or its base
            print(f"Error matching project rules: {e}", file=sys.stderr)
            actions = []

        if actions:
            ctx.verbose_msg(f"Executing {len(actions)} source action(s)...")
            for action in actions:
                try:
                    action.run(
                        source_dir=None,
                        target_dir=source_path,
                        pass_through_stdout=not ctx.quiet,
                    )
                except ActionError as e:
                    print(f"Error executing source action: {e}", file=sys.stderr)

    ctx.say(str(source_path))

    return 0