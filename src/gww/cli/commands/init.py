"""Init commands implementation (config and shell)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from gww.cli.context import CommandContext, CommandExit, exit_on_error
from gww.config.loader import config_exists, get_default_config
from gww.utils.shell import (
    generate_bash_aliases,
    generate_fish_aliases,
    generate_zsh_aliases,
    get_aliases_path,
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


def detect_user_shell() -> str | None:
    """Return the user's current shell name, or ``None`` if undetectable.

    Reads ``$SHELL`` and extracts the basename (``/bin/bash`` → ``bash``).
    Returns ``None`` for unknown shells so callers can silently skip
    staleness checks rather than guess.
    """
    shell_path = os.environ.get("SHELL", "")
    basename = os.path.basename(shell_path)
    if basename in {"bash", "zsh", "fish"}:
        return basename
    return None


def warn_if_alias_is_stale(shell: str) -> None:
    """Warn on stderr if the installed alias file predates the current source.

    Compares the on-disk alias file to what :func:`gww.utils.shell` would
    generate today. If they differ, prints a one-line reminder to re-run
    ``gww init shell <shell>``. Silently does nothing when:

    * no alias file exists yet — we don't pester first-time installers;
    * the file already matches the current generator output.

    Args:
        shell: Shell name (``"bash"``, ``"zsh"``, or ``"fish"``).
    """
    aliases_path = get_aliases_path(shell)

    if shell == "fish":
        assert isinstance(aliases_path, dict)
        target = aliases_path["gwa"]
        if not target.exists():
            return
        installed = target.read_text()
        expected = generate_fish_aliases()["gwa"]
        location = str(target)
    else:
        assert isinstance(aliases_path, Path)
        if not aliases_path.exists():
            return
        installed = aliases_path.read_text()
        expected = (
            generate_bash_aliases() if shell == "bash" else generate_zsh_aliases()
        )
        location = str(aliases_path)

    if installed != expected:
        print(
            f"gww: shell aliases at {location} are out of date — "
            f"re-run 'gww init shell {shell}' to pick up the latest "
            f"gwc/gwa/gwr.",
            file=sys.stderr,
        )