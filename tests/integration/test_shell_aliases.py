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


def _bash_script_clone(reply: str) -> str:
    """Bash script that sources the alias file, runs ``gwc`` on ``$SRC_URI``.

    Uses process substitution so ``gwc`` runs in the current shell (otherwise
    the right side of a pipe runs in a subshell and any ``cd`` is lost).
    """
    return dedent(
        f"""
        source "$ALIAS_FILE"
        gwc "$SRC_URI" < <(printf '{reply}\\n')
        echo "PWD_AFTER=$PWD"
        """
    ).strip()


def _zsh_script_clone(reply: str) -> str:
    """Zsh script that sources the alias file, runs ``gwc`` on ``$SRC_URI``."""
    return dedent(
        f"""
        source "$ALIAS_FILE"
        gwc "$SRC_URI" < <(printf '{reply}\\n')
        echo "PWD_AFTER=$PWD"
        """
    ).strip()


def _fish_script_clone(reply: str) -> str:
    """Fish script that sources the alias file, runs ``gwc`` on ``$SRC_URI``.

    Fish propagates ``cd`` from subshells, so a plain pipe is enough.
    """
    return dedent(
        f"""
        source $ALIAS_FILE
        printf '{reply}\\n' | gwc $SRC_URI
        echo "PWD_AFTER=$PWD"
        """
    ).strip()


def _write_bash_alias_stripped(path: Path) -> None:
    """Write the bash alias file without trailing ``complete`` lines."""
    path.write_text(
        "\n".join(
            line
            for line in generate_bash_aliases().splitlines()
            if not line.startswith("complete -F")
        )
    )


def _write_zsh_alias_stripped(path: Path) -> None:
    """Write the zsh alias file without trailing ``compdef`` lines."""
    path.write_text(
        "\n".join(
            line
            for line in generate_zsh_aliases().splitlines()
            if not line.startswith("compdef ")
        )
    )


def _seed_worktree(src_clone: Path, branch: str) -> Path:
    """Create a worktree for ``branch`` against ``src_clone``.

    Creates ``branch`` first (the test source repo only has ``master``/``main``),
    then ``git worktree add`` to mirror the user's flow. Returns the worktree's
    absolute path so tests can dirty it or assert its removal.
    """
    from ruamel.yaml import YAML

    from gww.utils.xdg import get_config_path

    saved_home = os.environ.get("HOME")
    os.environ.pop("XDG_CONFIG_HOME", None)
    try:
        yaml = YAML(typ="safe", pure=True)
        with open(get_config_path()) as f:
            config = yaml.load(f)
    finally:
        if saved_home is not None:
            os.environ["HOME"] = saved_home

    wt_template = config["default_worktrees"]
    # Mirror gww's template evaluation: norm_branch() turns
    # "feature/foo" into "feature-foo". Good enough for the test branches
    # we use, which never contain a slash.
    norm = branch.replace("/", "-")
    wt_path = Path(wt_template.replace("norm_branch()", norm))

    subprocess.run(
        ["git", "branch", branch, "main"],
        cwd=src_clone,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "worktree", "add", str(wt_path), branch],
        cwd=src_clone,
        check=True,
        capture_output=True,
    )
    return wt_path


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


