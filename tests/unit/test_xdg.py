"""Unit tests for :mod:`gww.utils.xdg`.

Locks in the documented behavior from ADR 0003:

- ``$XDG_CONFIG_HOME`` is honored on every platform when set to an
  absolute path.
- Otherwise the platform default is used
  (``~/.config``, ``~/Library/Application Support``,
  ``%APPDATA%``).
- ``$XDG_CONFIG_HOME`` must be an absolute path; relative or empty
  values fall back to the platform default.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from gww.utils.xdg import APP_NAME, ensure_config_dir, get_config_path, user_config_dir

pytestmark = pytest.mark.unit


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect ``$HOME`` to a temp directory for the duration of a test."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    return fake_home


@pytest.fixture
def platform_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")


@pytest.fixture
def platform_macos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")


@pytest.fixture
def platform_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("APPDATA", raising=False)


class TestLinux:
    """Linux uses ``$XDG_CONFIG_HOME`` when set, else ``~/.config``."""

    def test_default_uses_dotconfig(
        self,
        home: Path,
        platform_linux: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        assert user_config_dir() == home / ".config" / APP_NAME

    def test_xdg_absolute_overrides_default(
        self,
        home: Path,
        platform_linux: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", "/custom/cfg")
        assert user_config_dir() == Path("/custom/cfg") / APP_NAME

    def test_xdg_empty_falls_back_to_dotconfig(
        self,
        home: Path,
        platform_linux: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", "")
        assert user_config_dir() == home / ".config" / APP_NAME

    def test_xdg_relative_falls_back_to_dotconfig(
        self,
        home: Path,
        platform_linux: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", "relative/cfg")
        assert user_config_dir() == home / ".config" / APP_NAME

    def test_xdg_with_tilde_is_relative_and_ignored(
        self,
        home: Path,
        platform_linux: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A path starting with ``~`` is not absolute (no expansion here)
        and must be rejected."""
        monkeypatch.setenv("XDG_CONFIG_HOME", "~/cfg")
        assert user_config_dir() == home / ".config" / APP_NAME


class TestMacos:
    """macOS defaults to ``~/Library/Application Support`` but honors
    ``$XDG_CONFIG_HOME`` when set to an absolute path."""

    def test_default_uses_library_application_support(
        self,
        home: Path,
        platform_macos: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        assert (
            user_config_dir()
            == home / "Library" / "Application Support" / APP_NAME
        )

    def test_xdg_absolute_overrides_default(
        self,
        home: Path,
        platform_macos: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """This is the behavior change: macOS now respects
        ``$XDG_CONFIG_HOME`` instead of silently using the Apple
        default."""
        monkeypatch.setenv("XDG_CONFIG_HOME", "/xdg/cfg")
        assert user_config_dir() == Path("/xdg/cfg") / APP_NAME

    def test_xdg_empty_falls_back_to_library(
        self,
        home: Path,
        platform_macos: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", "")
        assert (
            user_config_dir()
            == home / "Library" / "Application Support" / APP_NAME
        )

    def test_xdg_relative_falls_back_to_library(
        self,
        home: Path,
        platform_macos: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", "relative/cfg")
        assert (
            user_config_dir()
            == home / "Library" / "Application Support" / APP_NAME
        )


class TestWindows:
    """Windows defaults to ``%APPDATA%`` (or ``~/AppData/Roaming``) but
    honors ``$XDG_CONFIG_HOME`` when set to an absolute path."""

    def test_default_uses_appdata_env(
        self,
        home: Path,
        platform_windows: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("APPDATA", r"C:\Users\me\AppData\Roaming")
        assert (
            user_config_dir()
            == Path(r"C:\Users\me\AppData\Roaming") / APP_NAME
        )

    def test_default_falls_back_to_home_when_appdata_unset(
        self,
        home: Path,
        platform_windows: None,
    ) -> None:
        assert user_config_dir() == home / "AppData" / "Roaming" / APP_NAME

    def test_xdg_absolute_overrides_default(
        self,
        home: Path,
        platform_windows: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Windows also honors ``$XDG_CONFIG_HOME`` when the user sets
        it."""
        monkeypatch.setenv("APPDATA", r"C:\Users\me\AppData\Roaming")
        monkeypatch.setenv("XDG_CONFIG_HOME", "/xdg/cfg")
        assert user_config_dir() == Path("/xdg/cfg") / APP_NAME

    def test_xdg_relative_falls_back_to_appdata(
        self,
        home: Path,
        platform_windows: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("APPDATA", r"C:\Users\me\AppData\Roaming")
        monkeypatch.setenv("XDG_CONFIG_HOME", "relative/cfg")
        assert (
            user_config_dir()
            == Path(r"C:\Users\me\AppData\Roaming") / APP_NAME
        )


class TestGetConfigPath:
    """``get_config_path`` appends ``config.yml`` to the config dir."""

    def test_appends_config_yml(
        self,
        home: Path,
        platform_linux: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        assert get_config_path() == home / ".config" / APP_NAME / "config.yml"

    def test_respects_xdg(
        self,
        home: Path,
        platform_macos: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", "/xdg/cfg")
        assert get_config_path() == Path("/xdg/cfg") / APP_NAME / "config.yml"

    def test_custom_appname(
        self,
        home: Path,
        platform_linux: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        assert get_config_path("other") == home / ".config" / "other" / "config.yml"


class TestEnsureConfigDir:
    """``ensure_config_dir`` creates the directory if missing."""

    def test_creates_directory(
        self,
        tmp_path: Path,
        platform_linux: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

        target = user_config_dir()
        assert not target.exists()

        created = ensure_config_dir()
        assert created == target
        assert created.is_dir()

    def test_existing_directory_is_left_alone(
        self,
        home: Path,
        platform_linux: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        target = user_config_dir()
        target.mkdir(parents=True)
        sentinel = target / "keep-me"
        sentinel.write_text("hi")

        ensure_config_dir()

        assert sentinel.read_text() == "hi"