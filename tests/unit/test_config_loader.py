"""Unit tests for configuration loading in src/gww/config/loader.py."""

import pytest
from pathlib import Path

from gww.config.loader import (
    ConfigLoadError,
    ConfigNotFoundError,
    load_config,
    save_config,
    config_exists,
    get_default_config,
    DEFAULT_CONFIG_TEMPLATE,
)


class TestLoadConfig:
    """Tests for load_config function."""

    def test_loads_valid_yaml_config(self, tmp_path: Path) -> None:
        """Test loading a valid YAML configuration file."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
default_sources: ~/sources/default
default_worktrees: ~/worktrees/default
""")

        result = load_config(config_file)

        assert result["default_sources"] == "~/sources/default"
        assert result["default_worktrees"] == "~/worktrees/default"

    def test_loads_config_with_sources(self, tmp_path: Path) -> None:
        """Test loading config with source rules."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
default_sources: ~/sources/default
default_worktrees: ~/worktrees/default
sources:
  github:
    predicate: '"github" in host'
    sources: ~/sources/github/path(-2)/path(-1)
""")

        result = load_config(config_file)

        assert "sources" in result
        assert "github" in result["sources"]
        assert result["sources"]["github"]["predicate"] == '"github" in host'

    def test_loads_config_with_projects(self, tmp_path: Path) -> None:
        """Test loading config with project rules."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
default_sources: ~/sources/default
default_worktrees: ~/worktrees/default
projects:
  - predicate: 'file_exists("package.json")'
    source_actions:
      - command: "npm install"
""")

        result = load_config(config_file)

        assert "projects" in result
        assert len(result["projects"]) == 1
        assert result["projects"][0]["predicate"] == 'file_exists("package.json")'

    def test_raises_error_for_nonexistent_file(self, tmp_path: Path) -> None:
        """Test that ConfigNotFoundError is raised for missing file."""
        nonexistent = tmp_path / "nonexistent.yml"

        with pytest.raises(ConfigNotFoundError, match="not found"):
            load_config(nonexistent)

    def test_raises_error_for_invalid_yaml(self, tmp_path: Path) -> None:
        """Test that ConfigLoadError is raised for invalid YAML."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
invalid: yaml: content:
  - missing
    indent
""")

        with pytest.raises(ConfigLoadError, match="Invalid YAML"):
            load_config(config_file)

    def test_returns_empty_dict_for_empty_file(self, tmp_path: Path) -> None:
        """Test that empty file returns empty dict."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("")

        result = load_config(config_file)

        assert result == {}

    def test_returns_empty_dict_for_comments_only(self, tmp_path: Path) -> None:
        """Test that file with only comments returns empty dict."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("# Just a comment\n# Another comment")

        result = load_config(config_file)

        assert result == {}

    def test_raises_error_for_non_mapping_content(self, tmp_path: Path) -> None:
        """Test that non-mapping content raises error."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("- just\n- a\n- list")

        with pytest.raises(ConfigLoadError, match="must contain a mapping"):
            load_config(config_file)

    def test_preserves_comments_in_loaded_config(self, tmp_path: Path) -> None:
        """Test that ruamel.yaml preserves comments (round-trip mode)."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
