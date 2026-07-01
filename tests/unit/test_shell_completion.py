"""Unit tests for shell completion generation in src/gww/utils/shell.py."""

from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

from gww.utils.shell import (
    _BASH_REMOVE_AWK,
    _FISH_REMOVE_AWK,
    _ZSH_REMOVE_AWK,
    get_completion_path,
    generate_bash_aliases,
    generate_bash_completion,
    generate_fish_aliases,
    generate_fish_completion,
    generate_zsh_aliases,
    generate_zsh_completion,
    generate_completion,
    install_completion,
    get_installation_instructions,
)

SH_BASH = shutil.which("bash")
SH_FISH = shutil.which("fish")
SH_ZSH = shutil.which("zsh")


class TestGetCompletionPath:
    """Tests for get_completion_path function."""

    def test_returns_bash_completion_path(self) -> None:
        """Test getting bash completion path."""
        path = get_completion_path("bash")
        
        assert ".bash_completion.d" in str(path)
        assert "gww" in str(path)

    def test_returns_zsh_completion_path(self) -> None:
        """Test getting zsh completion path."""
        path = get_completion_path("zsh")
        
        assert ".zsh" in str(path)
        assert "completions" in str(path)
        assert "_gww" in str(path)

    def test_returns_fish_completion_path(self) -> None:
        """Test getting fish completion path."""
        path = get_completion_path("fish")
        
        assert ".config/fish/completions" in str(path)
        assert "gww.fish" in str(path)

    def test_raises_error_for_unsupported_shell(self) -> None:
        """Test that unsupported shell raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported shell"):
            get_completion_path("powershell")


class TestGenerateBashCompletion:
    """Tests for generate_bash_completion function (T069)."""

    def test_generates_non_empty_script(self) -> None:
        """Test that bash completion script is non-empty."""
        script = generate_bash_completion()
        assert len(script) > 0

    def test_includes_completion_function(self) -> None:
        """Test that script includes completion function."""
        script = generate_bash_completion()
        assert "_gww_completions" in script

    def test_includes_complete_command(self) -> None:
        """Test that script includes complete command."""
        script = generate_bash_completion()
        assert "complete" in script

    def test_includes_main_commands(self) -> None:
        """Test that script includes main gww commands."""
        script = generate_bash_completion()
        assert "clone" in script
        assert "add" in script
        assert "remove" in script
        assert "pull" in script
        assert "init" in script

    def test_includes_init_subcommands(self) -> None:
        """Test that script includes init subcommands."""
        script = generate_bash_completion()
        assert "config" in script
        assert "shell" in script

    def test_includes_shell_options(self) -> None:
        """Test that script includes shell options for init shell."""
        script = generate_bash_completion()
        assert "bash" in script
        assert "zsh" in script
        assert "fish" in script

    def test_includes_dynamic_branch_completion(self) -> None:
        """Test that script includes dynamic branch completion for `add`."""
        script = generate_bash_completion()
        # `add` should still reference `git branch` so the user can pick any branch.
        assert "git branch" in script

    def test_remove_completion_filters_to_worktrees(self) -> None:
        """`remove` completer must use `git worktree list --porcelain`, not `git branch`.

        Bug regression: previously the `remove` completer used `git branch`
        which returned every local + remote branch — including ones not checked
        out in any worktree — so `gwr <TAB>` offered lots of bogus candidates.
        """
        script = generate_bash_completion()
        remove_block = _extract_case_block(script, "remove)")
        assert "git worktree list --porcelain" in remove_block
        assert "compgen" in remove_block

    def test_is_valid_bash_syntax(self) -> None:
        """Test that generated script has valid bash syntax elements."""
        script = generate_bash_completion()
        # Check for bash-specific syntax
        assert "COMPREPLY" in script
        assert "compgen" in script


class TestGenerateZshCompletion:
    """Tests for generate_zsh_completion function (T069)."""

    def test_generates_non_empty_script(self) -> None:
        """Test that zsh completion script is non-empty."""
        script = generate_zsh_completion()
        assert len(script) > 0

    def test_includes_compdef(self) -> None:
        """Test that script includes compdef directive."""
        script = generate_zsh_completion()
        assert "#compdef" in script

    def test_includes_gww_function(self) -> None:
        """Test that script includes _gww function."""
        script = generate_zsh_completion()
        assert "_gww" in script

    def test_includes_command_descriptions(self) -> None:
        """Test that script includes command descriptions."""
        script = generate_zsh_completion()
        # Zsh completions typically include descriptions
        assert "Clone" in script or "clone" in script.lower()
        assert "Add" in script or "worktree" in script.lower()

    def test_includes_arguments_handling(self) -> None:
        """Test that script includes _arguments."""
        script = generate_zsh_completion()
        assert "_arguments" in script

    def test_includes_option_completions(self) -> None:
        """Test that script includes option completions."""
        script = generate_zsh_completion()
        # Should have flag completions
        assert "--force" in script or "-f" in script
        assert "--create-branch" in script or "-c" in script


class TestGenerateFishCompletion:
    """Tests for generate_fish_completion function (T069)."""

    def test_generates_non_empty_script(self) -> None:
        """Test that fish completion script is non-empty."""
        script = generate_fish_completion()
        assert len(script) > 0

    def test_includes_complete_commands(self) -> None:
        """Test that script uses fish complete command."""
        script = generate_fish_completion()
        assert "complete -c gww" in script

    def test_includes_subcommand_completions(self) -> None:
        """Test that script includes subcommand completions."""
        script = generate_fish_completion()
        assert "clone" in script
        assert "add" in script
        assert "remove" in script

    def test_includes_option_completions(self) -> None:
        """Test that script includes option completions."""
        script = generate_fish_completion()
        # Fish uses -s for short, -l for long options
        assert "-l force" in script or "-s f" in script
        assert "-l help" in script or "-s h" in script

    def test_includes_description_flags(self) -> None:
        """Test that script includes -d flags for descriptions."""
        script = generate_fish_completion()
        assert "-d" in script

    def test_uses_seen_subcommand_from(self) -> None:
        """Test that script uses __fish_seen_subcommand_from."""
        script = generate_fish_completion()
        assert "__fish_seen_subcommand_from" in script

    def test_sources_git_completion(self) -> None:
        """Test that script sources git.fish to import __fish_git_branches."""
        script = generate_fish_completion()
        # Should source git.fish to make __fish_git_branches available
        assert "source" in script
        assert "git.fish" in script
        assert "__fish_data_dir" in script
        # Should use __fish_git_branches for branch completion
        assert "__fish_git_branches" in script


class TestGenerateCompletion:
    """Tests for generate_completion function."""

    def test_generates_bash_completion(self) -> None:
        """Test generating bash completion."""
        script = generate_completion("bash")
        assert "_gww_completions" in script

    def test_generates_zsh_completion(self) -> None:
        """Test generating zsh completion."""
        script = generate_completion("zsh")
        assert "#compdef" in script

    def test_generates_fish_completion(self) -> None:
        """Test generating fish completion."""
        script = generate_completion("fish")
        assert "complete -c gww" in script

    def test_raises_error_for_unsupported_shell(self) -> None:
        """Test that unsupported shell raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported shell"):
            generate_completion("invalid")


