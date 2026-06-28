"""Init commands implementation (config and shell)."""

from __future__ import annotations

import sys

from gww.cli.context import CommandContext, CommandExit, exit_on_error
from gww.config.loader import config_exists, get_default_config
from gww.utils.shell import (
    get_installation_instructions,
    install_aliases,
    install_completion,
)
from gww.utils.xdg import get_config_path


@exit_on_error
def run_init_config(ctx: CommandContext) -> int:
    """Execute the init config command.

    Args:
        ctx: Per-invocation command context.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    config_path = get_config_path()

    if config_exists():
        print(
            f"Config file already exists at: {config_path}\n"
            "Not overwriting.",
            file=sys.stderr,
        )
        return 1

    default_content = get_default_config(config_path)

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(default_content)
    except OSError as e:
        raise CommandExit(1, f"Error creating config file: {e}") from e

    ctx.say(f"Created config file: {config_path}")

    return 0


@exit_on_error
def run_init_shell(ctx: CommandContext) -> int:
    """Execute the init shell command.

    Args:
        ctx: Per-invocation command context.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    if ctx.shell is None:
        raise CommandExit(1, "Error: Missing shell name.")

    valid_shells = {"bash", "zsh", "fish"}
    if ctx.shell not in valid_shells:
        raise CommandExit(
            1,
            f"Error: Invalid shell '{ctx.shell}'. "
            f"Must be one of: {', '.join(sorted(valid_shells))}",
        )

    try:
        completion_path = install_completion(ctx.shell)
    except (ValueError, OSError) as e:
        raise CommandExit(1, f"Error: {e}") from e

    try:
        aliases_path = install_aliases(ctx.shell)
    except (ValueError, OSError) as e:
        raise CommandExit(1, f"Error: {e}") from e

    if not ctx.quiet:
        instructions = get_installation_instructions(ctx.shell, completion_path, aliases_path)
        print(instructions)

    return 0