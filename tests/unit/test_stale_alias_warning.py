"""Unit tests for the stale-alias startup check.

These cover :func:`gww.cli.commands.init.detect_user_shell` and
:func:`gww.cli.commands.init.warn_if_alias_is_stale`, plus the integration
point in :func:`gww.cli.main.main` that fires the warning before dispatching
any command.

The bug being guarded against: upgrading gww without re-running
``gww init shell <shell>`` leaves a stale ``gwa``/``gwc``/``gwr`` alias
installed, swallowing git's stderr progress. The startup check exists so
the user gets a one-line nudge to regenerate.
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import pytest

from gww.cli.commands.init import detect_user_shell, warn_if_alias_is_stale
from gww.cli.main import main
from gww.utils.shell import (
    generate_bash_aliases,
    generate_fish_aliases,
    generate_zsh_aliases,
)


# ---------------------------------------------------------------------------
# detect_user_shell
# ---------------------------------------------------------------------------


class TestDetectUserShell:
    """``detect_user_shell`` maps ``$SHELL`` to a known shell name."""

    @pytest.mark.parametrize(
        "shell_path, expected",
        [
            ("/bin/bash", "bash"),
            ("/usr/local/bin/bash", "bash"),
            ("/bin/zsh", "zsh"),
            ("/usr/bin/zsh", "zsh"),
            ("/usr/bin/fish", "fish"),
            ("/opt/homebrew/bin/fish", "fish"),
        ],
    )
    def test_known_shells(
        self,
        monkeypatch: pytest.MonkeyPatch,
        shell_path: str,
        expected: str,
    ) -> None:
        """``/path/to/<shell>`` returns the basename."""
        monkeypatch.setenv("SHELL", shell_path)
        assert detect_user_shell() == expected

    @pytest.mark.parametrize(
        "shell_path",
        [
            "/bin/sh",
            "/usr/bin/dash",
            "/usr/bin/tcsh",
            "/usr/bin/powershell",
            "",
        ],
    )
    def test_unknown_shells_return_none(
        self,
        monkeypatch: pytest.MonkeyPatch,
        shell_path: str,
    ) -> None:
        """Unknown or empty ``$SHELL`` returns ``None`` so we silently skip."""
        monkeypatch.setenv("SHELL", shell_path)
        assert detect_user_shell() is None

    def test_unset_shell_returns_none(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """No ``$SHELL`` at all returns ``None`` rather than crashing."""
        monkeypatch.delenv("SHELL", raising=False)
        assert detect_user_shell() is None


# ---------------------------------------------------------------------------
# warn_if_alias_is_stale
# ---------------------------------------------------------------------------


class TestWarnIfAliasIsStale:
    """``warn_if_alias_is_stale`` prints to stderr when the on-disk alias
    file has drifted from the generator output."""

    def _write_stale_alias(
        self,
        home: Path,
        shell: str,
        content: str,
    ) -> Path:
        """Write ``content`` to the alias file the way the user would have
        installed it. Returns the path written to."""
        if shell == "bash":
            target = home / ".bash_completion.d" / "gww-aliases"
        elif shell == "zsh":
            target = home / ".zsh" / "functions" / "gww-aliases"
        else:
            target = home / ".config" / "fish" / "functions" / "gwa.fish"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return target

    def _fresh_alias_content(self, shell: str) -> str:
        if shell == "bash":
            return generate_bash_aliases()
        if shell == "zsh":
            return generate_zsh_aliases()
        return generate_fish_aliases()["gwa"]

    @pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
    def test_no_alias_file_is_silent(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        shell: str,
        capfd: pytest.CaptureFixture[str],
    ) -> None:
        """No alias installed → no warning. We don't pester new users."""
        monkeypatch.setenv("HOME", str(tmp_path))
        warn_if_alias_is_stale(shell)
        captured = capfd.readouterr()
        assert captured.err == ""
        assert captured.out == ""

    @pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
    def test_fresh_alias_is_silent(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        shell: str,
        capfd: pytest.CaptureFixture[str],
    ) -> None:
        """A freshly-installed alias matches the generator → no warning."""
        monkeypatch.setenv("HOME", str(tmp_path))
        self._write_stale_alias(tmp_path, shell, self._fresh_alias_content(shell))
        warn_if_alias_is_stale(shell)
        captured = capfd.readouterr()
        assert captured.err == ""

    @pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
    def test_stale_alias_warns_on_stderr(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        shell: str,
        capfd: pytest.CaptureFixture[str],
    ) -> None:
        """A pre-6e77c6b-style alias file (captures and discards output)
        triggers a one-line reminder pointing at ``gww init shell``."""
        monkeypatch.setenv("HOME", str(tmp_path))
        self._write_stale_alias(
            tmp_path,
            shell,
            "# old alias template — captures output into a discarded var\n"
            "gwa() { local output; output=$(command gww add \"$@\" 2>&1); }\n",
        )

        warn_if_alias_is_stale(shell)

        captured = capfd.readouterr()
        assert captured.out == ""
        assert f"gww init shell {shell}" in captured.err
        assert "out of date" in captured.err

    def test_bash_stale_warns_with_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capfd: pytest.CaptureFixture[str],
    ) -> None:
        """The warning mentions ``gwc/gwa/gwr`` so users know what's broken."""
        monkeypatch.setenv("HOME", str(tmp_path))
        target = self._write_stale_alias(tmp_path, "bash", "gwa() { :; }\n")
        warn_if_alias_is_stale("bash")
        captured = capfd.readouterr()
        assert "gwc" in captured.err
        assert "gwa" in captured.err
        assert "gwr" in captured.err
        assert str(target) in captured.err

    def test_customised_alias_triggers_false_positive(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capfd: pytest.CaptureFixture[str],
    ) -> None:
        """Documented behaviour: if a user hand-edits the alias file, the
        next run will warn because content no longer matches the generator.
        They can safely ignore the reminder or re-apply their changes after
        ``gww init shell`` regenerates the file."""
        monkeypatch.setenv("HOME", str(tmp_path))
        self._write_stale_alias(tmp_path, "bash", "# my customisation\ngwa() { :; }\n")
        warn_if_alias_is_stale("bash")
        captured = capfd.readouterr()
        assert "out of date" in captured.err


