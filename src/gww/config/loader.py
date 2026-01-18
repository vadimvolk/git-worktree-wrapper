"""Configuration file loading using ruamel.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from gww.utils.xdg import get_config_path


class ConfigLoadError(Exception):
    """Raised when config file cannot be loaded."""

    pass


class ConfigNotFoundError(ConfigLoadError):
    """Raised when config file does not exist."""

    pass


def _create_yaml() -> YAML:
    """Create a YAML instance configured for round-trip parsing.

    Returns:
        Configured YAML instance.
    """
    yaml = YAML(typ="rt")  # Round-trip mode preserves comments and formatting
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def load_config(config_path: Optional[Path] = None) -> dict[str, Any]:
    """Load configuration from YAML file.

    Args:
        config_path: Path to config file. If None, uses default XDG path.

    Returns:
        Parsed configuration dictionary.

    Raises:
        ConfigNotFoundError: If config file does not exist.
        ConfigLoadError: If config file cannot be parsed.
    """
    if config_path is None:
        config_path = get_config_path()

    if not config_path.exists():
        raise ConfigNotFoundError(f"Config file not found: {config_path}")

    yaml = _create_yaml()

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.load(f)
    except YAMLError as e:
        raise ConfigLoadError(f"Invalid YAML in config file {config_path}: {e}") from e
    except OSError as e:
        raise ConfigLoadError(f"Cannot read config file {config_path}: {e}") from e

    if data is None:
        # Empty file or only comments
        return {}

    if not isinstance(data, dict):
        raise ConfigLoadError(
            f"Config file must contain a mapping, got {type(data).__name__}"
        )

    return dict(data)


def save_config(config: dict[str, Any], config_path: Optional[Path] = None) -> Path:
    """Save configuration to YAML file.

    Args:
        config: Configuration dictionary to save.
        config_path: Path to config file. If None, uses default XDG path.

    Returns:
        Path where config was saved.

    Raises:
        ConfigLoadError: If config file cannot be written.
    """
    if config_path is None:
        config_path = get_config_path()

    # Ensure parent directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    yaml = _create_yaml()

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f)
    except OSError as e:
        raise ConfigLoadError(f"Cannot write config file {config_path}: {e}") from e

    return config_path


def config_exists(config_path: Optional[Path] = None) -> bool:
    """Check if config file exists.

    Args:
        config_path: Path to config file. If None, uses default XDG path.

    Returns:
        True if config file exists.
    """
    if config_path is None:
        config_path = get_config_path()
    return config_path.exists()


DEFAULT_CONFIG_TEMPLATE = """\
# GWW (Git Worktree Wrapper) Configuration
# =========================================
#
# This file configures how gww manages your git repositories and worktrees.
# Location: {config_path}

# Template Functions and Variables Available
# ===========================================
#
# SHARED FUNCTIONS (available in templates and 'when' conditions):
# ----------------------------------------------------------------------------------
#
# URI Functions:
#   path(n)              - URI path segment at index n (0-based, negative for reverse)
#                         Example: path(-1) returns "repo", path(0) returns "user"
#
#   host()               - URI hostname (string)
#                         Example: host() returns "github.com" from "https://github.com/user/repo"
#
#   uri()                - Full URI string (string)
#                         Example: uri() returns "https://github.com/user/repo.git"
#
#   port()               - URI port number (string, empty if not specified)
#                         Example: port() returns "3000" from "http://git.example.com:3000/path"
#
#   protocol()           - URI protocol/scheme (string)
#                         Example: protocol() returns "https", "ssh", "git"
#
# Branch Functions (require branch context, available in worktree templates):
#   branch()             - Current branch name (as-is)
#                         Example: branch() from "feature/new-ui" → "feature/new-ui"
#
#   norm_branch(sep)     - Branch name with "/" replaced
#                         - norm_branch(): replaces "/" with "-"
#                         - norm_branch("_"): replaces "/" with "_"
#                         Example: norm_branch() from "feature/new-ui" → "feature-new-ui"
#
# Tag Functions:
#   tag(name)            - Get tag value by name (returns empty string if not set)
#                         Tags are passed via --tag option
#                         Example: tag("env") returns "prod" if --tag env=prod was used
#
#   tag_exist(name)      - Check if tag exists (returns True/False)
#                         Useful in 'when' conditions for conditional routing and path templates
#                         Example: tag_exist("env") returns True if --tag env was used
#
# PROJECT-SPECIFIC FUNCTIONS (only in project 'when' conditions):
# ---------------------------------------------------------
#   source_path()        - Absolute path to current repository or worktree root (string)
#                         Detects repository based on current working directory:
#                         - If in source repository: returns source repository root
#                         - If in worktree: returns worktree root
#                         - If in subdirectory: finds and returns repository/worktree root
#                         - If not in git repository: returns empty string
#                         Examples:
#                           source_path() returns "/home/user/Developer/sources/github/user/repo"
#                           source_path() returns "/home/user/Developer/worktrees/github/user/repo/feature-branch"
#
#   dest_path()          - Absolute path to destination (clone target or worktree) (string)
#                         Returns the destination path based on operation context:
#                         - During clone: returns source_path (same as source_path())
#                         - During add: returns the worktree path
#                         Useful for commands that need the operation's output location
#                         Examples:
#                           After clone: dest_path() returns "/home/user/Developer/sources/github/user/repo"
#                           After add: dest_path() returns "/home/user/Developer/worktrees/github/user/repo/feature-branch"
#
#   file_exists(path)    - Check if file exists in source repository (returns True/False)
#                         Path is relative to source repository root
#                         Example: file_exists("package.json") checks for package.json in repo
#
#   dir_exists(path)     - Check if directory exists in source repository (returns True/False)
#                         Path is relative to source repository root
#                         Example: dir_exists("src") checks for src/ directory in repo
#
#   path_exists(path)    - Check if path exists (file or directory) in source repository
#                         Path is relative to source repository root
#                         Example: path_exists("README.md") checks for README.md in repo

