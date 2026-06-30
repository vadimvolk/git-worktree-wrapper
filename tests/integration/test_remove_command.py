"""Integration tests for the new ``before_remove`` action kind on
``gww remove`` (ADR-0011).

Covers the full CLI flow:

* Happy path — no actions: existing behaviour preserved.
* Happy path with ``before_remove`` — action runs, ``git worktree remove``
  follows, exit 0, path deleted.
* Critical failure — ``git worktree remove`` is *not* invoked, exit 1,
  path survives, failure summary printed.
* Non-critical failure — ``git worktree remove`` *is* invoked, exit 0,
  path deleted, failure summary printed.
* Path-based remove — ``branch()`` resolves to the worktree's branch.
* Detached HEAD path-based remove — ``branch()`` evaluates to ``""`` without
  raising predicates that reference it.
* Tag-driven predicate — ``--tag key=value`` flows through ``tag()``.
* Matcher error — exit 2, ``git worktree remove`` not invoked.
* ``dest_path()`` is the worktree being removed; ``source_path()`` is its
  source repo.
* ``--force`` does *not* bypass ``before_remove`` — a critical failure still
  blocks the remove even with ``--force``.
* Empty actions list — unchanged behaviour.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from gww.cli.commands.remove import run_remove
from tests.conftest import make_ctx


@pytest.fixture
def git_repo_with_remote(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    bare = tmp_path_factory.mktemp("bare")
    bare_repo = bare / "origin.git"
    subprocess.run(["git", "init", "--bare", str(bare_repo)], check=True, capture_output=True)

    local = tmp_path_factory.mktemp("local")
    subprocess.run(["git", "init"], cwd=local, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=local, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=local, check=True, capture_output=True,
    )
    (local / "README.md").write_text("# Test")
    subprocess.run(["git", "add", "."], cwd=local, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial"], cwd=local, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "remote", "add", "origin", f"file://{bare_repo}"],
        cwd=local, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "push", "-u", "origin", "HEAD"], cwd=local, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "branch", "feature-test"], cwd=local, check=True, capture_output=True,
    )
    return local, bare_repo


@pytest.fixture
def worktree_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("worktrees")


@pytest.fixture
def worktree_at(git_repo_with_remote: tuple[Path, Path], worktree_dir: Path) -> Path:
    """Create a worktree on ``feature-test`` and return its path."""
    local, _ = git_repo_with_remote
    wt = worktree_dir / "feature-test"
    subprocess.run(
        ["git", "worktree", "add", str(wt), "feature-test"],
        cwd=local, check=True, capture_output=True,
    )
    return wt


def _write_config(config_dir: Path, actions_block: str = "") -> None:
    config_path = config_dir / "gww" / "config.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if actions_block:
        config_path.write_text(f"""
default_sources: ~/sources
default_worktrees: ~/worktrees/norm_branch()

actions:
{actions_block}
""")
    else:
        config_path.write_text("""
default_sources: ~/sources
default_worktrees: ~/worktrees/norm_branch()
""")


# ---------------------------------------------------------------------------
# Existing behaviour preserved
# ---------------------------------------------------------------------------


class TestRemoveWithoutBeforeRemoveActions:
    """When no ``before_remove`` rules are configured, ``gww remove`` behaves
    exactly as before — no regressions."""

    def test_branch_based_remove_succeeds(
        self,
        git_repo_with_remote: tuple[Path, Path],
        config_dir: Path,
        worktree_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        local, _ = git_repo_with_remote
        wt = worktree_dir / "feature-test"
        subprocess.run(
            ["git", "worktree", "add", str(wt), "feature-test"],
            cwd=local, check=True, capture_output=True,
        )
        _write_config(config_dir)
        monkeypatch.chdir(local)

        result = run_remove(make_ctx(branch_or_path="feature-test"))

        assert result == 0
        assert not wt.exists()


# ---------------------------------------------------------------------------
# Happy path with before_remove
# ---------------------------------------------------------------------------


class TestRemoveWithBeforeRemove:
    """``before_remove`` runs in the worktree, then ``git worktree remove``
    is invoked. Exit 0, path deleted."""

    def test_before_remove_command_runs_then_remove(
        self,
        git_repo_with_remote: tuple[Path, Path],
        config_dir: Path,
        worktree_at: Path,
        worktree_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        local, _ = git_repo_with_remote
        marker = worktree_dir / "ran.log"
        _write_config(
            config_dir,
            f"""\
  - when: 'True'
    before_remove:
      - command: 'touch "{marker}"'