# ---------------------------------------------------------------------------
# main() integration
# ---------------------------------------------------------------------------


class TestMainWarnsOnStaleAlias:
    """``main()`` calls :func:`warn_if_alias_is_stale` before dispatching
    a command, but skips the check when the user is regenerating."""

    def _install_stale_bash_alias(self, home: Path) -> Path:
        target = home / ".bash_completion.d" / "gww-aliases"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# stale alias\ngwa() { :; }\n")
        return target

    def test_main_prints_warning_before_dispatching(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capfd: pytest.CaptureFixture[str],
    ) -> None:
        """Running *any* command (here: ``gww --version``) with a stale
        alias prints the warning to stderr."""
        home = tmp_path / "home"
        home.mkdir()
        self._install_stale_bash_alias(home)
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("SHELL", "/bin/bash")
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.delenv("APPDATA", raising=False)

        rc = main(["init", "config"])

        captured = capfd.readouterr()
        assert rc == 0
        assert "out of date" in captured.err

    def test_main_skips_warning_for_init_shell(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capfd: pytest.CaptureFixture[str],
    ) -> None:
        """When the user is regenerating the alias, the staleness check is
        skipped so they don't see ``out of date`` immediately before their
        own ``gww init shell`` writes the fresh file."""
        home = tmp_path / "home"
        home.mkdir()
        self._install_stale_bash_alias(home)
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("SHELL", "/bin/bash")
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.delenv("APPDATA", raising=False)

        rc = main(["init", "shell", "bash"])

        captured = capfd.readouterr()
        assert rc == 0
        # The stale warning would say "out of date"; init shell's own
        # output mentions "Installed bash alias functions" but not the
        # warning phrase.
        assert "out of date" not in captured.err

    def test_main_silent_for_fresh_alias(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capfd: pytest.CaptureFixture[str],
    ) -> None:
        """A user who already re-ran ``gww init shell`` after upgrading
        sees no warning on subsequent ``gww`` invocations."""
        home = tmp_path / "home"
        home.mkdir()
        alias_path = home / ".bash_completion.d" / "gww-aliases"
        alias_path.parent.mkdir(parents=True, exist_ok=True)
        alias_path.write_text(generate_bash_aliases())
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("SHELL", "/bin/bash")
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.delenv("APPDATA", raising=False)

        rc = main(["init", "config"])

        captured = capfd.readouterr()
        assert rc == 0
        assert "out of date" not in captured.err

    def test_main_silent_when_no_alias_installed(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capfd: pytest.CaptureFixture[str],
    ) -> None:
        """Brand-new users (no ``~/.bash_completion.d/gww-aliases``) get no
        warning — we only remind people who *had* an alias that drifted."""
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("SHELL", "/bin/bash")
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.delenv("APPDATA", raising=False)

        rc = main(["init", "config"])

        captured = capfd.readouterr()
        assert rc == 0
        assert "out of date" not in captured.err
