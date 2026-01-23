"""Init commands implementation (config and shell)."""

from __future__ import annotations

import argparse
import sys

from gww.config.loader import config_exists, get_default_config, save_config
from gww.utils.shell import (
    generate_completion,
    get_completion_path,
    get_installation_instructions,
    install_aliases,
    install_completion,
)
from gww.utils.xdg import get_config_path


def run_init_config(args: argparse.Namespace) -> int:
    """Execute the init config command.

    Args:
        args: Parsed command line arguments.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    verbose = getattr(args, "verbose", 0)
    quiet = getattr(args, "quiet", False)

    config_path = get_config_path()

    # Check if config already exists
    if config_exists():
        print(
            f"Config file already exists at: {config_path}\n"
            "Not overwriting.",
            file=sys.stderr,
        )
        return 1

    # Get default config content
    default_content = get_default_config(config_path)

    # Write config file
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(default_content)
    except OSError as e:
        print(f"Error creating config file: {e}", file=sys.stderr)
        return 1

    if not quiet:
        print(f"Created config file: {config_path}")

    return 0


def run_init_shell(args: argparse.Namespace) -> int:
    """Execute the init shell command.

    Args:
        args: Parsed command line arguments.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    shell = args.shell
    verbose = getattr(args, "verbose", 0)
    quiet = getattr(args, "quiet", False)

    # Validate shell
    valid_shells = {"bash", "zsh", "fish"}
    if shell not in valid_shells:
        print(
            f"Error: Invalid shell '{shell}'. Must be one of: {', '.join(sorted(valid_shells))}",
            file=sys.stderr,
        )
        return 1

    # Install completion
    try:
        completion_path = install_completion(shell)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"Error installing completion: {e}", file=sys.stderr)
        return 1

    # Install aliases
    try:
        aliases_path = install_aliases(shell)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"Error installing aliases: {e}", file=sys.stderr)
        return 1

    # Print instructions
    if not quiet:
        instructions = get_installation_instructions(shell, completion_path, aliases_path)
        print(instructions)

    return 0
