"""CLI entry point and argument parser structure."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from gww import __version__


def create_parser() -> argparse.ArgumentParser:
    """Create the main argument parser with all subcommands.

    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        prog="gww",
        description="Git Worktree Wrapper - manage git worktrees with configurable paths",
        epilog="Run 'gww <command> --help' for more information on a specific command.",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    parser.add_argument(
        "-v", "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (can be repeated)",
    )

    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress non-error output",
    )

    parser.add_argument(
        "-t", "--tag",
        action="append",
        default=[],
        help="Tag in format key=value or just key (can be specified multiple times)",
        metavar="TAG",
    )

    # Create subparsers for commands
    subparsers = parser.add_subparsers(
        dest="command",
        title="commands",
        metavar="<command>",
    )

    # clone command
    clone_parser = subparsers.add_parser(
        "clone",
        help="Clone a repository to configured location",
        description="Clone a git repository to the location determined by configuration rules.",
    )
    clone_parser.add_argument(
        "uri",
        help="Git repository URI (HTTP, HTTPS, SSH, or file://)",
    )
    clone_parser.add_argument(
        "-t", "--tag",
        action="append",
        default=[],
        help="Tag in format key=value or just key (can be specified multiple times)",
        metavar="TAG",
    )

    # add command
    add_parser = subparsers.add_parser(
        "add",
        help="Add a worktree for a branch",
        description="Add a worktree for the specified branch.",
    )
    add_parser.add_argument(
        "branch",
        help="Branch name to checkout in worktree",
    )
    add_parser.add_argument(
        "-c", "--create-branch",
        action="store_true",
        help="Create branch from current commit if it doesn't exist",
    )
    add_parser.add_argument(
        "-t", "--tag",
        action="append",
        default=[],
        help="Tag in format key=value or just key (can be specified multiple times)",
        metavar="TAG",
    )

    # remove command
    remove_parser = subparsers.add_parser(
        "remove",
        help="Remove a worktree",
        description="Remove a worktree by branch name or path.",
    )
    remove_parser.add_argument(
        "branch_or_path",
        help="Branch name or absolute path to worktree",
    )
    remove_parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Force removal even if worktree has uncommitted changes",
    )

    # pull command
    pull_parser = subparsers.add_parser(
        "pull",
        help="Update source repository",
        description="Pull changes from remote in the source repository.",
    )

    # migrate command
    migrate_parser = subparsers.add_parser(
        "migrate",
        help="Migrate repositories to new locations",
        description="Scan directory for repositories and migrate them based on current configuration.",
    )
    migrate_parser.add_argument(
        "old_repos",
        help="Path to directory containing old repositories",
    )
    migrate_parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="Show what would be migrated without making changes",
    )
    migrate_parser.add_argument(
        "--move",
        action="store_true",
        help="Move repositories instead of copying",
    )

    # init command (with subcommands)
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize config or shell completion",
        description="Create default configuration file or install shell completion.",
    )

    init_subparsers = init_parser.add_subparsers(
        dest="init_command",
        title="init commands",
        metavar="<init_command>",
    )

    # init config
    init_config_parser = init_subparsers.add_parser(
        "config",
        help="Create default configuration file",
        description="Create a default configuration file with examples and documentation.",
    )

    # init shell
    init_shell_parser = init_subparsers.add_parser(
        "shell",
        help="Install shell completion",
        description="Generate and install shell autocompletion script.",
    )
    init_shell_parser.add_argument(
        "shell",
        choices=["bash", "zsh", "fish"],
        help="Shell to install completion for",
    )

    return parser


def _parse_tags(tag_args: list[str]) -> dict[str, str]:
    """Parse tag arguments into a dictionary.

    Args:
        tag_args: List of tag strings in format "key=value" or "key".

    Returns:
        Dictionary mapping tag keys to values (empty string if no value).
    """
    tags: dict[str, str] = {}
    for tag_arg in tag_args:
        if "=" in tag_arg:
            key, value = tag_arg.split("=", 1)
            tags[key] = value
        else:
            tags[tag_arg] = ""
    return tags


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Main entry point for gww CLI.

    Args:
        argv: Command line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 for success, 1 for error, 2 for config error).
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    # Parse tags into dictionary
    args.tags = _parse_tags(args.tag)

    if args.command is None:
        parser.print_help()
        return 0

    # Import and run command handlers
    try:
        if args.command == "clone":
            from gww.cli.commands.clone import run_clone
            return run_clone(args)

        elif args.command == "add":
            from gww.cli.commands.add import run_add
            return run_add(args)

        elif args.command == "remove":
            from gww.cli.commands.remove import run_remove
            return run_remove(args)

        elif args.command == "pull":
            from gww.cli.commands.pull import run_pull
            return run_pull(args)

        elif args.command == "migrate":
            from gww.cli.commands.migrate import run_migrate
            return run_migrate(args)

        elif args.command == "init":
            if args.init_command is None:
                # Show init help
                parser.parse_args(["init", "--help"])
                return 0

            if args.init_command == "config":
                from gww.cli.commands.init import run_init_config
                return run_init_config(args)

            elif args.init_command == "shell":
                from gww.cli.commands.init import run_init_shell
                return run_init_shell(args)

        else:
            parser.print_help()
            return 1

    except KeyboardInterrupt:
        print("\nOperation cancelled.", file=sys.stderr)
        return 130

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose > 0:
            import traceback
            traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