class TestInstallCompletion:
    """Tests for install_completion function."""

    def test_installs_completion_script(self, tmp_path: Path) -> None:
        """Test installing completion script to custom path."""
        custom_path = tmp_path / "completions" / "gww"

        result = install_completion("bash", custom_path)

        assert result == custom_path
        assert custom_path.exists()
        content = custom_path.read_text()
        assert "_gww_completions" in content

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Test that install_completion creates parent directories."""
        deep_path = tmp_path / "deep" / "nested" / "completions" / "gww"

        result = install_completion("bash", deep_path)

        assert result == deep_path
        assert deep_path.exists()

    def test_installs_correct_shell_script(self, tmp_path: Path) -> None:
        """Test that correct shell script is installed."""
        # Test bash
        bash_path = tmp_path / "bash_completion"
        install_completion("bash", bash_path)
        assert "_gww_completions" in bash_path.read_text()

        # Test zsh
        zsh_path = tmp_path / "zsh_completion"
        install_completion("zsh", zsh_path)
        assert "#compdef" in zsh_path.read_text()

        # Test fish
        fish_path = tmp_path / "fish_completion"
        install_completion("fish", fish_path)
        assert "complete -c gww" in fish_path.read_text()


class TestGetInstallationInstructions:
    """Tests for get_installation_instructions function."""

    def test_bash_instructions(self, tmp_path: Path) -> None:
        """Test getting bash installation instructions."""
        path = tmp_path / "gww"
        instructions = get_installation_instructions("bash", path)

        assert "bash" in instructions.lower()
        assert str(path) in instructions
        assert "source" in instructions.lower()

    def test_zsh_instructions(self, tmp_path: Path) -> None:
        """Test getting zsh installation instructions."""
        path = tmp_path / "_gww"
        instructions = get_installation_instructions("zsh", path)

        assert "zsh" in instructions.lower()
        assert str(path) in instructions
        assert "fpath" in instructions or "compinit" in instructions

    def test_fish_instructions(self, tmp_path: Path) -> None:
        """Test getting fish installation instructions."""
        path = tmp_path / "gww.fish"
        instructions = get_installation_instructions("fish", path)

        assert "fish" in instructions.lower()
        assert str(path) in instructions

    def test_generic_instructions_for_unknown_shell(self, tmp_path: Path) -> None:
        """Test getting generic instructions for unknown shell."""
        path = tmp_path / "completion"
        instructions = get_installation_instructions("other", path)

        assert str(path) in instructions


def _extract_case_block(script: str, marker: str, end_marker: str = ";;") -> str:
    """Return the bash `case` arm that starts with ``marker`` and ends at ``end_marker``.

    Used to assert structural properties of a single arm of the completion
    function's `case "${prev}"` block without depending on line numbers.
    """
    start = script.find(marker)
    assert start != -1, f"marker {marker!r} not found in script"
    end = script.find(end_marker, start)
    assert end != -1, f"end marker {end_marker!r} not found after {marker!r}"
    return script[start:end]


def _install_fake_git(tmp_path: Path) -> Path:
    """Write a fake ``git`` binary that returns canned worktree porcelain.

    Returns the directory that should be prepended to ``PATH`` for subprocess
    tests. The fake ``git`` answers two queries only: ``git rev-parse --git-dir``
    (returns a fake path so the completion code thinks we're in a repo) and
    ``git worktree list --porcelain`` (returns the canned fixture).
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    git = bin_dir / "git"
    git.write_text(
        textwrap.dedent(
            """\
            #!/bin/sh
            case "$*" in
              "rev-parse --git-dir")
                echo "/tmp/fake-git-dir"
                exit 0
                ;;
              "worktree list --porcelain")
                cat <<'PORCELAIN_EOF'
            worktree /home/u/myrepo
            HEAD 1111111111111111111111111111111111111111
            branch refs/heads/main

            worktree /home/u/myrepo-feature-x
            HEAD 2222222222222222222222222222222222222222
            branch refs/heads/feature-x

            worktree /home/u/myrepo-detached
            HEAD 3333333333333333333333333333333333333333
            detached

            PORCELAIN_EOF
                ;;
            esac
            """
        )
    )
    git.chmod(0o755)
    return bin_dir


class TestRemoveCompletionListsWorktrees:
    """`gww remove` completion must offer paths + checked-out branches only.

    Bug regression: the completer used to call ``git branch`` (all branches)
    or the shell-native branch helpers, which returned every local + remote
    branch. The fix is to parse ``git worktree list --porcelain``, drop the
    source entry, and emit each worktree's path (always) and its branch (only
    if not detached).
    """

    def test_bash_awk_script_skips_source(self, tmp_path: Path) -> None:
        """The awk pipe shipped with bash completion drops the source entry."""
        bin_dir = _install_fake_git(tmp_path)
        env = os.environ.copy()
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
        result = subprocess.run(
            ["bash", "-c", "git worktree list --porcelain 2>/dev/null | awk -v skip=1 '" + _BASH_REMOVE_AWK + "'"],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        candidates = result.stdout.splitlines()
        assert "/home/u/myrepo" not in candidates
        assert "main" not in candidates
        assert "/home/u/myrepo-feature-x" in candidates
        assert "feature-x" in candidates
        assert "/home/u/myrepo-detached" in candidates
        # Detached worktree has no branch line in porcelain, so no branch entry.
        assert candidates.count("/home/u/myrepo-feature-x") == 1
        assert candidates.count("feature-x") == 1

    def test_zsh_awk_script_emits_descriptions(self, tmp_path: Path) -> None:
        """The zsh/fish awk script emits `value<TAB>description` lines."""
        bin_dir = _install_fake_git(tmp_path)
        env = os.environ.copy()
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
        for label, script in (("zsh", _ZSH_REMOVE_AWK), ("fish", _FISH_REMOVE_AWK)):
            result = subprocess.run(
                ["bash", "-c", "git worktree list --porcelain 2>/dev/null | awk -v skip=1 '" + script + "'"],
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            lines = [ln for ln in result.stdout.splitlines() if ln]
            # Each line is `value<TAB>description`. Split once.
            values = [ln.split("\t", 1)[0] for ln in lines]
            # Source excluded (note: '/home/u/myrepo' is a prefix of the linked
            # worktree paths, so we must check exact membership, not substring).
            assert "/home/u/myrepo" not in values, f"{label}: source path leaked"
            assert "main" not in values, f"{label}: source branch leaked"
            # Cross-descriptions present
            joined = "\n".join(lines)
            assert "/home/u/myrepo-feature-x\tpath (branch: feature-x)" in joined, label
            assert "feature-x\tbranch (worktree at /home/u/myrepo-feature-x)" in joined, label
            # Detached path present, with "detached" description
            assert "/home/u/myrepo-detached" in values, label
            assert "detached at 3333333" in joined, label

    @pytest.mark.skipif(SH_BASH is None, reason="bash not installed")
    def test_bash_completion_live(self, tmp_path: Path) -> None:
        """Spawn a real bash, source the completion, and check COMPREPLY."""
        bin_dir = _install_fake_git(tmp_path)
        completion_file = tmp_path / "gww.bash"
        completion_file.write_text(generate_bash_completion())

        env = os.environ.copy()
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
        # No need for `compgen` to actually display — just need the values.
        result = subprocess.run(
            [
                "bash",
                "-c",
                (
                    f"source {completion_file}\n"
                    'COMP_WORDS=(gww remove "")\n'
                    "COMP_CWORD=2\n"
                    "_gww_completions\n"
                    'printf "%s\\n" "${COMPREPLY[@]}"\n'
                ),
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, f"bash failed: {result.stderr}"
        candidates = sorted(result.stdout.splitlines())
        # Source excluded
        assert "/home/u/myrepo" not in candidates
        assert "main" not in candidates
        # Worktree paths and checked-out branch present
        assert "/home/u/myrepo-feature-x" in candidates
        assert "feature-x" in candidates
        assert "/home/u/myrepo-detached" in candidates
        # No extras
        assert len(candidates) == 3

    @pytest.mark.skipif(SH_FISH is None, reason="fish not installed")
    def test_fish_remove_function_emits_candidates(self, tmp_path: Path) -> None:
        """Source the fish completion, call the helper, and parse the output."""
        bin_dir = _install_fake_git(tmp_path)
        completion_file = tmp_path / "gww.fish"
        completion_file.write_text(generate_fish_completion())

        # Fish re-resolves PATH from its own config, so push the fake dir
        # to the front of $PATH *inside* the fish process.
        env = os.environ.copy()
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
        script = (
            f"set -gx PATH {bin_dir} $PATH\n"
            f"source {completion_file}\n"
            "__gww_remove_worktrees\n"
        )
        result = subprocess.run(
            ["fish", "-c", script],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, f"fish failed: {result.stderr}"
        lines = [ln for ln in result.stdout.splitlines() if ln]
        # Source excluded
        assert not any("/home/u/myrepo" == ln.split("\t", 1)[0] for ln in lines)
        assert not any("main" == ln.split("\t", 1)[0] for ln in lines)
        # Checked-out branch and paths present
        assert any(
            ln.startswith("/home/u/myrepo-feature-x\t") and "branch: feature-x" in ln
            for ln in lines
        )
        assert any(
            ln.startswith("feature-x\t") and "worktree at /home/u/myrepo-feature-x" in ln
            for ln in lines
        )
        assert any(
            ln.startswith("/home/u/myrepo-detached\t") and "detached at 3333333" in ln
            for ln in lines
        )

    @pytest.mark.skipif(SH_ZSH is None, reason="zsh not installed")
    def test_zsh_awk_pipeline_runs(self, tmp_path: Path) -> None:
        """Run the awk pipeline used by the zsh completer under zsh.

        zsh's completion system can only be exercised from a real terminal, so
        we don't call the completion function directly. We do verify that the
        exact pipeline embedded in the generated script works in a zsh subshell.
        """
        bin_dir = _install_fake_git(tmp_path)
        env = os.environ.copy()
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
        result = subprocess.run(
            [
                "zsh",
                "-c",
                (
                    "git worktree list --porcelain 2>/dev/null | awk -v skip=1 '"
                    + _ZSH_REMOVE_AWK
                    + "'"
                ),
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, f"zsh failed: {result.stderr}"
        lines = [ln for ln in result.stdout.splitlines() if ln]
        values = [ln.split("\t", 1)[0] for ln in lines]
        joined = "\n".join(lines)
        assert "/home/u/myrepo" not in values
        assert "main" not in values
        assert "/home/u/myrepo-feature-x\tpath (branch: feature-x)" in joined
        assert "feature-x\tbranch (worktree at /home/u/myrepo-feature-x)" in joined
        assert "/home/u/myrepo-detached" in values
        assert "detached at 3333333" in joined

    def test_zsh_remove_uses_worktrees_completer_not_branch_names(self) -> None:
        """Structural check: zsh `remove` case must call our function, not branch helper."""
        script = generate_zsh_completion()
        # Locate the `remove)` arm inside `_gww()`
        start = script.find("remove)")
        assert start != -1
        end = script.find(";;", start)
        assert end != -1
        arm = script[start:end]
        assert "_gww_worktrees" in arm
        assert "_git_branch_names" not in arm
        # The function itself must use `git worktree list --porcelain` and `_describe`.
        # The function spans multiple lines — find the opening brace, then the
        # matching closing brace by tracking brace depth.
        func_start = script.find("_gww_worktrees()")
        assert func_start != -1
        brace = script.find("{", func_start)
        depth = 1
        i = brace + 1
        while i < len(script) and depth > 0:
            if script[i] == "{":
                depth += 1
            elif script[i] == "}":
                depth -= 1
            i += 1
        func_body = script[func_start:i]
        assert "git worktree list --porcelain" in func_body
        assert "_describe" in func_body

    def test_fish_remove_completion_does_not_use_git_branches(self) -> None:
        """Structural check: fish `remove` completion must not call __fish_git_branches."""
        script = generate_fish_completion()
        # The `add` arm still uses __fish_git_branches (correct).
        # The `remove` section must not. The fish completion defines a
        # `__gww_remove_worktrees` helper inside the `# remove completions`
        # section, so we look at that whole section.
        remove_arm_start = script.find("# remove completions")
        assert remove_arm_start != -1
        next_section = script.find("# migrate", remove_arm_start)
        assert next_section != -1
        remove_section = script[remove_arm_start:next_section]
        # The candidates line should not reference __fish_git_branches.
        assert "__fish_git_branches" not in remove_section
        # The helper function (defined inline in this section) should use
        # `git worktree list --porcelain`.
        assert "git worktree list --porcelain" in remove_section
        # The `__gww_remove_worktrees` helper should be wired into the
        # `complete -a` line for remove.
        assert "(__gww_remove_worktrees)" in remove_section


class TestRemoveCommandTagCompletion:
    """`gww remove` accepts ``--tag key=value`` (ADR-0011) — completion
    scripts must advertise it so users can discover the flag."""

    def test_bash_remove_lists_tag_option(self) -> None:
        """Bash: the ``-t|--tag`` ``case`` branch must terminate cleanly
        (returning 0) so ``-t`` is not completed as a path."""
        script = generate_bash_completion()
        # The ``-t|--tag)`` arm lives after the ``remove)`` arm, in the same
        # ``case "${prev}"`` block. Look for it explicitly.
        assert "-t|--tag)" in script
        tag_block = _extract_case_block(script, "-t|--tag)")
        assert "return 0" in tag_block

    def test_zsh_remove_lists_tag_option(self) -> None:
        script = generate_zsh_completion()
        start = script.find("remove)")
        assert start != -1
        end = script.find(";;", start)
        arm = script[start:end]
        assert "'-t[Tag" in arm
        assert "'--tag[Tag" in arm

    def test_fish_remove_lists_tag_option(self) -> None:
        script = generate_fish_completion()
        remove_arm_start = script.find("# remove completions")
        assert remove_arm_start != -1
        next_section = script.find("# migrate", remove_arm_start)
        assert next_section != -1
        remove_section = script[remove_arm_start:next_section]
        assert "-s t -l tag" in remove_section


class TestFishAliasPromptRepaint:
    """ADR-0013: every fish alias must end every terminal branch with
    ``commandline -f repaint`` so the prompt redraws after navigation.
    Bash and zsh aliases must NOT receive the call: their prompts re-evaluate
    automatically and they have no queue-based repaint primitive.
    """

    @staticmethod
    def _line_index(lines: list[str], needle: str) -> int:
        """Return the index of the first line that contains ``needle``.

        Raises ``AssertionError`` if no line matches; useful to express
        "X appears before Y" without leaning on textual ordering tricks.
        """
        for i, line in enumerate(lines):
            if needle in line:
                return i
        raise AssertionError(f"line containing {needle!r} not found")

    def test_gwc_contains_repaint(self) -> None:
        """``gwc`` calls ``commandline -f repaint`` exactly once."""
        script = generate_fish_aliases()["gwc"]
        assert script.count("commandline -f repaint") == 1

    def test_gwa_contains_repaint(self) -> None:
        """``gwa`` calls ``commandline -f repaint`` exactly once."""
        script = generate_fish_aliases()["gwa"]
        assert script.count("commandline -f repaint") == 1

    def test_gwr_contains_repaint_per_terminal_branch(self) -> None:
        """``gwr`` calls ``commandline -f repaint`` once per terminal branch
        (clean-remove, force-accept, decline, error-return) — four total.
        See ADR-0013 §"placement rule"."""
        script = generate_fish_aliases()["gwr"]
        count = script.count("commandline -f repaint")
        # Spec floor in the handoff: at least three occurrences (one per
        # terminal branch as described). The implementation emits four
        # (clean-remove, force-accept, decline, error-return) — assert
        # the actual placement rather than a bare count.
        assert count >= 3, f"expected >= 3 repaint calls in gwr, got {count}"

    def test_gwc_repaint_runs_after_cd(self) -> None:
        """``gwc`` must repaint AFTER it has changed directory.

        Guard against someone moving the call to the top of the function
        — the prompt would render against the stale PWD.
        """
        lines = generate_fish_aliases()["gwc"].splitlines()
        cd_idx = self._line_index(lines, 'cd "$target_path"')
        repaint_idx = self._line_index(lines, "commandline -f repaint")
        assert cd_idx < repaint_idx, (
            "repaint must come after cd so the prompt reflects the new PWD"
        )

    def test_gwa_repaint_runs_after_cd(self) -> None:
        """``gwa`` must repaint AFTER it has changed directory."""
        lines = generate_fish_aliases()["gwa"].splitlines()
        cd_idx = self._line_index(lines, 'cd "$target_path"')
        repaint_idx = self._line_index(lines, "commandline -f repaint")
        assert cd_idx < repaint_idx, (
            "repaint must come after cd so the prompt reflects the new PWD"
        )

    def test_gwr_repaint_precedes_every_return(self) -> None:
        """``gwr`` repaints immediately before each ``return`` statement.

        The force-decline branch returns 1 and the error branch returns
        $exit_code — both must repaint just before. Catches a regression
        where someone writes the repaint at the wrong indent level or
        attaches it to the wrong branch.
        """
        lines = generate_fish_aliases()["gwr"].splitlines()

        for return_needle in ("return 1", "return $exit_code"):
            return_idx = self._line_index(lines, return_needle)
            # Walk backwards to find the nearest preceding line that is
            # neither blank nor a trailing comment.
            prev_idx = return_idx - 1
            while prev_idx >= 0 and (
                lines[prev_idx].strip() == ""
                or lines[prev_idx].lstrip().startswith("#")
            ):
                prev_idx -= 1
            assert prev_idx >= 0, f"no preceding line before {return_needle!r}"
            assert "commandline -f repaint" in lines[prev_idx], (
                f"expected repaint immediately before {return_needle!r}, "
                f"found: {lines[prev_idx]!r}"
            )

    def test_bash_aliases_have_no_repaint(self) -> None:
        """Bash aliases must NOT call ``commandline -f repaint``.

        Bash's PS1 re-evaluates automatically on the next prompt; the
        fish-specific queue-based repaint has no equivalent there.
        """
        script = generate_bash_aliases()
        assert "commandline" not in script
        assert "repaint" not in script

    def test_zsh_aliases_have_no_repaint(self) -> None:
        """Zsh aliases must NOT call ``commandline -f repaint`` for the
        same reason as bash (PROMPT/RPROMPT re-evaluate automatically)."""
        script = generate_zsh_aliases()
        assert "commandline" not in script
        assert "repaint" not in script