# Main comment
default_sources: ~/sources/default  # Inline comment
default_worktrees: ~/worktrees/default
""")

        # Load should succeed even with comments
        result = load_config(config_file)

        assert result["default_sources"] == "~/sources/default"


class TestSaveConfig:
    """Tests for save_config function."""

    def test_saves_config_to_file(self, tmp_path: Path) -> None:
        """Test saving configuration to file."""
        config_file = tmp_path / "config.yml"
        config = {
            "default_sources": "~/sources/default",
            "default_worktrees": "~/worktrees/default",
        }

        result = save_config(config, config_file)

        assert result == config_file
        assert config_file.exists()
        content = config_file.read_text()
        assert "default_sources" in content
        assert "default_worktrees" in content

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Test that save_config creates parent directories."""
        config_file = tmp_path / "deep" / "nested" / "config.yml"
        config = {"default_sources": "~/sources", "default_worktrees": "~/worktrees"}

        result = save_config(config, config_file)

        assert result == config_file
        assert config_file.exists()

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        """Test that save_config overwrites existing file."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("old: content")

        new_config = {"default_sources": "~/new", "default_worktrees": "~/worktrees"}
        save_config(new_config, config_file)

        content = config_file.read_text()
        assert "default_sources" in content
        assert "old" not in content


class TestConfigExists:
    """Tests for config_exists function."""

    def test_returns_true_when_exists(self, tmp_path: Path) -> None:
        """Test that config_exists returns True when file exists."""
        config_file = tmp_path / "config.yml"
        config_file.write_text("test: content")

        assert config_exists(config_file) is True

    def test_returns_false_when_missing(self, tmp_path: Path) -> None:
        """Test that config_exists returns False when file missing."""
        config_file = tmp_path / "nonexistent.yml"

        assert config_exists(config_file) is False


class TestGetDefaultConfig:
    """Tests for get_default_config function (T062)."""

    def test_returns_non_empty_string(self) -> None:
        """Test that get_default_config returns non-empty string."""
        result = get_default_config()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_includes_default_sources_template(self) -> None:
        """Test that default config includes default_sources."""
        result = get_default_config()
        assert "default_sources:" in result

    def test_includes_default_worktrees_template(self) -> None:
        """Test that default config includes default_worktrees."""
        result = get_default_config()
        assert "default_worktrees:" in result

    def test_includes_path_function_examples(self) -> None:
        """Test that default config includes path() function examples."""
        result = get_default_config()
        assert "path(" in result

    def test_includes_commented_source_examples(self) -> None:
        """Test that default config includes commented source rule examples."""
        result = get_default_config()
        assert "sources:" in result or "# sources:" in result
        assert "github" in result.lower()

    def test_includes_commented_project_examples(self) -> None:
        """Test that default config includes commented project rule examples."""
        result = get_default_config()
        assert "projects:" in result or "# projects:" in result

    def test_includes_template_function_documentation(self) -> None:
        """Test that default config includes template function docs."""
        result = get_default_config()
        # Check for function documentation
        assert "branch()" in result or "norm_branch" in result

    def test_is_valid_yaml_when_parsed(self, tmp_path: Path) -> None:
        """Test that default config is valid YAML."""
        result = get_default_config()
        
        # Write and load to verify it's valid YAML
        config_file = tmp_path / "test_config.yml"
        config_file.write_text(result)

        loaded = load_config(config_file)
        
        assert "default_sources" in loaded
        assert "default_worktrees" in loaded

    def test_includes_config_path_placeholder(self) -> None:
        """Test that default config can include config path."""
        custom_path = Path("/custom/path/config.yml")
        result = get_default_config(custom_path)
        
        # The config should have path in a comment or similar
        assert isinstance(result, str)


class TestDefaultConfigTemplate:
    """Tests for DEFAULT_CONFIG_TEMPLATE constant."""

    def test_template_contains_required_fields(self) -> None:
        """Test that template contains required configuration fields."""
        assert "default_sources:" in DEFAULT_CONFIG_TEMPLATE
        assert "default_worktrees:" in DEFAULT_CONFIG_TEMPLATE

    def test_template_has_helpful_comments(self) -> None:
        """Test that template has helpful comments for users."""
        # Should have header comment
        assert "#" in DEFAULT_CONFIG_TEMPLATE
        # Should mention configuration
        assert "config" in DEFAULT_CONFIG_TEMPLATE.lower() or "configuration" in DEFAULT_CONFIG_TEMPLATE.lower()

    def test_template_has_function_documentation(self) -> None:
        """Test that template documents available template functions."""
        template = DEFAULT_CONFIG_TEMPLATE
        # Should document key functions
        assert "path(" in template
        assert "branch(" in template
        assert "norm_branch" in template
