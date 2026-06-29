"""Clone command implementation."""

from __future__ import annotations

from gww.actions import ActionError, MatcherError, apply_actions
from gww.cli.context import (
    CommandContext,
    CommandExit,
    RuleFailure,
    exit_on_error,
    load_config_or_exit,
    parse_uri_or_exit,
    print_action_failure_summary,
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
        Exit code (0 for success, 1 for runtime/action failure, 2 for config
        error).
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

    failures: list[RuleFailure] = []
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
            rule_bundles = apply_actions(config.actions, context, kind="after_clone")
        except MatcherError as e:
            raise CommandExit(2, f"Config error: {e}") from e

        if rule_bundles:
            ctx.verbose_msg(f"Executing {len(rule_bundles)} rule(s)...")
            for bundle in rule_bundles:
                for action in bundle.actions:
                    try:
                        action.run(
                            source_dir=None,
                            target_dir=source_path,
                            pass_through_stdout=not ctx.quiet,
                        )
                    except ActionError as e:
                        failures.append(RuleFailure(bundle, action, e))
                        if bundle.critical:
                            break

    if failures:
        print_action_failure_summary(failures)

    if not failures:
        ctx.say(str(source_path))

    if any(f.bundle.critical for f in failures):
        raise CommandExit(1, "")
    return 0