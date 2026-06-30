"""XDG Base Directory specification handling for cross-platform config paths."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "gww"


def user_config_dir(appname: str = APP_NAME) -> Path:
    """Return cross-platform config directory following XDG/OS conventions.

    On every platform, ``$XDG_CONFIG_HOME`` is honored when set to an
    absolute path (per the XDG Base Directory spec). Otherwise the
    platform default is used:

    - Linux: ``~/.config/{appname}``
    - macOS: ``~/Library/Application Support/{appname}``
    - Windows: ``%APPDATA%/{appname}`` (falling back to
      ``~/AppData/Roaming/{appname}``)

    Args:
        appname: Application name for the config subdirectory.

    Returns:
        Path to the application config directory.
    """
    home = Path.home()

    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg and Path(xdg).is_absolute():
        return Path(xdg) / appname

    platform = sys.platform

    if platform.startswith("win"):
        base = os.environ.get("APPDATA", str(home / "AppData" / "Roaming"))
        return Path(base) / appname

    if platform == "darwin":
        return home / "Library" / "Application Support" / appname

    return home / ".config" / appname


def get_config_path(appname: str = APP_NAME) -> Path:
    """Return full path to config file.

    Args:
        appname: Application name for the config subdirectory.

    Returns:
        Path to config.yml in the user config directory.
    """
    return user_config_dir(appname) / "config.yml"


def ensure_config_dir(appname: str = APP_NAME) -> Path:
    """Ensure config directory exists, creating it if necessary.

    Args:
        appname: Application name for the config subdirectory.

    Returns:
        Path to the existing or newly created config directory.
    """
    config_dir = user_config_dir(appname)
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir