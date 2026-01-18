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
# SHARED FUNCTIONS (available in templates, URI predicates, and project predicates):
# ----------------------------------------------------------------------------------
#
# URI Functions:
#   path()               - URI path segments (dual signature)
#                         - path(): returns list of all segments
#                           Example: path() returns ["user", "repo"]
#                           Use path()[0] to access first segment, path()[-1] for last
#                         - path(n): returns single segment at index n
#                           Example: path(-1) returns "repo", path(0) returns "user"
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
#                         Tags are passed via --tag option: gww clone <uri> --tag env=prod
#                         Example: tag("env") returns "prod" if --tag env=prod was used
#
#   tag_exist(name)      - Check if tag exists (returns True/False)
#                         Useful in predicates for conditional routing and path templates
#                         Example: tag_exist("env") returns True if --tag env was used
#
# PROJECT-SPECIFIC FUNCTIONS (only in project predicates):
# ---------------------------------------------------------
#   source_path()        - Absolute path to source repository (string)
#                         Example: source_path() returns "/home/user/Developer/sources/github/user/repo"
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
# Routes repositories to different locations based on URI predicates
# Uncomment and customize as needed:

# sources:
#   github:
#     predicate: '"github" in host()'
#     sources: ~/Developer/sources/github/path(-2)/path(-1)
#     worktrees: ~/Developer/worktrees/github/path(-2)/path(-1)/norm_branch()
#
#   gitlab:
#     predicate: '"gitlab" in host()'
#     sources: ~/Developer/sources/gitlab/path(-3)/path(-2)/path(-1)
#     worktrees: ~/Developer/worktrees/gitlab/path(-3)/path(-2)/path(-1)/norm_branch()
#
#   custom:
#     predicate: 'path()[0] == "myorg"'
#     sources: ~/Developer/sources/custom/path(-2)/path(-1)
#
#   # Tag-based routing examples:
#   review:
#     predicate: 'tag_exist("review")
#     sources: ~/Developer/sources/custom/path(-2)/path(-1)
#     worktrees: ~/Developer/worktrees/review/path(-2)/path(-1)/norm_branch()
#
#   # Tag-based path templates:
#   tagged_sources:
#     predicate: 'tag_exist("worktree-name")'
#     sources: ~/Developer/sources/tag("project")/path(-2)/path(-1)
#     worktrees: ~/Developer/worktrees/tag("project")/path(-2)/path(-1)/branch()-tag("worktree-name")
#
# Project rules (optional)
# Execute actions after clone or worktree creation based on project detection
# Uncomment and customize as needed:

# projects:
#   - predicate: 'file_exists("local.properties")'
#     source_actions:
#       - abs_copy: ["~/sources/default-local.properties", "local.properties"]
#     worktree_actions:
#       - rel_copy: ["local.properties"]
#       - command: ["./setup-env.sh"]
#
#   # Tag-based project actions:
#   - predicate: not file_exists("CLAUDE.md") and tag_exist("use-claude")
#     source_actions:
#       - command: ["claude", "init"]
#     worktree_actions:
#       - rel_copy: ["CLAUDE.md"]
#
#   # Tag-based project actions:
#   - predicate: file_exists("CLAUDE.md") and tag_exist("use-claude") and tag_exist("review")
#     worktree_actions:
#       - command: ["claude", "-p", "/review"] # it's better to create slash command to avoid prompt repetion
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
