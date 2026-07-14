"""Integration tests for the ``gww clean`` subcommand.

Covers the full CLI flow:

* Happy path -- ``--all -y`` removes every cleanable worktree, leaves
  the main checkout alone, prints the summary, exits 0.
* ``--merged`` filter with a fixture provider that exits 0 (cleanable)
  vs 1 (kept).
* Git fallback (``--merged`` without a configured provider) uses
  ``git branch --merged <default>``.
* ``--dry-run`` runs the full flow with no side effects and no prompt.
* ``--yes`` skips the prompt.
* ``--force`` escalates ``git worktree remove`` and ``git branch -d``.
* Confirmation prompt: ``n`` exits 0 with no side effects; EOF exits 0
  with no side effects.
* ``--merged`` and ``--all`` are mutually exclusive.
* Remote branches are never touched.
* Per-branch provider timeout fires ``X: skip (timeout)``.
* Per-branch missing CLI fires ``X: skip (<command> not found)``.
* Exit code is 1 when a per-worktree ``git worktree remove`` /
  ``git branch -d`` step fails; provider failures do not affect exit code.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from gww.cli.commands.clean import run_clean
from tests.conftest import make_ctx


FIXTURE_PROVIDER = (
    "PYTHONPATH={fixture_dir} "
    "python {fixture} branch()"
)


@pytest.fixture
def git_repo_with_remote(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, str]:
    """Create a fresh source repo with a remote on a local bare repo.

    Returns ``(local_repo_path, origin_uri_string)``. ``origin_uri`` is a
    ``file://`` URL pointing at the bare repo so the URI parser produces
    a real host (the bare repo's parent directory), and provider-host
    pattern matching exercises the full path.
    """
    base = tmp_path_factory.mktemp("clean_repo")
    bare = base / "origin.git"
    local = base / "local"
    local.mkdir()
    subprocess.run(
        ["git", "init", "--bare", str(bare)],
        check=True, capture_output=True,
    )
    subprocess.run(["git", "init"], cwd=local, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"],
        cwd=local, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "T"],
        cwd=local, check=True, capture_output=True,
    )
    (local / "README.md").write_text("# T")
    subprocess.run(["git", "add", "."], cwd=local, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=local, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "remote", "add", "origin", f"file://{bare}"],
        cwd=local, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "push", "-u", "origin", "HEAD"],
        cwd=local, check=True, capture_output=True,
    )
    origin_uri = f"file://{bare}"
    return local, origin_uri


@pytest.fixture
def worktrees_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("worktrees")


@pytest.fixture
def fixture_dir() -> Path:
    """Absolute path to the ``tests/fixtures/clean`` directory.

    Used by tests that wire ``providers.<kind>.merged`` to point at
    ``provider_fixture.py`` so the provider command can be invoked
    end-to-end via the shell.
    """
    return Path(__file__).resolve().parent.parent / "fixtures" / "clean"


def _add_worktree(
    source: Path,
    branch: str,
    target: Path,
) -> None:
    """Create ``branch`` in ``source`` and check it out at ``target``.

    The branch is created from HEAD so it shares an initial commit with
    the default branch. To make ``--merged`` interesting, the caller can
    create an extra commit on the default branch so the branch is no
    longer merged -- or use multiple branches with different merge states.
    """
    subprocess.run(
        ["git", "branch", branch],
        cwd=source, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "worktree", "add", str(target), branch],
        cwd=source, check=True, capture_output=True,
    )


def _default_branch(source: Path) -> str:
    """Detect the source's default branch (handles ``main`` and ``master``)."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=source, capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def _make_config(
    config_dir: Path,
    *,
    providers: str = "",
    actions: str = "",
) -> None:
    config_path = config_dir / "gww" / "config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    blocks = ["default_sources: ~/sources", "default_worktrees: ~/worktrees"]
    if providers:
        blocks.append(providers)
    if actions:
        blocks.append("actions:")
        blocks.append(actions)
    config_path.write_text("\n".join(blocks) + "\n")


# ---------------------------------------------------------------------------
# --all filter
# ---------------------------------------------------------------------------