class TestBashGwcAlias:
    """Behavioural tests for the generated ``gwc`` function (bash)."""

    def test_yes_answer_cds_into_cloned_repo(
        self, tmp_path: Path
    ) -> None:
        """Answering ``y`` to the prompt must ``cd`` into the freshly cloned repo."""
        assert SH_BASH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"

        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwc.bash"
        _write_bash_alias_stripped(alias_file)

        result = _run_shell(
            SH_BASH,
            _bash_script_clone("y"),
            cwd=tmp_path,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_URI": f"file://{src}",
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        pwd_after = _parse_pwd_marker(result.stdout, "PWD_AFTER=")
        assert pwd_after.endswith("/src"), (
            f"expected cd into cloned repo ending in /src, got {pwd_after!r}"
        )
        assert (Path(pwd_after) / ".git").exists()

    def test_no_answer_stays_put(self, tmp_path: Path) -> None:
        """Answering ``n`` to the prompt must not change the current directory."""
        assert SH_BASH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"

        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwc.bash"
        _write_bash_alias_stripped(alias_file)

        result = _run_shell(
            SH_BASH,
            _bash_script_clone("n"),
            cwd=tmp_path,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_URI": f"file://{src}",
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        pwd_after = _parse_pwd_marker(result.stdout, "PWD_AFTER=")
        assert pwd_after == str(tmp_path), (
            f"expected to stay at {tmp_path}, got {pwd_after!r}"
        )

    def test_prompt_text_is_emitted_on_stdout(
        self, tmp_path: Path
    ) -> None:
        """The ``Navigate to <path>? [Y/n]`` prompt must be visible on stdout."""
        assert SH_BASH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"

        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwc.bash"
        _write_bash_alias_stripped(alias_file)

        result = _run_shell(
            SH_BASH,
            _bash_script_clone("n"),
            cwd=tmp_path,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_URI": f"file://{src}",
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

    def test_streams_clone_progress_to_stderr(
        self, tmp_path: Path
    ) -> None:
        """``gwc`` must let git's ``Cloning into …`` line through to the user.

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
        alias_file = tmp_path / "gwc.bash"
        _write_bash_alias_stripped(alias_file)

        result = _run_shell(
            SH_BASH,
            _bash_script_clone("n"),
            cwd=tmp_path,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_URI": f"file://{src}",
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        assert "Cloning into" in result.stderr, (
            f"expected clone progress in stderr, got {result.stderr!r}"
        )

    def test_subshell_capture_discards_cd(
        self, tmp_path: Path
    ) -> None:
        """Capturing ``gwc`` in ``$(...)`` runs it in a subshell.

        The ``cd`` inside the subshell does **not** propagate to the parent,
        so PWD is unchanged. Same bash semantics as ``gwa``.
        """
        assert SH_BASH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"

        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwc.bash"
        _write_bash_alias_stripped(alias_file)

        script = dedent(
            f"""
            source "$ALIAS_FILE"
            OUT=$(printf 'y\\n' | gwc "$SRC_URI")
            echo "PWD_AFTER=$PWD"
            """
        ).strip()

        result = _run_shell(
            SH_BASH,
            script,
            cwd=tmp_path,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_URI": f"file://{src}",
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        pwd_after = _parse_pwd_marker(result.stdout, "PWD_AFTER=")
        assert pwd_after == str(tmp_path), (
            "subshell cd should NOT propagate to parent shell (bash semantics)"
        )


@pytest.mark.skipif(SH_ZSH is None, reason="zsh shell not installed")
class TestZshGwcAlias:
    """Behavioural tests for the generated ``gwc`` function (zsh)."""

    def test_yes_answer_cds_into_cloned_repo(
        self, tmp_path: Path
    ) -> None:
        """Answering ``y`` to the prompt must ``cd`` into the freshly cloned repo."""
        assert SH_ZSH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"

        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwc.zsh"
        _write_zsh_alias_stripped(alias_file)

        result = _run_shell(
            SH_ZSH,
            _zsh_script_clone("y"),
            cwd=tmp_path,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_URI": f"file://{src}",
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        pwd_after = _parse_pwd_marker(result.stdout, "PWD_AFTER=")
        assert pwd_after.endswith("/src"), (
            f"expected cd into cloned repo ending in /src, got {pwd_after!r}"
        )
        assert (Path(pwd_after) / ".git").exists()

    def test_no_answer_stays_put(self, tmp_path: Path) -> None:
        """Answering ``n`` to the prompt must not change the current directory."""
        assert SH_ZSH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"

        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwc.zsh"
        _write_zsh_alias_stripped(alias_file)

        result = _run_shell(
            SH_ZSH,
            _zsh_script_clone("n"),
            cwd=tmp_path,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_URI": f"file://{src}",
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        pwd_after = _parse_pwd_marker(result.stdout, "PWD_AFTER=")
        assert pwd_after == str(tmp_path), (
            f"expected to stay at {tmp_path}, got {pwd_after!r}"
        )

    def test_prompt_text_is_emitted_on_stdout(
        self, tmp_path: Path
    ) -> None:
        """The ``Navigate to <path>? [Y/n]`` prompt must be visible on stdout."""
        assert SH_ZSH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"

        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwc.zsh"
        _write_zsh_alias_stripped(alias_file)

        result = _run_shell(
            SH_ZSH,
            _zsh_script_clone("n"),
            cwd=tmp_path,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_URI": f"file://{src}",
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

    def test_streams_clone_progress_to_stderr(
        self, tmp_path: Path
    ) -> None:
        """``gwc`` must let git's ``Cloning into …`` line through to the user."""
        assert SH_ZSH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"

        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwc.zsh"
        _write_zsh_alias_stripped(alias_file)

        result = _run_shell(
            SH_ZSH,
            _zsh_script_clone("n"),
            cwd=tmp_path,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_URI": f"file://{src}",
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        assert "Cloning into" in result.stderr, (
            f"expected clone progress in stderr, got {result.stderr!r}"
        )

    def test_subshell_capture_discards_cd(
        self, tmp_path: Path
    ) -> None:
        """Capturing ``gwc`` in ``$(...)`` runs it in a subshell.

        The ``cd`` inside the subshell does **not** propagate to the parent,
        so PWD is unchanged. zsh shares this bash semantics.
        """
        assert SH_ZSH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"

        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwc.zsh"
        _write_zsh_alias_stripped(alias_file)

        script = dedent(
            f"""
            source "$ALIAS_FILE"
            OUT=$(printf 'y\\n' | gwc "$SRC_URI")
            echo "PWD_AFTER=$PWD"
            """
        ).strip()

        result = _run_shell(
            SH_ZSH,
            script,
            cwd=tmp_path,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_URI": f"file://{src}",
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        pwd_after = _parse_pwd_marker(result.stdout, "PWD_AFTER=")
        assert pwd_after == str(tmp_path), (
            "subshell cd should NOT propagate to parent shell (zsh semantics)"
        )


@pytest.mark.skipif(SH_FISH is None, reason="fish shell not installed")
class TestFishGwcAlias:
    """Behavioural tests for the generated ``gwc`` function (fish)."""

    def test_yes_answer_cds_into_cloned_repo(
        self, tmp_path: Path
    ) -> None:
        """Answering ``y`` to the prompt must ``cd`` into the freshly cloned repo.

        Fish propagates ``cd`` from subshells to the parent, so the test runs
        ``gwc`` on the right side of a pipe and still expects PWD to change.
        """
        assert SH_FISH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"

        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwc.fish"
        alias_file.write_text(generate_fish_aliases()["gwc"])

        result = _run_shell(
            SH_FISH,
            _fish_script_clone("y"),
            cwd=tmp_path,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_URI": f"file://{src}",
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        pwd_after = _parse_pwd_marker(result.stdout, "PWD_AFTER=")
        assert pwd_after.endswith("/src"), (
            f"expected cd into cloned repo ending in /src, got {pwd_after!r}"
        )
        assert (Path(pwd_after) / ".git").exists()

    def test_no_answer_stays_put(self, tmp_path: Path) -> None:
        """Answering ``n`` to the prompt must not change the current directory."""
        assert SH_FISH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"

        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwc.fish"
        alias_file.write_text(generate_fish_aliases()["gwc"])

        result = _run_shell(
            SH_FISH,
            _fish_script_clone("n"),
            cwd=tmp_path,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_URI": f"file://{src}",
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        pwd_after = _parse_pwd_marker(result.stdout, "PWD_AFTER=")
        assert pwd_after == str(tmp_path), (
            f"expected to stay at {tmp_path}, got {pwd_after!r}"
        )

    def test_streams_clone_progress_to_stderr(
        self, tmp_path: Path
    ) -> None:
        """``gwc`` must let git's ``Cloning into …`` line through to the user."""
        assert SH_FISH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"

        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwc.fish"
        alias_file.write_text(generate_fish_aliases()["gwc"])

        result = _run_shell(
            SH_FISH,
            _fish_script_clone("n"),
            cwd=tmp_path,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_URI": f"file://{src}",
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        assert "Cloning into" in result.stderr, (
            f"expected clone progress in stderr, got {result.stderr!r}"
        )

    def test_subshell_capture_propagates_cd(
        self, tmp_path: Path
    ) -> None:
        """In fish, ``set OUT (gwc ...)`` runs in a subshell but ``cd`` propagates."""
        assert SH_FISH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"

        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwc.fish"
        alias_file.write_text(generate_fish_aliases()["gwc"])

        script = dedent(
            f"""
            source $ALIAS_FILE
            set OUT (printf 'y\\n' | gwc $SRC_URI)
            echo "PWD_AFTER=$PWD"
            """
        ).strip()

        result = _run_shell(
            SH_FISH,
            script,
            cwd=tmp_path,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_URI": f"file://{src}",
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        pwd_after = _parse_pwd_marker(result.stdout, "PWD_AFTER=")
        assert pwd_after.endswith("/src"), (
            "fish subshell should propagate cd to parent (fish semantics)"
        )


class TestBashGwrAlias:
    """Behavioural tests for the generated ``gwr`` function (bash)."""

    def test_clean_worktree_is_removed(self, tmp_path: Path) -> None:
        """``gwr`` on a clean worktree must remove it without prompting."""
        assert SH_BASH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"
        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwr.bash"
        _write_bash_alias_stripped(alias_file)

        # Seed a worktree so gwr has something to remove
        os.environ["HOME"] = str(fake_home)
        os.environ.pop("XDG_CONFIG_HOME", None)
        wt_path = _seed_worktree(src, "gwr-clean")

        script = dedent(
            f"""
            source "$ALIAS_FILE"
            cd "$SRC_DIR"
            gwr gwr-clean
            if [ -d "{wt_path}" ]; then
                echo "STILL_THERE"
            else
                echo "REMOVED"
            fi
            """
        ).strip()

        result = _run_shell(
            SH_BASH,
            script,
            cwd=tmp_path,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_DIR": str(src),
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        assert "REMOVED" in result.stdout, (
            f"expected worktree removal, got stdout={result.stdout!r}"
        )
        assert "STILL_THERE" not in result.stdout

    def test_dirty_worktree_prompts_for_force(
        self, tmp_path: Path
    ) -> None:
        """``gwr`` on a dirty worktree must surface gww's error and refuse on 'n'.

        We can't reliably assert on the ``Force removal? [y/N]`` prompt text
        because ``fish``'s ``read -P`` only shows it when stdin is a TTY — in
        the test framework stdin is a pipe, so the prompt isn't captured.
        Instead we pin down the two observable effects: ``gwr`` must exit
        non-zero on refusal, and the worktree must still exist on disk.
        """
        assert SH_BASH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"
        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwr.bash"
        _write_bash_alias_stripped(alias_file)

        os.environ["HOME"] = str(fake_home)
        os.environ.pop("XDG_CONFIG_HOME", None)
        wt_path = _seed_worktree(src, "gwr-dirty")
        # Make the worktree dirty (untracked file is enough)
        (wt_path / "untracked.txt").write_text("junk")

        script = dedent(
            f"""
            source "$ALIAS_FILE"
            cd "$SRC_DIR"
            gwr gwr-dirty < <(printf 'n\\n')
            gwr_rc=$?
            echo "GWR_RC=$gwr_rc"
            """
        ).strip()

        result = _run_shell(
            SH_BASH,
            script,
            cwd=tmp_path,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_DIR": str(src),
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"script error: stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        assert "GWR_RC=1" in result.stdout, (
            f"gwr should refuse on 'n' (rc=1), got stdout={result.stdout!r}"
        )
        assert "uncommitted changes" in result.stderr, (
            f"expected dirty-state error in stderr, got {result.stderr!r}"
        )
        # Worktree still exists because we declined force
        assert wt_path.exists(), (
            "dirty worktree should still exist after declining force"
        )

    def test_streams_remove_message_to_stdout(
        self, tmp_path: Path
    ) -> None:
        """``gwr`` must let gww's ``Removed worktree: …`` line reach stdout."""
        assert SH_BASH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"
        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwr.bash"
        _write_bash_alias_stripped(alias_file)

        os.environ["HOME"] = str(fake_home)
        os.environ.pop("XDG_CONFIG_HOME", None)
        _seed_worktree(src, "gwr-msg")

        script = dedent(
            f"""
            source "$ALIAS_FILE"
            cd "$SRC_DIR"
            gwr gwr-msg
            """
        ).strip()

        result = _run_shell(
            SH_BASH,
            script,
            cwd=tmp_path,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_DIR": str(src),
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        assert "Removed worktree" in result.stdout, (
            f"expected 'Removed worktree:' message in stdout, "
            f"got stdout={result.stdout!r}"
        )


@pytest.mark.skipif(SH_ZSH is None, reason="zsh shell not installed")
class TestZshGwrAlias:
    """Behavioural tests for the generated ``gwr`` function (zsh)."""

    def test_clean_worktree_is_removed(self, tmp_path: Path) -> None:
        """``gwr`` on a clean worktree must remove it without prompting."""
        assert SH_ZSH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"
        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwr.zsh"
        _write_zsh_alias_stripped(alias_file)

        os.environ["HOME"] = str(fake_home)
        os.environ.pop("XDG_CONFIG_HOME", None)
        wt_path = _seed_worktree(src, "zsh-gwr-clean")

        script = dedent(
            f"""
            source "$ALIAS_FILE"
            cd "$SRC_DIR"
            gwr zsh-gwr-clean
            if [ -d "{wt_path}" ]; then
                echo "STILL_THERE"
            else
                echo "REMOVED"
            fi
            """
        ).strip()

        result = _run_shell(
            SH_ZSH,
            script,
            cwd=tmp_path,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_DIR": str(src),
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        assert "REMOVED" in result.stdout, (
            f"expected worktree removal, got stdout={result.stdout!r}"
        )
        assert "STILL_THERE" not in result.stdout

    def test_dirty_worktree_prompts_for_force(
        self, tmp_path: Path
    ) -> None:
        """``gwr`` on a dirty worktree must surface gww's error and refuse on 'n'.

        See :meth:`TestBashGwrAlias.test_dirty_worktree_prompts_for_force` for
        why we don't assert on the literal ``Force removal? [y/N]`` text.
        """
        assert SH_ZSH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"
        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwr.zsh"
        _write_zsh_alias_stripped(alias_file)

        os.environ["HOME"] = str(fake_home)
        os.environ.pop("XDG_CONFIG_HOME", None)
        wt_path = _seed_worktree(src, "zsh-gwr-dirty")
        (wt_path / "untracked.txt").write_text("junk")

        script = dedent(
            f"""
            source "$ALIAS_FILE"
            cd "$SRC_DIR"
            gwr zsh-gwr-dirty < <(printf 'n\\n')
            gwr_rc=$?
            echo "GWR_RC=$gwr_rc"
            """
        ).strip()

        result = _run_shell(
            SH_ZSH,
            script,
            cwd=tmp_path,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_DIR": str(src),
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"script error: stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        assert "GWR_RC=1" in result.stdout, (
            f"gwr should refuse on 'n' (rc=1), got stdout={result.stdout!r}"
        )
        assert "uncommitted changes" in result.stderr, (
            f"expected dirty-state error in stderr, got {result.stderr!r}"
        )
        assert wt_path.exists(), (
            "dirty worktree should still exist after declining force"
        )

    def test_streams_remove_message_to_stdout(
        self, tmp_path: Path
    ) -> None:
        """``gwr`` must let gww's ``Removed worktree: …`` line reach stdout."""
        assert SH_ZSH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"
        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwr.zsh"
        _write_zsh_alias_stripped(alias_file)

        os.environ["HOME"] = str(fake_home)
        os.environ.pop("XDG_CONFIG_HOME", None)
        _seed_worktree(src, "zsh-gwr-msg")

        script = dedent(
            f"""
            source "$ALIAS_FILE"
            cd "$SRC_DIR"
            gwr zsh-gwr-msg
            """
        ).strip()

        result = _run_shell(
            SH_ZSH,
            script,
            cwd=tmp_path,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_DIR": str(src),
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        assert "Removed worktree" in result.stdout, (
            f"expected 'Removed worktree:' message in stdout, "
            f"got stdout={result.stdout!r}"
        )


@pytest.mark.skipif(SH_FISH is None, reason="fish shell not installed")
class TestFishGwrAlias:
    """Behavioural tests for the generated ``gwr`` function (fish)."""

    def test_clean_worktree_is_removed(self, tmp_path: Path) -> None:
        """``gwr`` on a clean worktree must remove it without prompting."""
        assert SH_FISH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"
        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwr.fish"
        alias_file.write_text(generate_fish_aliases()["gwr"])

        os.environ["HOME"] = str(fake_home)
        os.environ.pop("XDG_CONFIG_HOME", None)
        wt_path = _seed_worktree(src, "fish-gwr-clean")

        script = dedent(
            f"""
            source $ALIAS_FILE
            cd $SRC_DIR
            gwr fish-gwr-clean
            if test -d "{wt_path}"
                echo "STILL_THERE"
            else
                echo "REMOVED"
            end
            """
        ).strip()

        result = _run_shell(
            SH_FISH,
            script,
            cwd=tmp_path,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_DIR": str(src),
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        assert "REMOVED" in result.stdout, (
            f"expected worktree removal, got stdout={result.stdout!r}"
        )
        assert "STILL_THERE" not in result.stdout

    def test_dirty_worktree_prompts_for_force(
        self, tmp_path: Path
    ) -> None:
        """``gwr`` on a dirty worktree must surface gww's error and refuse on 'n'.

        See :meth:`TestBashGwrAlias.test_dirty_worktree_prompts_for_force` for
        why we don't assert on the literal ``Force removal? [y/N]`` text.
        """
        assert SH_FISH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"
        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwr.fish"
        alias_file.write_text(generate_fish_aliases()["gwr"])

        os.environ["HOME"] = str(fake_home)
        os.environ.pop("XDG_CONFIG_HOME", None)
        wt_path = _seed_worktree(src, "fish-gwr-dirty")
        (wt_path / "untracked.txt").write_text("junk")

        # In fish the right side of a pipe runs in a subshell, so we capture
        # the gwr exit code into a local and surface it after the pipe.
        script = dedent(
            f"""
            source $ALIAS_FILE
            cd $SRC_DIR
            set gwr_rc 0
            printf 'n\\n' | gwr fish-gwr-dirty
            set gwr_rc $status
            echo "GWR_RC=$gwr_rc"
            """
        ).strip()

        result = _run_shell(
            SH_FISH,
            script,
            cwd=tmp_path,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_DIR": str(src),
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"script error: stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        assert "GWR_RC=1" in result.stdout, (
            f"gwr should refuse on 'n' (rc=1), got stdout={result.stdout!r}"
        )
        assert "uncommitted changes" in result.stderr, (
            f"expected dirty-state error in stderr, got {result.stderr!r}"
        )
        assert wt_path.exists(), (
            "dirty worktree should still exist after declining force"
        )

    def test_streams_remove_message_to_stdout(
        self, tmp_path: Path
    ) -> None:
        """``gwr`` must let gww's ``Removed worktree: …`` line reach stdout."""
        assert SH_FISH is not None
        src = _make_source_repo(tmp_path)
        wt = tmp_path / "worktrees"
        fake_home = _isolated_xdg_config(tmp_path, wt)
        alias_file = tmp_path / "gwr.fish"
        alias_file.write_text(generate_fish_aliases()["gwr"])

        os.environ["HOME"] = str(fake_home)
        os.environ.pop("XDG_CONFIG_HOME", None)
        _seed_worktree(src, "fish-gwr-msg")

        script = dedent(
            f"""
            source $ALIAS_FILE
            cd $SRC_DIR
            gwr fish-gwr-msg
            """
        ).strip()

        result = _run_shell(
            SH_FISH,
            script,
            cwd=tmp_path,
            env_extra={
                "ALIAS_FILE": str(alias_file),
                "SRC_DIR": str(src),
                "HOME": str(fake_home),
            },
        )

        assert result.returncode == 0, (
            f"stderr={result.stderr!r} stdout={result.stdout!r}"
        )
        assert "Removed worktree" in result.stdout, (
            f"expected 'Removed worktree:' message in stdout, "
            f"got stdout={result.stdout!r}"
        )
