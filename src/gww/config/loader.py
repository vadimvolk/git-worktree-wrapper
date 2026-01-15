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
# SGW (Git Worktree Wrapper) Configuration
# =========================================
#
# This file configures how gww manages your git repositories and worktrees.
# Location: {config_path}

# Default paths for sources (cloned repositories) and worktrees
# Template functions available:
#   path(n)            - URI path segment (0-based, negative for reverse)
#   branch()           - Current branch name
#   norm_branch(sep)   - Branch with "/" replaced (default: "-")
#   worktree()         - Worktree name (empty if not named)
#   prefix_worktree(p) - Prefix + worktree name, or empty (default: "-")
#   norm_prefix_branch() - worktree-branch or norm_branch

default_sources: ~/Developer/sources/default/path(-2)/path(-1)
default_worktrees: ~/Developer/worktrees/default/path(-2)/path(-1)/norm_branch()

# Source routing rules (optional)
# Routes repositories to different locations based on URI predicates
# Uncomment and customize as needed:

# sources:
#   github:
#     predicate: '"github" in host'
#     sources: ~/Developer/sources/github/path(-2)/path(-1)
#     worktrees: ~/Developer/worktrees/github/path(-2)/path(-1)/norm_branch()
#
#   gitlab:
#     predicate: '"gitlab" in host'
#     sources: ~/Developer/sources/gitlab/path(-3)/path(-2)/path(-1)
#     worktrees: ~/Developer/worktrees/gitlab/path(-3)/path(-2)/path(-1)/norm_branch()
#
#   custom:
#     predicate: 'path(0) == "myorg"'
#     sources: ~/Developer/sources/custom/path(-2)/path(-1)

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