""",
        )
        monkeypatch.chdir(local)

        result = run_remove(make_ctx(branch_or_path="feature-test"))

        assert result == 0
        assert not worktree_at.exists()
        # The action ran before the remove; the sibling marker survives.
        assert marker.exists()

    def test_before_remove_can_create_sibling_marker(
        self,
        git_repo_with_remote: tuple[Path, Path],
        config_dir: Path,
        worktree_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A ``before_remove`` action that writes *outside* the worktree leaves
        evidence behind after ``git worktree remove`` finishes."""
        local, _ = git_repo_with_remote
        wt = worktree_dir / "feature-test"
        subprocess.run(
            ["git", "worktree", "add", str(wt), "feature-test"],
            cwd=local, check=True, capture_output=True,
        )
        marker = worktree_dir / "removed.log"
        _write_config(
            config_dir,
            f"""\
  - when: 'True'
    before_remove:
      - command: 'touch "{marker}"'
""",
        )
        monkeypatch.chdir(local)

        result = run_remove(make_ctx(branch_or_path="feature-test"))

        assert result == 0
        assert not wt.exists()
        assert marker.exists()


# ---------------------------------------------------------------------------
# Failure semantics
# ---------------------------------------------------------------------------


class TestRemoveBeforeRemoveFailures:
    """Critical vs non-critical rule failure semantics (ADR-0010)."""

    def test_critical_failure_blocks_remove(
        self,
        git_repo_with_remote: tuple[Path, Path],
        config_dir: Path,
        worktree_at: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        local, _ = git_repo_with_remote
        _write_config(config_dir, """\
  - when: 'True'
    before_remove:
      - command: 'false'
""")
        monkeypatch.chdir(local)

        result = run_remove(make_ctx(branch_or_path="feature-test"))

        assert result == 1
        assert worktree_at.exists(), "critical failure must block git worktree remove"
        captured = capsys.readouterr()
        assert "Action execution summary" in captured.err
        assert "Rule 0 (critical" in captured.err
        assert "Command failed" in captured.err
        assert "Removed worktree" not in captured.out

    def test_non_critical_failure_proceeds_with_remove(
        self,
        git_repo_with_remote: tuple[Path, Path],
        config_dir: Path,
        worktree_at: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        local, _ = git_repo_with_remote
        _write_config(config_dir, """\
  - when: 'True'
    critical: false
    before_remove:
      - command: 'false'
""")
        monkeypatch.chdir(local)

        result = run_remove(make_ctx(branch_or_path="feature-test"))

        assert result == 0
        assert not worktree_at.exists(), "non-critical failure must not block remove"
        captured = capsys.readouterr()
        assert "Action execution summary" in captured.err
        assert "Rule 0 (non-critical" in captured.err

    def test_critical_failure_with_force_still_blocks(
        self,
        git_repo_with_remote: tuple[Path, Path],
        config_dir: Path,
        worktree_at: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``--force`` is git-only. It must not bypass ``before_remove``.

        The worktree here is clean, so ``--force`` has no observable effect
        on git's side — but the ``before_remove`` rule still runs, and its
        critical failure must still block the remove.
        """
        local, _ = git_repo_with_remote
        _write_config(config_dir, """\
  - when: 'True'
    before_remove:
      - command: 'false'
""")
        monkeypatch.chdir(local)

        result = run_remove(make_ctx(branch_or_path="feature-test", force=True))

        assert result == 1
        assert worktree_at.exists(), "--force must not bypass a critical before_remove"

    def test_matcher_error_exits_two_and_skips_remove(
        self,
        git_repo_with_remote: tuple[Path, Path],
        config_dir: Path,
        worktree_at: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        local, _ = git_repo_with_remote
        _write_config(config_dir, """\
  - when: 'undefined_variable'
    before_remove:
      - command: 'true'
""")
        monkeypatch.chdir(local)

        result = run_remove(make_ctx(branch_or_path="feature-test"))

        assert result == 2
        assert worktree_at.exists(), "matcher error must skip git worktree remove"
        captured = capsys.readouterr()
        assert "Config error" in captured.err


# ---------------------------------------------------------------------------
# Branch lookup & template context
# ---------------------------------------------------------------------------


class TestRemoveContextAndBranchLookup:
    """The ``TemplateContext`` passed to ``before_remove`` predicates and
    commands must match the agreed contract: ``dest_path()`` is the worktree
    being removed, ``source_path()`` is its source repo, ``branch()``
    resolves to the checked-out branch (or ``""`` on detached HEAD)."""

    def test_branch_predicate_matches_checked_out_branch(
        self,
        git_repo_with_remote: tuple[Path, Path],
        config_dir: Path,
        worktree_at: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        local, _ = git_repo_with_remote
        # Rule only fires for the matching branch — but the action itself is a
        # no-op so the worktree still gets removed.
        _write_config(config_dir, """\
  - when: 'branch() == "feature-test"'
    critical: false
    before_remove:
      - command: 'true'
  - when: 'branch() == "never"'
    before_remove:
      - command: 'false'
""")
        monkeypatch.chdir(local)

        result = run_remove(make_ctx(branch_or_path="feature-test"))

        assert result == 0
        assert not worktree_at.exists()

    def test_dest_path_evaluates_to_worktree(
        self,
        git_repo_with_remote: tuple[Path, Path],
        config_dir: Path,
        worktree_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``{dest_path()}`` template should evaluate to the worktree path."""
        local, _ = git_repo_with_remote
        wt = worktree_dir / "feature-test"
        subprocess.run(
            ["git", "worktree", "add", str(wt), "feature-test"],
            cwd=local, check=True, capture_output=True,
        )
        marker = worktree_dir / "dest-was.log"
        _write_config(
            config_dir,
            f"""\
  - when: 'dest_path() == "{wt}"'
    before_remove:
      - command: 'touch "{marker}"'
""",
        )
        monkeypatch.chdir(local)

        result = run_remove(make_ctx(branch_or_path="feature-test"))

        assert result == 0
        assert marker.exists()

    def test_source_path_evaluates_to_source_repo(
        self,
        git_repo_with_remote: tuple[Path, Path],
        config_dir: Path,
        worktree_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        local, _ = git_repo_with_remote
        wt = worktree_dir / "feature-test"
        subprocess.run(
            ["git", "worktree", "add", str(wt), "feature-test"],
            cwd=local, check=True, capture_output=True,
        )
        marker = worktree_dir / "source-was.log"
        _write_config(
            config_dir,
            f"""\
  - when: 'source_path() == "{local}"'
    before_remove:
      - command: 'touch "{marker}"'
""",
        )
        monkeypatch.chdir(local)

        result = run_remove(make_ctx(branch_or_path="feature-test"))

        assert result == 0
        assert marker.exists()

    def test_path_based_remove_resolves_branch(
        self,
        git_repo_with_remote: tuple[Path, Path],
        config_dir: Path,
        worktree_at: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Removing by absolute path: ``branch()`` still resolves."""
        local, _ = git_repo_with_remote
        marker = worktree_at.parent / "branch-was.log"
        _write_config(
            config_dir,
            f"""\
  - when: 'branch() == "feature-test"'
    before_remove:
      - command: 'touch "{marker}"'
""",
        )
        monkeypatch.chdir(local)

        result = run_remove(make_ctx(branch_or_path=str(worktree_at)))

        assert result == 0
        assert marker.exists()

    def test_detached_head_branch_is_empty_string(
        self,
        git_repo_with_remote: tuple[Path, Path],
        config_dir: Path,
        worktree_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``branch()`` must not raise on detached HEAD — it should evaluate
        to ``""`` and predicates using ``branch() == ""`` should match."""
        local, _ = git_repo_with_remote
        wt = worktree_dir / "detached"
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(wt), "HEAD"],
            cwd=local, check=True, capture_output=True,
        )
        marker = worktree_dir / "detached.log"
        _write_config(
            config_dir,
            f"""\
  - when: 'branch() == ""'
    before_remove:
      - command: 'touch "{marker}"'
""",
        )
        monkeypatch.chdir(local)

        result = run_remove(make_ctx(branch_or_path=str(wt)))

        assert result == 0
        assert marker.exists()


# ---------------------------------------------------------------------------
# Tag-driven predicates
# ---------------------------------------------------------------------------


class TestRemoveTagDrivenPredicates:
    """``--tag key=value`` from the CLI must flow into ``tag()`` /
    ``tag_exist()`` predicates."""

    def test_tag_drives_predicate_match(
        self,
        git_repo_with_remote: tuple[Path, Path],
        config_dir: Path,
        worktree_at: Path,
        worktree_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        local, _ = git_repo_with_remote
        marker = worktree_dir / "tag.log"
        _write_config(
            config_dir,
            f"""\
  - when: 'tag("keep") == "archive"'
    before_remove:
      - command: 'touch "{marker}"'
  - when: 'tag("keep") != "archive"'
    before_remove:
      - command: 'false'
""",
        )
        monkeypatch.chdir(local)

        result = run_remove(
            make_ctx(branch_or_path="feature-test", tags={"keep": "archive"}),
        )

        assert result == 0
        assert marker.exists()

    def test_missing_tag_does_not_match_predicate(
        self,
        git_repo_with_remote: tuple[Path, Path],
        config_dir: Path,
        worktree_at: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Without the matching tag, only ``True`` rules fire — no failure."""
        local, _ = git_repo_with_remote
        _write_config(config_dir, """\
  - when: 'tag("missing") == "x"'
    before_remove:
      - command: 'false'
""")
        monkeypatch.chdir(local)

        result = run_remove(make_ctx(branch_or_path="feature-test"))

        assert result == 0
        assert not worktree_at.exists()


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------


class TestRemoveEmptyActionsList:
    """``actions: []`` (or missing) preserves existing behaviour."""

    def test_empty_actions_works(
        self,
        git_repo_with_remote: tuple[Path, Path],
        config_dir: Path,
        worktree_at: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        local, _ = git_repo_with_remote
        _write_config(config_dir)  # no actions block at all
        monkeypatch.chdir(local)

        result = run_remove(make_ctx(branch_or_path="feature-test"))

        assert result == 0
        assert not worktree_at.exists()