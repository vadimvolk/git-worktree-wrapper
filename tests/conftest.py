"""Shared pytest fixtures and helpers for the gww test suite."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from gww.cli.context import CommandContext


@pytest.fixture
def config_dir(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Point gww's config lookup at a temporary directory.

    Returns the temp directory; the patched config file lives at
    ``<config_dir>/gww/config.yml``. Each test that depends on this fixture
    gets an isolated config so tests cannot leak into each other.
    """
    config_path = tmp_path_factory.mktemp("config")
    test_config_file = config_path / "gww" / "config.yml"

    monkeypatch.setattr(
        "gww.utils.xdg.get_config_path",
        lambda appname: test_config_file,
    )
    monkeypatch.setattr(
        "gww.config.loader.get_config_path",
        lambda: test_config_file,
    )
    monkeypatch.setattr(
        "gww.cli.commands.init.get_config_path",
        lambda: test_config_file,
    )

    return config_path


def make_ctx(**kwargs: Any) -> CommandContext:
    """Build a :class:`CommandContext` from keyword arguments.

    Convenience helper used by integration tests that previously constructed
    a small ``class Args`` namespace inline. Normalises a few fields so tests
    can pass them in their natural shape (``str`` instead of ``list[str]``).
    """
    if "old_repos" in kwargs and isinstance(kwargs["old_repos"], str):
        kwargs["old_repos"] = [kwargs["old_repos"]]
    return CommandContext(**kwargs)