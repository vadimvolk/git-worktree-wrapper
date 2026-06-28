"""Integration tests for generated shell alias functions (gwa, gwc, gwr).

These tests spawn real bash/fish subshells, source the generated alias script,
and verify the "navigate after command" prompt behaves correctly.

Fish tests are skipped automatically when fish is not installed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

from gww.utils.shell import (
    generate_bash_aliases,
    generate_fish_aliases,
    generate_zsh_aliases,
)

SH_BASH = shutil.which("bash")
SH_FISH = shutil.which("fish")
SH_ZSH = shutil.which("zsh")

pytestmark = pytest.mark.integration


def _venv_bin() -> Path:
    """Return the bin directory of the venv running the tests."""
    return Path(sys.executable).parent


def _make_source_repo(tmp_path: Path) -> Path:
    """Build a git repo with a single commit and an origin remote.

    Returns the source working tree (not the bare repo). The ``origin`` remote
    points at a bare clone of itself, so ``gww add`` can resolve the worktree
    path from the configured URI template.
    """
    src = tmp_path / "upstream"
    src.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=src, check=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t"], cwd=src, check=True
    )
    subprocess.run(["git", "config", "user.name", "t"], cwd=src, check=True)
    subprocess.run(
        ["git", "commit", "-q", "--allow-empty", "-m", "init"],
        cwd=src,
        check=True,
    )
    subprocess.run(["git", "checkout", "-q", "-b", "main"], cwd=src, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", f"file://{src}"], cwd=src, check=True
    )
    return src


def _isolated_xdg_config(tmp_path: Path, worktree_dir: Path) -> Path:
    """Create a config file at the platform-appropriate XDG path under a fake HOME.

    Returns the directory that should be set as ``HOME`` for the subprocess
    so that ``gww`` reads our test config instead of the user's real one.
    The gww XDG code in :mod:`gww.utils.xdg` has no env-var override, so
    HOME redirection is the cleanest way to isolate. The config path is
    computed by calling :func:`gww.utils.xdg.user_config_dir` with a
    patched HOME so it matches what the subprocess will look up exactly.
    """
    fake_home = tmp_path / "fakehome"
    fake_home.mkdir(parents=True, exist_ok=True)

    # Compute the config path the same way gww will, so we don't drift
    # from the production XDG logic across platforms / Python versions.
    saved_home = os.environ.get("HOME")
    saved_appdata = os.environ.get("APPDATA")
    saved_xdg = os.environ.get("XDG_CONFIG_HOME")
    os.environ["HOME"] = str(fake_home)
    os.environ.pop("XDG_CONFIG_HOME", None)
    os.environ.pop("APPDATA", None)
    try:
        from gww.utils.xdg import get_config_path  # local import: needs patched env

        config_path = get_config_path()
    finally:
        if saved_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = saved_home
        if saved_xdg is not None:
            os.environ["XDG_CONFIG_HOME"] = saved_xdg
        if saved_appdata is not None:
            os.environ["APPDATA"] = saved_appdata

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        f"default_sources: {config_path.parent}/src\n"
        f"default_worktrees: {worktree_dir}/norm_branch()\n"
    )
    return fake_home


def _run_shell(
    shell: str,
    script: str,
    cwd: Path,
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run ``script`` with ``shell`` in ``cwd``, returning the result."""
    env = os.environ.copy()
    env["PATH"] = f"{_venv_bin()}:{env.get('PATH', '')}"
    env.pop("XDG_CONFIG_HOME", None)
    env.pop("APPDATA", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [shell, "-c", script],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _parse_pwd_marker(output: str, marker: str) -> str:
    """Extract the PWD value associated with ``marker``.

    bash's ``read`` doesn't emit a newline after the prompt, so the
    subsequent ``echo`` can end up on the same line as the prompt text.
    We search the whole output rather than relying on line starts.
    """
    for line in output.splitlines():
        idx = line.find(marker)
        if idx >= 0:
            return line[idx + len(marker) :].strip()
    return ""


def _bash_script(branch: str, reply: str) -> str:
    """A bash script that sources the gwa alias, runs it, and prints PWD.

    Uses process substitution instead of a pipe so that ``gwa`` runs in the
    current shell — bash puts the right side of a pipe in a subshell, which
    would discard any ``cd`` the function performs.
    """
    return dedent(
        f"""
        source "$ALIAS_FILE"
        cd "$SRC_DIR"
        gwa {branch} -c < <(printf '{reply}\\n')
        echo "PWD_AFTER=$PWD"
        """
    ).strip()


def _zsh_script(branch: str, reply: str) -> str:
    """A zsh script that sources the gwa alias, runs it, and prints PWD.

    Same shape as the bash version — zsh also runs the right side of a pipe
    in a subshell, so process substitution keeps the ``cd`` in the parent.
    """
    return dedent(
        f"""
        source "$ALIAS_FILE"
        cd "$SRC_DIR"
        gwa {branch} -c < <(printf '{reply}\\n')
        echo "PWD_AFTER=$PWD"
        """
    ).strip()


def _fish_script(branch: str, reply: str) -> str:
    """A fish script that sources the gwa alias, runs it, and prints PWD.

    Fish propagates ``cd`` from subshells by design, so a plain pipe is fine
    here — the working directory change still reaches the parent shell.
    """
    return dedent(
        f"""
        source $ALIAS_FILE
        cd $SRC_DIR
        printf '{reply}\\n' | gwa {branch} -c
        echo "PWD_AFTER=$PWD"
        """
    ).strip()


class TestBashGwaAlias:
    """Behavioural tests for the generated ``gwa`` function (bash)."""

    def test_yes_answer_cds_into_new_worktree(
        self, tmp_path: Path
    ) -> None:
        """Answering ``y`` to the prompt must ``cd`` into the printed worktree."""
        assert SH_BASH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"
        
        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwa.bash"
        # strip trailing `complete` lines — they need an interactive shell
        alias_file.write_text(
            "\n".join(
                line
                for line in generate_bash_aliases().splitlines()
                if not line.startswith("complete -F")
            )
        )

        result = _run_shell(
            SH_BASH,
            _bash_script("yes-branch", "y"),
            cwd=src,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_DIR": str(src),
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        pwd_after = _parse_pwd_marker(result.stdout, "PWD_AFTER=")
        assert pwd_after.endswith("yes-branch"), (
            f"expected cd into worktree, got PWD={pwd_after!r}, "
            f"stdout={result.stdout!r}"
        )
        assert (Path(pwd_after) / ".git").exists()

    def test_no_answer_stays_put(self, tmp_path: Path) -> None:
        """Answering ``n`` to the prompt must not change the current directory."""
        assert SH_BASH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"
        
        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwa.bash"
        alias_file.write_text(
            "\n".join(
                line
                for line in generate_bash_aliases().splitlines()
                if not line.startswith("complete -F")
            )
        )

        result = _run_shell(
            SH_BASH,
            _bash_script("no-branch", "n"),
            cwd=src,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_DIR": str(src),
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        pwd_after = _parse_pwd_marker(result.stdout, "PWD_AFTER=")
        assert pwd_after == str(src), (
            f"expected to stay at {src}, got PWD={pwd_after!r}"
        )

    def test_prompt_text_is_emitted_on_stdout(
        self, tmp_path: Path
    ) -> None:
        """The ``Navigate to <path>? [Y/n]`` prompt must be visible to the user.

        In bash the prompt is a plain ``printf`` to stdout, so it shows up
        in the captured output.
        """
        assert SH_BASH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"

        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwa.bash"
        alias_file.write_text(
            "\n".join(
                line
                for line in generate_bash_aliases().splitlines()
                if not line.startswith("complete -F")
            )
        )

        result = _run_shell(
            SH_BASH,
            _bash_script("prompt-branch", "n"),
            cwd=src,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_DIR": str(src),
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        assert "Navigate to " in result.stdout, (
            f"expected 'Navigate to ' prompt on stdout, got {result.stdout!r}"
        )
        assert "[Y/n]" in result.stdout

    def test_streams_git_progress_to_stderr(
        self, tmp_path: Path
    ) -> None:
        """``gwa`` must let git's ``Preparing worktree …`` line through to the user.

        The old template captured both stdout and stderr into a variable that
        was discarded on success, swallowing every progress message. The new
        template pipes only stdout through ``tail -n 1`` and lets stderr
        stream straight to the terminal — which in this test framework ends
        up in ``result.stderr``.
        """
        assert SH_BASH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"

        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwa.bash"
        alias_file.write_text(
            "\n".join(
                line
                for line in generate_bash_aliases().splitlines()
                if not line.startswith("complete -F")
            )
        )

        result = _run_shell(
            SH_BASH,
            _bash_script("stream-branch", "n"),
            cwd=src,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_DIR": str(src),
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        assert "Preparing worktree" in result.stderr, (
            f"expected git progress in stderr, got {result.stderr!r}"
        )

    def test_subshell_capture_discards_cd(
        self, tmp_path: Path
    ) -> None:
        """Capturing ``gwa`` in ``$(...)`` runs it in a subshell.

        The ``cd`` inside the subshell does **not** propagate to the parent,
        so PWD is unchanged. This is a bash-only gotcha worth documenting.
        """
        assert SH_BASH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"
        
        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwa.bash"
        alias_file.write_text(
            "\n".join(
                line
                for line in generate_bash_aliases().splitlines()
                if not line.startswith("complete -F")
            )
        )

        script = dedent(
            f"""
            source "$ALIAS_FILE"
            cd "$SRC_DIR"
            OUT=$(printf 'y\\n' | gwa gotcha-branch -c)
            echo "PWD_AFTER=$PWD"
            """
        ).strip()

        result = _run_shell(
            SH_BASH,
            script,
            cwd=src,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_DIR": str(src),
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        pwd_after = _parse_pwd_marker(result.stdout, "PWD_AFTER=")
        assert pwd_after == str(src), (
            "subshell cd should NOT propagate to parent shell (bash semantics)"
        )


@pytest.mark.skipif(SH_ZSH is None, reason="zsh shell not installed")
class TestZshGwaAlias:
    """Behavioural tests for the generated ``gwa`` function (zsh)."""

    @staticmethod
    def _write_alias(path: Path) -> None:
        # strip trailing `compdef` lines — they need an interactive shell
        path.write_text(
            "\n".join(
                line
                for line in generate_zsh_aliases().splitlines()
                if not line.startswith("compdef ")
            )
        )

    def test_yes_answer_cds_into_new_worktree(
        self, tmp_path: Path
    ) -> None:
        """Answering ``y`` to the prompt must ``cd`` into the printed worktree."""
        assert SH_ZSH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"
        
        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwa.zsh"
        self._write_alias(alias_file)

        result = _run_shell(
            SH_ZSH,
            _zsh_script("zsh-yes", "y"),
            cwd=src,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_DIR": str(src),
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        pwd_after = _parse_pwd_marker(result.stdout, "PWD_AFTER=")
        assert pwd_after.endswith("zsh-yes"), (
            f"expected cd into worktree, got PWD={pwd_after!r}"
        )
        assert (Path(pwd_after) / ".git").exists()

    def test_no_answer_stays_put(self, tmp_path: Path) -> None:
        """Answering ``n`` to the prompt must not change the current directory."""
        assert SH_ZSH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"
        
        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwa.zsh"
        self._write_alias(alias_file)

        result = _run_shell(
            SH_ZSH,
            _zsh_script("zsh-no", "n"),
            cwd=src,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_DIR": str(src),
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        pwd_after = _parse_pwd_marker(result.stdout, "PWD_AFTER=")
        assert pwd_after == str(src), (
            f"expected to stay at {src}, got PWD={pwd_after!r}"
        )

    def test_prompt_text_is_emitted_on_stdout(
        self, tmp_path: Path
    ) -> None:
        """The ``Navigate to <path>? [Y/n]`` prompt must be visible to the user.

        In zsh the prompt is a plain ``printf`` to stdout (same as bash), so
        it shows up in the captured output.
        """
        assert SH_ZSH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"

        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwa.zsh"
        self._write_alias(alias_file)

        result = _run_shell(
            SH_ZSH,
            _zsh_script("zsh-prompt", "n"),
            cwd=src,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_DIR": str(src),
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        assert "Navigate to " in result.stdout, (
            f"expected 'Navigate to ' prompt on stdout, got {result.stdout!r}"
        )
        assert "[Y/n]" in result.stdout

    def test_streams_git_progress_to_stderr(
        self, tmp_path: Path
    ) -> None:
        """``gwa`` must let git's ``Preparing worktree …`` line through to the user."""
        assert SH_ZSH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"

        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwa.zsh"
        self._write_alias(alias_file)

        result = _run_shell(
            SH_ZSH,
            _zsh_script("zsh-stream", "n"),
            cwd=src,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_DIR": str(src),
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        assert "Preparing worktree" in result.stderr, (
            f"expected git progress in stderr, got {result.stderr!r}"
        )

    def test_subshell_capture_discards_cd(
        self, tmp_path: Path
    ) -> None:
        """Capturing ``gwa`` in ``$(...)`` runs it in a subshell.

        The ``cd`` inside the subshell does **not** propagate to the parent,
        so PWD is unchanged. zsh shares this bash semantics.
        """
        assert SH_ZSH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"
        
        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwa.zsh"
        self._write_alias(alias_file)

        script = dedent(
            f"""
            source "$ALIAS_FILE"
            cd "$SRC_DIR"
            OUT=$(printf 'y\\n' | gwa zsh-gotcha -c)
            echo "PWD_AFTER=$PWD"
            """
        ).strip()

        result = _run_shell(
            SH_ZSH,
            script,
            cwd=src,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_DIR": str(src),
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        pwd_after = _parse_pwd_marker(result.stdout, "PWD_AFTER=")
        assert pwd_after == str(src), (
            "subshell cd should NOT propagate to parent shell (zsh semantics)"
        )


@pytest.mark.skipif(SH_FISH is None, reason="fish shell not installed")
class TestFishGwaAlias:
    """Behavioural tests for the generated ``gwa`` function (fish)."""

    def test_yes_answer_cds_into_new_worktree(
        self, tmp_path: Path
    ) -> None:
        """Answering ``y`` to the prompt must ``cd`` into the printed worktree."""
        assert SH_FISH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"
        
        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwa.fish"
        alias_file.write_text(generate_fish_aliases()["gwa"])

        result = _run_shell(
            SH_FISH,
            _fish_script("fish-yes", "y"),
            cwd=src,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_DIR": str(src),
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        pwd_after = _parse_pwd_marker(result.stdout, "PWD_AFTER=")
        assert pwd_after.endswith("fish-yes"), (
            f"expected cd into worktree, got PWD={pwd_after!r}"
        )
        assert (Path(pwd_after) / ".git").exists()

    def test_no_answer_stays_put(self, tmp_path: Path) -> None:
        """Answering ``n`` to the prompt must not change the current directory."""
        assert SH_FISH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"
        
        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwa.fish"
        alias_file.write_text(generate_fish_aliases()["gwa"])

        result = _run_shell(
            SH_FISH,
            _fish_script("fish-no", "n"),
            cwd=src,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_DIR": str(src),
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        pwd_after = _parse_pwd_marker(result.stdout, "PWD_AFTER=")
        assert pwd_after == str(src), (
            f"expected to stay at {src}, got PWD={pwd_after!r}"
        )

    def test_subshell_capture_propagates_cd(
        self, tmp_path: Path
    ) -> None:
        """In fish, ``set OUT (gwa ...)`` runs in a subshell but ``cd`` propagates.

        Unlike bash, fish's command substitution does not isolate directory
        state — the parent shell's PWD is updated. This is intentional fish
        behaviour; tests pin it down so changes to the alias can't break it
        silently.
        """
        assert SH_FISH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"
        
        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwa.fish"
        alias_file.write_text(generate_fish_aliases()["gwa"])

        script = dedent(
            f"""
            source $ALIAS_FILE
            cd $SRC_DIR
            set OUT (printf 'y\\n' | gwa fish-gotcha -c)
            echo "PWD_AFTER=$PWD"
            """
        ).strip()

        result = _run_shell(
            SH_FISH,
            script,
            cwd=src,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_DIR": str(src),
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        pwd_after = _parse_pwd_marker(result.stdout, "PWD_AFTER=")
        assert pwd_after.endswith("fish-gotcha"), (
            "fish subshell should propagate cd to parent (fish semantics)"
        )

    def test_streams_git_progress_to_stderr(
        self, tmp_path: Path
    ) -> None:
        """``gwa`` must let git's ``Preparing worktree …`` line through to the user."""
        assert SH_FISH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"

        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwa.fish"
        alias_file.write_text(generate_fish_aliases()["gwa"])

        result = _run_shell(
            SH_FISH,
            _fish_script("fish-stream", "n"),
            cwd=src,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_DIR": str(src),
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        assert "Preparing worktree" in result.stderr, (
            f"expected git progress in stderr, got {result.stderr!r}"
        )
