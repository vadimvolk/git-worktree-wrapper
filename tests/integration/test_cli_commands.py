"""Integration tests for init commands (config and shell) (T063, T070)."""

import pytest
from pathlib import Path

from gww.cli.commands.init import run_init_config, run_init_shell
from gww.config.loader import load_config
from tests.conftest import make_ctx


class TestInitConfigCommand:
    """Integration tests for init config command (T063)."""

    def test_creates_default_config(
        self,
        config_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that init config creates default configuration file."""
        result = run_init_config(make_ctx())

        assert result == 0
        config_path = config_dir / "gww" / "config.yml"
        assert config_path.exists()

        captured = capsys.readouterr()
        assert "Created config file" in captured.out

    def test_config_is_valid_yaml(
        self,
        config_dir: Path,
    ) -> None:
        """Test that created config is valid YAML."""
        run_init_config(make_ctx())

        config_path = config_dir / "gww" / "config.yml"
        config = load_config(config_path)
        assert "default_sources" in config
        assert "default_worktrees" in config

    def test_config_contains_documentation(
        self,
        config_dir: Path,
    ) -> None:
        """Test that config contains helpful documentation."""
        run_init_config(make_ctx())

        config_path = config_dir / "gww" / "config.yml"
        content = config_path.read_text()

        assert "#" in content
        assert "path(" in content
        assert "branch" in content.lower()

    def test_fails_when_config_exists(
        self,
        config_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that init config fails when config already exists."""
        config_path = config_dir / "gww" / "config.yml"
        config_path.parent.mkdir(parents=True)
        config_path.write_text("existing: config")

        result = run_init_config(make_ctx())

        assert result == 1
        captured = capsys.readouterr()
        assert "already exists" in captured.err

    def test_quiet_mode_no_output(
        self,
        config_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test that quiet mode suppresses output."""
        result = run_init_config(make_ctx(quiet=True))

        assert result == 0
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_creates_parent_directories(
        self,
        config_dir: Path,
    ) -> None:
        """Test that init config creates parent directories."""
        result = run_init_config(make_ctx())

        assert result == 0
        config_path = config_dir / "gww" / "config.yml"
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
        monkeypatch.setenv("HOME", str(tmp_path))

        result = run_init_shell(make_ctx(shell="bash"))

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

        result = run_init_shell(make_ctx(shell="zsh"))

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

        result = run_init_shell(make_ctx(shell="fish"))

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

        result = run_init_shell(make_ctx(shell="powershell"))

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

        result = run_init_shell(make_ctx(shell="bash", quiet=True))

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

        run_init_shell(make_ctx(shell="bash", quiet=True))

        completion_file = tmp_path / ".bash_completion.d" / "gww"
        assert completion_file.exists()

        content = completion_file.read_text()
        assert "_gww_completions" in content
        assert "complete" in content

    def test_zsh_completion_content_is_valid(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that zsh completion content has required elements."""
        monkeypatch.setenv("HOME", str(tmp_path))

        run_init_shell(make_ctx(shell="zsh", quiet=True))

        completion_file = tmp_path / ".zsh" / "completions" / "_gww"
        assert completion_file.exists()

        content = completion_file.read_text()
        assert "#compdef" in content
        assert "_gww" in content

    def test_fish_completion_content_is_valid(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that fish completion content has required elements."""
        monkeypatch.setenv("HOME", str(tmp_path))

        run_init_shell(make_ctx(shell="fish", quiet=True))

        completion_file = tmp_path / ".config" / "fish" / "completions" / "gww.fish"
        assert completion_file.exists()

        content = completion_file.read_text()
        assert "complete -c gww" in content

    def test_shows_installation_instructions(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that init shell shows installation instructions."""
        monkeypatch.setenv("HOME", str(tmp_path))

        run_init_shell(make_ctx(shell="bash"))

        captured = capsys.readouterr()
        assert "source" in captured.out.lower() or "bashrc" in captured.out.lower()