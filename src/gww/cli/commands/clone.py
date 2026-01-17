"""Clone command implementation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from gww.actions.executor import ActionError, execute_actions
from gww.actions.matcher import MatcherError, get_source_actions
from gww.config.loader import ConfigLoadError, ConfigNotFoundError, load_config
from gww.config.resolver import ResolverError, resolve_source_path
from gww.config.validator import ConfigValidationError, validate_config
from gww.git.repository import GitCommandError, clone_repository
from gww.utils.uri import ParsedURI, parse_uri


def run_clone(args: argparse.Namespace) -> int:
    """Execute the clone command.

    Args:
        args: Parsed command line arguments.

    Returns:
        Exit code (0 for success, 1 for error, 2 for config error).
    """
    uri_str = args.uri
    verbose = getattr(args, "verbose", 0)
    quiet = getattr(args, "quiet", False)
    tags = getattr(args, "tags", {})

    # Parse URI
    try:
        uri = parse_uri(uri_str)
    except ValueError as e:
        print(f"Error: Invalid repository URI: {e}", file=sys.stderr)
        return 1

    # Load and validate config
    try:
        raw_config = load_config()
        config = validate_config(raw_config)
    except ConfigNotFoundError:
        print(
            "Error: Config file not found. Run 'gww init config' to create one.",
            file=sys.stderr,
        )
        return 2
    except ConfigLoadError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except ConfigValidationError as e:
        print(f"Config validation error: {e}", file=sys.stderr)
        return 2

    # Resolve source path
    try:
        source_path = resolve_source_path(config, uri, tags)
    except ResolverError as e:
        print(f"Error resolving source path: {e}", file=sys.stderr)
        return 2

    # Check if already exists
    if source_path.exists():
        print(f"Error: Repository already exists at: {source_path}", file=sys.stderr)
        return 1

    if verbose > 0 and not quiet:
        print(f"Cloning {uri_str} to {source_path}...", file=sys.stderr)

    # Clone repository
    try:
        clone_repository(uri_str, source_path)
    except GitCommandError as e:
        print(f"Error cloning repository: {e}", file=sys.stderr)
        return 1

    # Execute source actions if any project rules match
    if config.projects:
        try:
            actions = get_source_actions(config.projects, source_path, tags)
            if actions:
                if verbose > 0 and not quiet:
                    print(f"Executing {len(actions)} source action(s)...", file=sys.stderr)
                execute_actions(actions, None, source_path)
        except MatcherError as e:
            print(f"Error matching project rules: {e}", file=sys.stderr)
            # Continue - clone succeeded, just actions failed
        except ActionError as e:
            print(f"Error executing source action: {e}", file=sys.stderr)
            # Continue - clone succeeded, just actions failed

    # Output clone path
    if not quiet:
        print(source_path)

    return 0