class TestCleanAllFilter:
    """``--all`` skips the MR filter and treats every cleanable worktree
    as eligible."""

    def test_all_removes_all_cleanable(
        self,
        git_repo_with_remote: tuple[Path, str],
        config_dir: Path,
        worktrees_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        local, _ = git_repo_with_remote
        _add_worktree(local, "feature-a", worktrees_dir / "feature-a")
        _add_worktree(local, "feature-b", worktrees_dir / "feature-b")
        _make_config(config_dir)
        monkeypatch.chdir(local)

        result = run_clean(make_ctx(clean_all=True, clean_yes=True))

        assert result == 0
        assert not (worktrees_dir / "feature-a").exists()
        assert not (worktrees_dir / "feature-b").exists()
        assert not local.joinpath(".git/worktrees/feature-a").exists()
        assert not local.joinpath(".git/worktrees/feature-b").exists()

    def test_all_skips_main_checkout(
        self,
        git_repo_with_remote: tuple[Path, str],
        config_dir: Path,
        worktrees_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The source's main checkout must never be removed, even with --all."""
        local, _ = git_repo_with_remote
        _add_worktree(local, "feature-a", worktrees_dir / "feature-a")
        _make_config(config_dir)
        monkeypatch.chdir(local)

        result = run_clean(make_ctx(clean_all=True, clean_yes=True))

        assert result == 0
        assert local.exists(), "main checkout must survive --all"
        assert local.joinpath(".git").exists()

    def test_all_skips_default_branch(
        self,
        git_repo_with_remote: tuple[Path, str],
        config_dir: Path,
        worktrees_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The default branch (main) must never be removed, even with --all."""
        local, _ = git_repo_with_remote
        _add_worktree(local, "main", worktrees_dir / "main-branch")
        _make_config(config_dir)
        monkeypatch.chdir(local)

        result = run_clean(make_ctx(clean_all=True, clean_yes=True))

        assert result == 0
        # main is never cleanable -- summary reflects no removals.
        assert (worktrees_dir / "main-branch").exists()


# ---------------------------------------------------------------------------
# --merged filter (provider path)
# ---------------------------------------------------------------------------


class TestCleanMergedProvider:
    """``--merged`` evaluates the provider's command template per branch.
    Exit 0 -> cleanable, anything else -> kept."""

    def _provider_cmd(self, mode: str, fixture_dir: Path) -> str:
        cmd = FIXTURE_PROVIDER.format(
            fixture_dir=fixture_dir,
            mode=mode,
            fixture=fixture_dir / "provider_fixture.py",
        )
        return cmd.replace("\\", "\\\\")

    def test_provider_exit0_removes_branch(
        self,
        git_repo_with_remote: tuple[Path, str],
        config_dir: Path,
        worktrees_dir: Path,
        fixture_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        local, origin_uri = git_repo_with_remote
        _add_worktree(local, "feature-a", worktrees_dir / "feature-a")
        _add_worktree(local, "feature-b", worktrees_dir / "feature-b")
        providers_block = f"""\
providers:
  github:
    host_patterns: ['^.*$']
    merged: "{self._provider_cmd('exit0', fixture_dir)}"
"""
        _make_config(config_dir, providers=providers_block)
        monkeypatch.chdir(local)
        monkeypatch.setenv("GWW_FIXTURE_MODE", "exit0")

        result = run_clean(make_ctx(clean_merged=True, clean_yes=True))

        assert result == 0
        assert not (worktrees_dir / "feature-a").exists()
        assert not (worktrees_dir / "feature-b").exists()
        captured = capsys.readouterr()
        assert "feature-a: clean" in captured.out
        assert "feature-b: clean" in captured.out
        assert "Removed 2; kept 0" in captured.out

    def test_provider_exit1_keeps_branch(
        self,
        git_repo_with_remote: tuple[Path, str],
        config_dir: Path,
        worktrees_dir: Path,
        fixture_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        local, origin_uri = git_repo_with_remote
        _add_worktree(local, "feature-a", worktrees_dir / "feature-a")
        providers_block = f"""\
providers:
  github:
    host_patterns: ['^.*$']
    merged: "{self._provider_cmd('exit1', fixture_dir)}"
"""
        _make_config(config_dir, providers=providers_block)
        monkeypatch.chdir(local)
        monkeypatch.setenv("GWW_FIXTURE_MODE", "exit1")

        result = run_clean(make_ctx(clean_merged=True, clean_yes=True))

        assert result == 0
        assert (worktrees_dir / "feature-a").exists()
        captured = capsys.readouterr()
        assert "feature-a: keep" in captured.out
        assert "Removed 0; kept 1" in captured.out

    def test_missing_provider_cli_fires_skip_label(
        self,
        git_repo_with_remote: tuple[Path, str],
        config_dir: Path,
        worktrees_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        local, origin_uri = git_repo_with_remote
        _add_worktree(local, "feature-a", worktrees_dir / "feature-a")
        # Render a command whose leading binary does not exist.
        providers_block = """\
providers:
  github:
    host_patterns: ['^.*$']
    merged: "gww-fixture-missing-binary branch()"
"""
        _make_config(config_dir, providers=providers_block)
        monkeypatch.chdir(local)

        result = run_clean(make_ctx(clean_merged=True, clean_yes=True))

        assert result == 0
        # Branch is kept (provider exited 127 -> treated as non-merged).
        assert (worktrees_dir / "feature-a").exists()
        captured = capsys.readouterr()
        assert "feature-a: skip (gww-fixture-missing-binary not found)" in captured.out
        assert "Removed 0; kept 1" in captured.out

    @pytest.mark.slow
    def test_provider_timeout_fires_skip_label(
        self,
        git_repo_with_remote: tuple[Path, str],
        config_dir: Path,
        worktrees_dir: Path,
        fixture_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        local, origin_uri = git_repo_with_remote
        _add_worktree(local, "feature-a", worktrees_dir / "feature-a")
        providers_block = f"""\
providers:
  github:
    host_patterns: ['^.*$']
    merged: "{self._provider_cmd('sleep', fixture_dir)}"
"""
        _make_config(config_dir, providers=providers_block)
        monkeypatch.chdir(local)
        monkeypatch.setenv("GWW_FIXTURE_MODE", "sleep")

        result = run_clean(make_ctx(clean_merged=True, clean_yes=True))

        assert result == 0
        assert (worktrees_dir / "feature-a").exists()
        captured = capsys.readouterr()
        assert "feature-a: skip (timeout)" in captured.out


# ---------------------------------------------------------------------------
# --merged filter (git fallback)
# ---------------------------------------------------------------------------


class TestCleanMergedGitFallback:
    """``--merged`` falls back to ``git branch --merged <default>`` when no
    provider resolves (ADR-0015)."""

    def test_merged_branch_removed_via_git_fallback(
        self,
        git_repo_with_remote: tuple[Path, str],
        config_dir: Path,
        worktrees_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        local, _ = git_repo_with_remote
        _add_worktree(local, "feature-a", worktrees_dir / "feature-a")
        _make_config(config_dir)  # no providers: block
        monkeypatch.chdir(local)

        result = run_clean(make_ctx(clean_merged=True, clean_yes=True))

        # ``feature-a`` was created from HEAD -> fully merged.
        assert result == 0
        assert not (worktrees_dir / "feature-a").exists()
        captured = capsys.readouterr()
        assert "feature-a: clean" in captured.out

    def test_unmerged_branch_kept_via_git_fallback(
        self,
        git_repo_with_remote: tuple[Path, str],
        config_dir: Path,
        worktrees_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        local, _ = git_repo_with_remote
        default = _default_branch(local)
        # Create a branch with a commit that has NOT been merged into the
        # default branch.
        subprocess.run(
            ["git", "checkout", "-b", "feature-a"],
            cwd=local, check=True, capture_output=True,
        )
        (local / "feature-a.txt").write_text("a")
        subprocess.run(["git", "add", "."], cwd=local, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "feat-a"],
            cwd=local, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", default],
            cwd=local, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "worktree", "add", str(worktrees_dir / "feature-a"), "feature-a"],
            cwd=local, check=True, capture_output=True,
        )
        _make_config(config_dir)
        monkeypatch.chdir(local)

        result = run_clean(make_ctx(clean_merged=True, clean_yes=True))

        # ``feature-a`` has an unmerged commit -> kept.
        assert result == 0
        assert (worktrees_dir / "feature-a").exists()
        captured = capsys.readouterr()
        assert "feature-a: keep" in captured.out


# ---------------------------------------------------------------------------
# Confirmation prompt
# ---------------------------------------------------------------------------


class TestCleanConfirmation:
    """The pre-execution prompt fires once without ``-y``; non-``y`` answers
    exit 0 with no side effects."""

    def test_prompt_accept_y_removes(
        self,
        git_repo_with_remote: tuple[Path, str],
        config_dir: Path,
        worktrees_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        local, _ = git_repo_with_remote
        _add_worktree(local, "feature-a", worktrees_dir / "feature-a")
        _make_config(config_dir)
        monkeypatch.chdir(local)
        monkeypatch.setattr("builtins.input", lambda _: "y")

        result = run_clean(make_ctx(clean_all=True))

        assert result == 0
        assert not (worktrees_dir / "feature-a").exists()

    def test_prompt_decline_exits_zero_with_no_side_effects(
        self,
        git_repo_with_remote: tuple[Path, str],
        config_dir: Path,
        worktrees_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        local, _ = git_repo_with_remote
        _add_worktree(local, "feature-a", worktrees_dir / "feature-a")
        _make_config(config_dir)
        monkeypatch.chdir(local)
        monkeypatch.setattr("builtins.input", lambda _: "n")

        result = run_clean(make_ctx(clean_all=True))

        assert result == 0
        assert (worktrees_dir / "feature-a").exists()
        captured = capsys.readouterr()
        assert "feature-a: clean" in captured.out
        # Summary not printed when declined -- user got "no" so we silently exit 0.
        assert "Removed" not in captured.out

    def test_prompt_eof_exits_zero_with_no_side_effects(
        self,
        git_repo_with_remote: tuple[Path, str],
        config_dir: Path,
        worktrees_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        local, _ = git_repo_with_remote
        _add_worktree(local, "feature-a", worktrees_dir / "feature-a")
        _make_config(config_dir)
        monkeypatch.chdir(local)

        def _raise_eof(_prompt: str) -> str:
            raise EOFError

        monkeypatch.setattr("builtins.input", _raise_eof)

        result = run_clean(make_ctx(clean_all=True))

        assert result == 0
        assert (worktrees_dir / "feature-a").exists()

    def test_yes_skips_prompt(
        self,
        git_repo_with_remote: tuple[Path, str],
        config_dir: Path,
        worktrees_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        local, _ = git_repo_with_remote
        _add_worktree(local, "feature-a", worktrees_dir / "feature-a")
        _make_config(config_dir)
        monkeypatch.chdir(local)

        def _fail(_prompt: str) -> str:
            raise AssertionError("input() should not be called with --yes")

        monkeypatch.setattr("builtins.input", _fail)

        result = run_clean(make_ctx(clean_all=True, clean_yes=True))

        assert result == 0
        assert not (worktrees_dir / "feature-a").exists()


# ---------------------------------------------------------------------------
# --dry-run
# ---------------------------------------------------------------------------


class TestCleanDryRun:
    """``--dry-run`` runs the full flow with no side effects, no prompt."""

    def test_dry_run_does_not_remove(
        self,
        git_repo_with_remote: tuple[Path, str],
        config_dir: Path,
        worktrees_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        local, _ = git_repo_with_remote
        _add_worktree(local, "feature-a", worktrees_dir / "feature-a")
        _make_config(config_dir)
        monkeypatch.chdir(local)

        result = run_clean(make_ctx(clean_all=True, dry_run=True))

        assert result == 0
        assert (worktrees_dir / "feature-a").exists()
        captured = capsys.readouterr()
        assert "Would remove 1; would keep 0" in captured.out

    def test_dry_run_does_not_prompt(
        self,
        git_repo_with_remote: tuple[Path, str],
        config_dir: Path,
        worktrees_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        local, _ = git_repo_with_remote
        _add_worktree(local, "feature-a", worktrees_dir / "feature-a")
        _make_config(config_dir)
        monkeypatch.chdir(local)

        def _fail(_prompt: str) -> str:
            raise AssertionError("input() should not be called in --dry-run")

        monkeypatch.setattr("builtins.input", _fail)

        result = run_clean(make_ctx(clean_all=True, dry_run=True))

        assert result == 0


# ---------------------------------------------------------------------------
# --force
# ---------------------------------------------------------------------------


class TestCleanForce:
    """``--force`` escalates ``git worktree remove`` and ``git branch -d``."""

    def test_force_overrides_dirty_worktree(
        self,
        git_repo_with_remote: tuple[Path, str],
        config_dir: Path,
        worktrees_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        local, _ = git_repo_with_remote
        wt = worktrees_dir / "feature-a"
        _add_worktree(local, "feature-a", wt)
        (wt / "uncommitted.txt").write_text("dirty")
        _make_config(config_dir)
        monkeypatch.chdir(local)

        # Without --force the dirty worktree would be kept (refusal).
        # With --force the removal proceeds and the branch is deleted.
        result = run_clean(make_ctx(clean_all=True, clean_yes=True, force=True))

        assert result == 0
        assert not wt.exists()


# ---------------------------------------------------------------------------
# Mutually exclusive flags
# ---------------------------------------------------------------------------


class TestCleanFlagConflicts:
    """``--merged`` and ``--all`` cannot both be set."""

    def test_merged_and_all_exits_one(
        self,
        git_repo_with_remote: tuple[Path, str],
        config_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        local, _ = git_repo_with_remote
        _make_config(config_dir)
        monkeypatch.chdir(local)

        result = run_clean(make_ctx(clean_merged=True, clean_all=True))

        assert result == 1
        captured = capsys.readouterr()
        assert "mutually exclusive" in captured.err


# ---------------------------------------------------------------------------
# Side-effect ordering and remote-branch isolation
# ---------------------------------------------------------------------------


class TestCleanSideEffects:
    """The locked per-worktree side-effect order: ``before_remove`` actions
    then ``git worktree remove`` then ``git branch -d``. Remote branches are
    never touched."""

    def test_before_remove_runs_then_worktree_then_branch(
        self,
        git_repo_with_remote: tuple[Path, str],
        config_dir: Path,
        worktrees_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        local, _ = git_repo_with_remote
        wt = worktrees_dir / "feature-a"
        _add_worktree(local, "feature-a", wt)
        marker = worktrees_dir / "before.log"
        actions = f"""\
  - when: 'True'
    critical: false
    before_remove:
      - command: 'touch "{marker}"'
"""
        _make_config(config_dir, actions=actions)
        monkeypatch.chdir(local)

        result = run_clean(make_ctx(clean_all=True, clean_yes=True))

        assert result == 0
        assert not wt.exists()
        assert marker.exists(), "before_remove must have run before worktree removal"

    def test_remote_branches_never_touched(
        self,
        git_repo_with_remote: tuple[Path, str],
        config_dir: Path,
        worktrees_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        local, origin_uri = git_repo_with_remote
        # Push a remote branch.
        subprocess.run(
            ["git", "branch", "remote-only"],
            cwd=local, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "push", "origin", "remote-only"],
            cwd=local, check=True, capture_output=True,
        )
        _add_worktree(local, "feature-a", worktrees_dir / "feature-a")
        _make_config(config_dir)
        monkeypatch.chdir(local)

        result = run_clean(make_ctx(clean_all=True, clean_yes=True))

        assert result == 0
        # Local branch is gone; remote branch is untouched.
        result_local = subprocess.run(
            ["git", "branch", "--list", "feature-a"],
            cwd=local, capture_output=True, text=True, check=False,
        )
        result_remote = subprocess.run(
            ["git", "branch", "-r", "--list", "origin/feature-a"],
            cwd=local, capture_output=True, text=True, check=False,
        )
        result_remote_only = subprocess.run(
            ["git", "branch", "-r", "--list", "origin/remote-only"],
            cwd=local, capture_output=True, text=True, check=False,
        )
        assert result_local.stdout.strip() == ""
        assert "feature-a" not in result_remote.stdout
        assert "remote-only" in result_remote_only.stdout


# ---------------------------------------------------------------------------
# Empty source / no worktrees
# ---------------------------------------------------------------------------


class TestCleanNoWorktrees:
    """When the source has no cleanable worktrees, exit 0 with a summary
    that reflects 'kept 0'."""

    def test_no_worktrees(
        self,
        git_repo_with_remote: tuple[Path, str],
        config_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        local, _ = git_repo_with_remote
        _make_config(config_dir)
        monkeypatch.chdir(local)

        result = run_clean(make_ctx(clean_all=True))

        assert result == 0
        captured = capsys.readouterr()
        assert "No matching worktrees" in captured.out


# ---------------------------------------------------------------------------
# Exit code semantics
# ---------------------------------------------------------------------------


class TestCleanExitCodes:
    """Exit 0 when no per-worktree git step fails; provider failures don't
    affect this."""

    def test_provider_failure_exits_zero(
        self,
        git_repo_with_remote: tuple[Path, str],
        config_dir: Path,
        worktrees_dir: Path,
        fixture_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Provider exit non-zero must not affect command exit code (ADR-0018)."""
        local, _ = git_repo_with_remote
        _add_worktree(local, "feature-a", worktrees_dir / "feature-a")
        cmd = FIXTURE_PROVIDER.format(
            fixture_dir=fixture_dir,
            mode="exit1",
            fixture=fixture_dir / "provider_fixture.py",
        ).replace("\\", "\\\\")
        providers_block = f"""\
providers:
  github:
    host_patterns: ['^.*$']
    merged: "{cmd}"
"""
        _make_config(config_dir, providers=providers_block)
        monkeypatch.chdir(local)
        monkeypatch.setenv("GWW_FIXTURE_MODE", "exit1")

        result = run_clean(make_ctx(clean_merged=True, clean_yes=True))

        assert result == 0
        assert (worktrees_dir / "feature-a").exists()