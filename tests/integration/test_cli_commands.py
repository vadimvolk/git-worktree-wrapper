"""Integration tests for init commands (config and shell) (T063, T070)."""

import pytest
import subprocess
from pathlib import Path
from unittest.mock import patch

from sgw.cli.commands.init import run_init_config, run_init_shell
from sgw.config.loader import load_config
from sgw.utils.xdg import get_config_path


@pytest.fixture
def config_dir(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary config directory and patch get_config_path."""
    config_path = tmp_path_factory.mktemp("config")
    test_config_file = config_path / "sgw" / "config.yml"
    
    # Patch get_config_path to return our test path
    monkeypatch.setattr("sgw.utils.xdg.get_config_path", lambda appname="sgw": test_config_file)
    monkeypatch.setattr("sgw.config.loader.get_config_path", lambda: test_config_file)
    monkeypatch.setattr("sgw.cli.commands.init.get_config_path", lambda: test_config_file)
    
    return config_path


class TestInitConfigCommand:
    """Integration tests for init config command (T063)."""

    def test_creates_default_config(
        self,
        config_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that init config creates default configuration file."""
        class Args:
            verbose = 0
            quiet = False

        result = run_init_config(Args())

        assert result == 0
        # Verify config was created
        config_path = config_dir / "sgw" / "config.yml"
        assert config_path.exists()

        # Verify output
        captured = capsys.readouterr()
        assert "Created config file" in captured.out

    def test_config_is_valid_yaml(
        self,
        config_dir: Path,
    ) -> None:
        """Test that created config is valid YAML."""
        class Args:
            verbose = 0
            quiet = False

        run_init_config(Args())

        config_path = config_dir / "sgw" / "config.yml"
        # Should be loadable
        config = load_config(config_path)
        assert "default_sources" in config
        assert "default_worktrees" in config

    def test_config_contains_documentation(
        self,
        config_dir: Path,
    ) -> None:
        """Test that config contains helpful documentation."""
        class Args:
            verbose = 0
            quiet = False

        run_init_config(Args())

        config_path = config_dir / "sgw" / "config.yml"
        content = config_path.read_text()

        # Should contain documentation
        assert "#" in content  # Has comments
        assert "path(" in content  # Documents path function
        assert "branch" in content.lower()  # Documents branch functions

    def test_fails_when_config_exists(
        self,
        config_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that init config fails when config already exists."""
        # Create config first
        config_path = config_dir / "sgw" / "config.yml"
        config_path.parent.mkdir(parents=True)
        config_path.write_text("existing: config")

        class Args:
            verbose = 0
            quiet = False

        result = run_init_config(Args())

        assert result == 1
        captured = capsys.readouterr()
        assert "already exists" in captured.err

    def test_quiet_mode_no_output(
        self,
        config_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that quiet mode suppresses output."""
        class Args:
            verbose = 0
            quiet = True

        result = run_init_config(Args())

        assert result == 0
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_creates_parent_directories(
        self,
        config_dir: Path,
    ) -> None:
        """Test that init config creates parent directories."""
        # Config dir exists but sgw subdirectory doesn't
        class Args:
            verbose = 0
            quiet = False

        result = run_init_config(Args())

        assert result == 0
        config_path = config_dir / "sgw" / "config.yml"
        assert config_path.exists()


class TestInitShellCommand:
    """Integration tests for init shell command (T070)."""

    def test_installs_bash_completion(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test installing bash completion script."""
        # Override home directory to use tmp_path
        monkeypatch.setenv("HOME", str(tmp_path))

        class Args:
            shell = "bash"
            verbose = 0
            quiet = False

        result = run_init_shell(Args())

        assert result == 0
        captured = capsys.readouterr()
        assert "bash" in captured.out.lower()

    def test_installs_zsh_completion(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test installing zsh completion script."""
        monkeypatch.setenv("HOME", str(tmp_path))

        class Args:
            shell = "zsh"
            verbose = 0
            quiet = False

        result = run_init_shell(Args())

        assert result == 0
        captured = capsys.readouterr()
        assert "zsh" in captured.out.lower()

    def test_installs_fish_completion(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test installing fish completion script."""
        monkeypatch.setenv("HOME", str(tmp_path))

        class Args:
            shell = "fish"
            verbose = 0
            quiet = False

        result = run_init_shell(Args())

        assert result == 0
        captured = capsys.readouterr()
        assert "fish" in captured.out.lower()

    def test_fails_for_invalid_shell(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that init shell fails for invalid shell name."""
        monkeypatch.setenv("HOME", str(tmp_path))

        class Args:
            shell = "powershell"
            verbose = 0
            quiet = False

        result = run_init_shell(Args())

        assert result == 1
        captured = capsys.readouterr()
        assert "Invalid shell" in captured.err

    def test_quiet_mode_no_output(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that quiet mode suppresses output."""
        monkeypatch.setenv("HOME", str(tmp_path))

        class Args:
            shell = "bash"
            verbose = 0
            quiet = True

        result = run_init_shell(Args())

        assert result == 0
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_bash_completion_content_is_valid(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that bash completion content has required elements."""
        monkeypatch.setenv("HOME", str(tmp_path))

        class Args:
            shell = "bash"
            verbose = 0
            quiet = True

        run_init_shell(Args())

        # Find and read the completion file
        completion_file = tmp_path / ".bash_completion.d" / "sgw"
        assert completion_file.exists()

        content = completion_file.read_text()
        assert "_sgw_completions" in content
        assert "complete" in content

    def test_zsh_completion_content_is_valid(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that zsh completion content has required elements."""
        monkeypatch.setenv("HOME", str(tmp_path))

        class Args:
            shell = "zsh"
            verbose = 0
            quiet = True

        run_init_shell(Args())

        # Find and read the completion file
        completion_file = tmp_path / ".zsh" / "completions" / "_sgw"
        assert completion_file.exists()

        content = completion_file.read_text()
        assert "#compdef" in content
        assert "_sgw" in content

    def test_fish_completion_content_is_valid(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that fish completion content has required elements."""
        monkeypatch.setenv("HOME", str(tmp_path))

        class Args:
            shell = "fish"
            verbose = 0
            quiet = True

        run_init_shell(Args())

        # Find and read the completion file
        completion_file = tmp_path / ".config" / "fish" / "completions" / "sgw.fish"
        assert completion_file.exists()

        content = completion_file.read_text()
        assert "complete -c sgw" in content

    def test_shows_installation_instructions(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that init shell shows installation instructions."""
        monkeypatch.setenv("HOME", str(tmp_path))

        class Args:
            shell = "bash"
            verbose = 0
            quiet = False

        run_init_shell(Args())

        captured = capsys.readouterr()
        # Should include instructions for activating
        assert "source" in captured.out.lower() or "bashrc" in captured.out.lower()
