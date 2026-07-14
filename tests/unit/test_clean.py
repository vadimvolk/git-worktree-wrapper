"""Unit tests for ``gww.cli.commands.clean`` internals.

These exercise the per-branch label/summary logic and provider-template
rendering without touching real git worktrees. The full git-based flow is
covered by ``tests/integration/test_clean_command.py``.
"""

from __future__ import annotations

from pathlib import Path

from gww.cli.commands.clean import (
    EXIT_COMMAND_NOT_FOUND,
    _format_summary,
    _git_merged_branch_set,
    _is_main_worktree,
    _main_checkout_path,
    _provider_template_for_branch,
    _run_provider_command,
)
from gww.config.validator import ProviderConfig
from gww.utils.uri import parse_uri


class TestFormatSummary:
    """The end-of-execution summary per the locked format."""

    def test_real_run_no_extras(self) -> None:
        assert _format_summary(
            removed=3, kept=2, failed=0, timed_out=0, dry_run=False,
        ) == "Removed 3; kept 2"

    def test_real_run_with_failed(self) -> None:
        assert _format_summary(
            removed=3, kept=2, failed=1, timed_out=0, dry_run=False,
        ) == "Removed 3; kept 2; 1 failed"

    def test_real_run_with_timed_out(self) -> None:
        assert _format_summary(
            removed=3, kept=2, failed=0, timed_out=4, dry_run=False,
        ) == "Removed 3; kept 2; 4 timed out"

    def test_real_run_with_failed_and_timed_out(self) -> None:
        assert _format_summary(
            removed=3, kept=2, failed=1, timed_out=4, dry_run=False,
        ) == "Removed 3; kept 2; 1 failed; 4 timed out"

    def test_dry_run_no_extras(self) -> None:
        assert _format_summary(
            removed=3, kept=2, failed=0, timed_out=0, dry_run=True,
        ) == "Would remove 3; would keep 2"

    def test_dry_run_with_timed_out(self) -> None:
        assert _format_summary(
            removed=3, kept=2, failed=0, timed_out=4, dry_run=True,
        ) == "Would remove 3; would keep 2; 4 timed out"

    def test_dry_run_omits_failed_even_if_nonzero(self) -> None:
        """F is always 0 in dry-run because no side effects ran."""
        assert _format_summary(
            removed=3, kept=2, failed=99, timed_out=0, dry_run=True,
        ) == "Would remove 3; would keep 2"

    def test_zero_counts_omitted(self) -> None:
        """Zero extras are not printed; only nonzero counts append."""
        out = _format_summary(
            removed=5, kept=3, failed=0, timed_out=2, dry_run=False,
        )
        assert "; 0 failed" not in out
        assert "; 2 timed out" in out


class TestProviderTemplateRendering:
    """``_provider_template_for_branch`` evaluates the merged template
    against a per-branch context."""

    def _pcfg(self, merged: str) -> ProviderConfig:
        return ProviderConfig(
            kind="github",
            host_patterns=[r"^github\.com$"],
            merged=merged,
        )

    def test_renders_branch_function(self) -> None:
        provider = self._pcfg("gh pr list --head branch() --state merged")
        rendered = _provider_template_for_branch(
            provider, "feature/x", parse_uri("https://github.com/user/repo.git"),
        )
        assert rendered == "gh pr list --head feature/x --state merged"

    def test_renders_with_uri_function(self) -> None:
        provider = self._pcfg("echo host()")
        rendered = _provider_template_for_branch(
            provider, "x", parse_uri("https://github.com/user/repo.git"),
        )
        assert rendered == "echo github.com"

    def test_renders_without_uri(self) -> None:
        """When the source has no remote URI, the URI context is absent
        and template functions referencing URI fields raise. We pass
        ``uri=None`` so the rendering context has no URI; using
        only ``branch()`` keeps the template evaluable."""
        provider = self._pcfg("gh pr list --head branch() --state merged")
        rendered = _provider_template_for_branch(provider, "main", None)
        assert rendered == "gh pr list --head main --state merged"


class TestGitMergedBranchSet:
    """The ``--merged`` git fallback uses ``git branch --merged``."""

    def test_returns_set_of_merged_branches(self, tmp_path: Path) -> None:
        import subprocess

        from gww.git.branch import get_default_branch

        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "t@t.com"],
            cwd=tmp_path, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "T"],
            cwd=tmp_path, check=True, capture_output=True,
        )
        (tmp_path / "a").write_text("a")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "branch", "feature"], cwd=tmp_path, check=True, capture_output=True,
        )

        default = get_default_branch(tmp_path)
        merged = _git_merged_branch_set(tmp_path, default)

        assert default not in merged
        assert "feature" in merged


class TestRunProviderCommand:
    """Subprocess for provider commands inherits both streams and respects
    the timeout. ``shell=True`` means a missing command produces exit 127
    rather than :class:`FileNotFoundError`; we verify the actual contract."""

    def test_exit_zero(self) -> None:
        assert _run_provider_command("true") == 0

    def test_exit_nonzero(self) -> None:
        assert _run_provider_command("false") == 1

    def test_missing_command_returns_127(self) -> None:
        """The shell exits 127 on "command not found"; this is the
        signal ``clean`` uses to fire the ``skip (... not found)`` label.
        ``FileNotFoundError`` is NOT raised by ``shell=True`` for missing
        commands inside the shell pipeline."""
        assert (
            _run_provider_command("this-binary-definitely-does-not-exist-xyz123")
            == EXIT_COMMAND_NOT_FOUND
        )

    def test_exit_127_constant_matches_posix(self) -> None:
        """Sanity check the constant; the shell semantics are stable."""
        assert EXIT_COMMAND_NOT_FOUND == 127


class TestMainWorktreeFilter:
    """``_is_main_worktree`` identifies the source's own checkout."""

    def test_main_matches(self, tmp_path: Path) -> None:
        main = _main_checkout_path(tmp_path)
        assert _is_main_worktree(tmp_path, main)

    def test_subdir_does_not_match(self, tmp_path: Path) -> None:
        wt = tmp_path / "feature"
        wt.mkdir()
        main = _main_checkout_path(tmp_path)
        assert not _is_main_worktree(wt, main)