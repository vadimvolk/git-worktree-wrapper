"""Unit tests for shell completion generation in src/gww/utils/shell.py."""

import pytest
from pathlib import Path

from gww.utils.shell import (
    get_completion_path,
    generate_bash_completion,
    generate_zsh_completion,
    generate_fish_completion,
    generate_completion,
    install_completion,
    get_installation_instructions,
)


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
        """Test that script includes dynamic branch completion."""
        script = generate_bash_completion()
        # Should reference git branch for completion
        assert "git" in script and "branch" in script

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