# Default paths for sources (cloned repositories) and worktrees
default_sources: ~/Developer/sources/default/path(-2)/path(-1)
default_worktrees: ~/Developer/worktrees/default/path(-2)/path(-1)/norm_branch()

# Source routing rules (optional)
# Routes repositories to different locations based on URI conditions
# Uncomment and customize as needed:

# sources:
#   github:
#     when: '"github" in host()'
#     sources: ~/Developer/sources/github/path(-2)/path(-1)
#     worktrees: ~/Developer/worktrees/github/path(-2)/path(-1)/norm_branch()
#
#   gitlab:
#     when: '"gitlab" in host()'
#     sources: ~/Developer/sources/gitlab/path(-3)/path(-2)/path(-1)
#     worktrees: ~/Developer/worktrees/gitlab/path(-3)/path(-2)/path(-1)/norm_branch()
#
#   custom:
#     when: 'path(0) == "myorg"'
#     sources: ~/Developer/sources/custom/path(-2)/path(-1)
#
#   # Tag-based routing examples:
#   review:
#     when: 'tag_exist("review")
#     sources: ~/Developer/sources/custom/path(-2)/path(-1)
#     worktrees: ~/Developer/worktrees/review/path(-2)/path(-1)/norm_branch()
#
#   # Tag-based path templates:
#   tagged_sources:
#     when: 'tag_exist("worktree-name")'
#     sources: ~/Developer/sources/tag("project")/path(-2)/path(-1)
#     worktrees: ~/Developer/worktrees/tag("project")/path(-2)/path(-1)/branch()-tag("worktree-name")
#
# Actions (optional)
# Execute actions after clone or worktree creation based on project detection
#
# Command action syntax:
#   - command: "single string with optional template functions"
#   - Template functions are evaluated first, then the string is parsed as shell arguments
#   - Commands always execute with dest_path() as the current working directory
#   - Use quotes for arguments with spaces: command: "echo 'hello world'"
#   - Available functions: dest_path(), source_path(), tag("name"), etc.
#
# Uncomment and customize as needed:

# actions:
#   - when: 'file_exists("local.properties")'
#     after_clone:
#       - abs_copy: ["~/sources/default-local.properties", "local.properties"]
#     after_add:
#       - rel_copy: ["local.properties"]
#       - command: "./setup-env.sh"
#
#   # Tag-based actions:
#   - when: not file_exists("CLAUDE.md") and tag_exist("use-claude")
#     after_clone:
#       - command: "claude init"
#     after_add:
#       - rel_copy: ["CLAUDE.md"]
#
#   # Commands with template functions:
#   - when: file_exists("CLAUDE.md") and tag_exist("use-claude") and tag_exist("review")
#     after_add:
#       - command: "claude -p tag('prompt') --cwd dest_path()"
#
#   # Simple command with dest_path:
#   - when: 'file_exists("package.json")'
#     after_add:
#       - command: "npm install --prefix dest_path()"
"""


def get_default_config(config_path: Optional[Path] = None) -> str:
    """Get default configuration file content.

    Args:
        config_path: Path where config will be saved (for documentation).

    Returns:
        Default configuration YAML content.
    """
    if config_path is None:
        config_path = get_config_path()
    return DEFAULT_CONFIG_TEMPLATE.format(config_path=config_path)
