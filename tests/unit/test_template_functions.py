"""Unit tests for template functions in src/gww/template/functions.py."""

import os
import subprocess
from pathlib import Path

import pytest

from gww.template.functions import (
    FunctionRegistry,
    TemplateContext,
    create_function_registry,
    create_project_functions,
)
from gww.template.evaluator import evaluate_template
from gww.utils.uri import parse_uri


def _init_git_repo(path: Path) -> None:
    """Initialize a git repository at the given path."""
    subprocess.run(
        ["git", "init"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    # Configure git user for the repo (needed for commits)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=path,
        check=True,
        capture_output=True,
    )


def _create_initial_commit(path: Path) -> None:
    """Create an initial commit in the git repository."""
    readme = path / "README.md"
    readme.write_text("# Test Repo\n")
    subprocess.run(
        ["git", "add", "."],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=path,
        check=True,
        capture_output=True,
    )


def _add_worktree(repo_path: Path, worktree_path: Path, branch: str) -> None:
    """Add a worktree to the repository."""
    subprocess.run(
        ["git", "worktree", "add", str(worktree_path), "-b", branch],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )


class TestTagFunction:
    """Tests for tag() template function."""

    def test_tag_returns_value_when_exists(self) -> None:
        """Test tag() returns tag value when tag exists with value."""
        context = TemplateContext(tags={"env": "production", "version": "1.2.3"})
        registry = FunctionRegistry(context)
        functions = registry.get_functions()

        result = functions["tag"]("env")

        assert result == "production"

    def test_tag_returns_empty_when_tag_has_empty_value(self) -> None:
        """Test tag() returns empty string when tag exists but has empty value."""
        context = TemplateContext(tags={"flag": ""})
        registry = FunctionRegistry(context)
        functions = registry.get_functions()

        result = functions["tag"]("flag")

        assert result == ""

    def test_tag_returns_empty_when_tag_not_exists(self) -> None:
        """Test tag() returns empty string when tag does not exist."""
        context = TemplateContext(tags={"other": "value"})
        registry = FunctionRegistry(context)
        functions = registry.get_functions()

        result = functions["tag"]("missing")

        assert result == ""

    def test_tag_returns_empty_when_no_tags(self) -> None:
        """Test tag() returns empty string when no tags are provided."""
        context = TemplateContext()
        registry = FunctionRegistry(context)
        functions = registry.get_functions()

        result = functions["tag"]("any")

        assert result == ""

    def test_tag_in_template_evaluation(self) -> None:
        """Test tag() function in template evaluation."""
        context = TemplateContext(
            uri=parse_uri("https://github.com/user/repo.git"),
            tags={"env": "dev", "region": "us-east"},
        )

        result = evaluate_template("~/sources/tag('env')/path(-1)", context)

        assert "dev" in result
        assert "repo" in result

    def test_tag_in_template_with_multiple_tags(self) -> None:
        """Test tag() function with multiple tags in template."""
        context = TemplateContext(
            uri=parse_uri("https://github.com/user/repo.git"),
            tags={"env": "prod", "version": "2.0", "region": "eu"},
        )

        result = evaluate_template(
            "~/sources/tag('env')/tag('version')/path(-1)", context
        )

        assert "prod" in result
        assert "2.0" in result
        assert "repo" in result

    def test_tag_with_empty_value_in_template(self) -> None:
        """Test tag() function with empty value in template."""
        context = TemplateContext(
            uri=parse_uri("https://github.com/user/repo.git"),
            tags={"flag": ""},
        )

        result = evaluate_template("~/sources/tag('flag')/path(-1)", context)

        # Should still work, just have empty string in path
        assert "repo" in result

    def test_tag_with_missing_tag_in_template(self) -> None:
        """Test tag() function with missing tag in template."""
        context = TemplateContext(
            uri=parse_uri("https://github.com/user/repo.git"),
            tags={"other": "value"},
        )

        result = evaluate_template("~/sources/tag('missing')/path(-1)", context)

        # Should return empty string, path should still work
        assert "repo" in result


class TestTagExistFunction:
    """Tests for tag_exist() template function."""

    def test_tag_exist_returns_true_when_tag_exists_with_value(self) -> None:
        """Test tag_exist() returns True when tag exists with value."""
        context = TemplateContext(tags={"env": "production"})
        registry = FunctionRegistry(context)
        functions = registry.get_functions()

        result = functions["tag_exist"]("env")

        assert result is True

    def test_tag_exist_returns_true_when_tag_exists_with_empty_value(self) -> None:
        """Test tag_exist() returns True when tag exists with empty value."""
        context = TemplateContext(tags={"flag": ""})
        registry = FunctionRegistry(context)
        functions = registry.get_functions()

        result = functions["tag_exist"]("flag")

        assert result is True

    def test_tag_exist_returns_false_when_tag_not_exists(self) -> None:
        """Test tag_exist() returns False when tag does not exist."""
        context = TemplateContext(tags={"other": "value"})
        registry = FunctionRegistry(context)
        functions = registry.get_functions()

        result = functions["tag_exist"]("missing")

        assert result is False

    def test_tag_exist_returns_false_when_no_tags(self) -> None:
        """Test tag_exist() returns False when no tags are provided."""
        context = TemplateContext()
        registry = FunctionRegistry(context)
        functions = registry.get_functions()

        result = functions["tag_exist"]("any")

        assert result is False

    def test_tag_exist_in_template_evaluation(self) -> None:
        """Test tag_exist() function in template evaluation."""
        context = TemplateContext(
            uri=parse_uri("https://github.com/user/repo.git"),
            tags={"env": "dev"},
        )

        # Note: tag_exist returns bool, so we need to convert to string in template
        # This tests the function works, but template evaluation converts bool to string
        registry = FunctionRegistry(context)
        functions = registry.get_functions()

        result = functions["tag_exist"]("env")

        assert result is True

    def test_tag_exist_with_multiple_tags(self) -> None:
        """Test tag_exist() function with multiple tags."""
        context = TemplateContext(tags={"tag1": "value1", "tag2": "value2"})
        registry = FunctionRegistry(context)
        functions = registry.get_functions()

        assert functions["tag_exist"]("tag1") is True
        assert functions["tag_exist"]("tag2") is True
        assert functions["tag_exist"]("tag3") is False


class TestTagFunctionsIntegration:
    """Integration tests for tag and tag_exist functions."""

    def test_tag_and_tag_exist_together(self) -> None:
        """Test using tag() and tag_exist() together."""
        context = TemplateContext(tags={"env": "production", "debug": ""})
        registry = FunctionRegistry(context)
        functions = registry.get_functions()

        assert functions["tag_exist"]("env") is True
        assert functions["tag"]("env") == "production"
        assert functions["tag_exist"]("debug") is True
        assert functions["tag"]("debug") == ""
        assert functions["tag_exist"]("missing") is False
        assert functions["tag"]("missing") == ""

    def test_tag_functions_with_uri_context(self) -> None:
        """Test tag functions work with URI context."""
        context = TemplateContext(
            uri=parse_uri("https://github.com/user/repo.git"),
            tags={"env": "dev"},
        )
        registry = FunctionRegistry(context)
        functions = registry.get_functions()

        assert functions["tag"]("env") == "dev"
        assert functions["tag_exist"]("env") is True
        assert functions["tag_exist"]("missing") is False

    def test_tag_functions_with_branch_context(self) -> None:
        """Test tag functions work with branch context."""
        context = TemplateContext(
            branch="feature/test",
            tags={"env": "test"},
        )
        registry = FunctionRegistry(context)
        functions = registry.get_functions()

        assert functions["tag"]("env") == "test"
        assert functions["tag_exist"]("env") is True

    def test_tag_functions_with_branch_context(self) -> None:
        """Test tag functions work with branch context."""
        context = TemplateContext(
            branch="main",
            tags={"env": "prod"},
        )
        registry = FunctionRegistry(context)
        functions = registry.get_functions()

        assert functions["tag"]("env") == "prod"
        assert functions["tag_exist"]("env") is True

    def test_tag_functions_with_complex_template(self) -> None:
        """Test tag functions in complex template with other functions."""
        context = TemplateContext(
            uri=parse_uri("https://github.com/org/project.git"),
            branch="feature/new-ui",
            tags={"env": "dev", "version": "1.0"},
        )

        # Use tag in path template
        result = evaluate_template(
            "~/worktrees/tag('env')/path(-1)/norm_branch()", context
        )

        assert "dev" in result
        assert "project" in result
        assert "feature-new-ui" in result

    def test_create_function_registry_includes_tag_functions(self) -> None:
        """Test that create_function_registry includes tag functions."""
        context = TemplateContext(tags={"test": "value"})
        functions = create_function_registry(context)

        assert "tag" in functions
        assert "tag_exist" in functions
        assert callable(functions["tag"])
        assert callable(functions["tag_exist"])

        assert functions["tag"]("test") == "value"
        assert functions["tag_exist"]("test") is True
        assert functions["tag_exist"]("missing") is False


class TestURIFunctions:
    """Tests for URI functions (host, port, protocol, uri) in templates."""

    def test_host_returns_hostname(self) -> None:
        """Test host() returns URI hostname."""
        context = TemplateContext(uri=parse_uri("https://github.com/user/repo.git"))
        registry = FunctionRegistry(context)
        functions = registry.get_functions()

        result = functions["host"]()

        assert result == "github.com"

    def test_host_without_uri_raises_error(self) -> None:
        """Test host() raises ValueError when no URI context."""
        context = TemplateContext()
        registry = FunctionRegistry(context)
        functions = registry.get_functions()

        with pytest.raises(ValueError, match="No URI context available"):
            functions["host"]()

    def test_port_returns_port(self) -> None:
        """Test port() returns URI port."""
        context = TemplateContext(uri=parse_uri("http://git.example.com:3000/org/repo.git"))
        registry = FunctionRegistry(context)
        functions = registry.get_functions()

        result = functions["port"]()

        assert result == "3000"

    def test_port_returns_empty_when_not_specified(self) -> None:
        """Test port() returns empty string when port not specified."""
        context = TemplateContext(uri=parse_uri("https://github.com/user/repo.git"))
        registry = FunctionRegistry(context)
        functions = registry.get_functions()

        result = functions["port"]()

        assert result == ""

    def test_protocol_returns_scheme(self) -> None:
        """Test protocol() returns URI protocol/scheme."""
        context = TemplateContext(uri=parse_uri("https://github.com/user/repo.git"))
        registry = FunctionRegistry(context)
        functions = registry.get_functions()

        result = functions["protocol"]()

        assert result == "https"

    def test_protocol_for_ssh(self) -> None:
        """Test protocol() returns ssh for SCP-style URLs."""
        context = TemplateContext(uri=parse_uri("git@github.com:user/repo.git"))
        registry = FunctionRegistry(context)
        functions = registry.get_functions()

        result = functions["protocol"]()

        assert result == "ssh"

    def test_uri_returns_full_uri(self) -> None:
        """Test uri() returns full URI string."""
        uri_str = "https://github.com/user/repo.git"
        context = TemplateContext(uri=parse_uri(uri_str))
        registry = FunctionRegistry(context)
        functions = registry.get_functions()

        result = functions["uri"]()

        assert result == uri_str

    def test_host_in_template_evaluation(self) -> None:
        """Test host() function in template evaluation."""
        context = TemplateContext(
            uri=parse_uri("https://github.com/user/repo.git"),
        )

        result = evaluate_template("~/sources/host()/path(-1)", context)

        assert "github.com" in result
        assert "repo" in result

    def test_protocol_in_template_evaluation(self) -> None:
        """Test protocol() function in template evaluation."""
        context = TemplateContext(
            uri=parse_uri("https://gitlab.com/user/repo.git"),
        )

        result = evaluate_template("~/sources/protocol()/path(-1)", context)

        assert "https" in result
        assert "repo" in result

    def test_uri_functions_combined_in_template(self) -> None:
        """Test combining URI functions in template."""
        context = TemplateContext(
            uri=parse_uri("ssh://git@myhost:3000/org/project.git"),
        )

        result = evaluate_template("~/sources/protocol()/host()/path(-1)", context)

        assert "ssh" in result
        assert "myhost" in result
        assert "project" in result


class TestPathFunction:
    """Tests for path(index) function."""

    def test_path_with_index_returns_string(self) -> None:
        """Test path(index) returns single segment string."""
        context = TemplateContext(uri=parse_uri("https://github.com/user/repo.git"))
        registry = FunctionRegistry(context)
        functions = registry.get_functions()

        result = functions["path"](-1)

        assert result == "repo"
        assert isinstance(result, str)

    def test_path_with_positive_index(self) -> None:
        """Test path() with positive index."""
        context = TemplateContext(uri=parse_uri("https://github.com/user/repo.git"))
        registry = FunctionRegistry(context)
        functions = registry.get_functions()

        assert functions["path"](0) == "user"
        assert functions["path"](1) == "repo"

    def test_path_with_negative_index(self) -> None:
        """Test path() with negative index."""
        context = TemplateContext(
            uri=parse_uri("https://gitlab.com/group/subgroup/project.git")
        )
        registry = FunctionRegistry(context)
        functions = registry.get_functions()

        assert functions["path"](-1) == "project"
        assert functions["path"](-2) == "subgroup"
        assert functions["path"](-3) == "group"

    def test_path_with_out_of_range_index_raises_error(self) -> None:
        """Test path() with out-of-range index raises ValueError."""
        context = TemplateContext(uri=parse_uri("https://github.com/user/repo.git"))
        registry = FunctionRegistry(context)
        functions = registry.get_functions()

        with pytest.raises(ValueError, match="out of range"):
            functions["path"](5)

    def test_path_without_uri_raises_error(self) -> None:
        """Test path() without URI context raises ValueError."""
        context = TemplateContext()
        registry = FunctionRegistry(context)
        functions = registry.get_functions()

        with pytest.raises(ValueError, match="No URI context available"):
            functions["path"](0)

    def test_path_in_when(self) -> None:
        """Test path(index) works in 'when' condition context."""
        context = TemplateContext(uri=parse_uri("https://github.com/myorg/repo.git"))
        functions = create_function_registry(context)

        # Simulate 'when' condition evaluation: path(0) == "myorg"
        result = functions["path"](0)

        assert result == "myorg"

    def test_path_index_in_template(self) -> None:
        """Test path(index) works in templates."""
        context = TemplateContext(
            uri=parse_uri("https://github.com/user/repo.git"),
        )

        result = evaluate_template("~/sources/path(-2)/path(-1)", context)

        assert "user" in result
        assert "repo" in result


class TestProjectFunctions:
    """Tests for project-specific functions."""

    def test_create_project_functions_returns_all_functions(self, tmp_path: Path) -> None:
        """Test create_project_functions returns all project functions."""
        functions = create_project_functions(tmp_path)

        assert "source_path" in functions
        assert "dest_path" in functions
        assert "file_exists" in functions
        assert "dir_exists" in functions
        assert "path_exists" in functions

    def test_source_path_from_source_repo_root(self, tmp_path: Path) -> None:
        """Test source_path() returns repo root when called from source repository root."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        _init_git_repo(repo_path)
        _create_initial_commit(repo_path)

        functions = create_project_functions(tmp_path)  # param not used by source_path()

        original_cwd = os.getcwd()
        try:
            os.chdir(repo_path)
            result = functions["source_path"]()
            assert result == str(repo_path.resolve())
        finally:
            os.chdir(original_cwd)

    def test_source_path_from_source_repo_subdirectory(self, tmp_path: Path) -> None:
        """Test source_path() finds repo root when called from subdirectory."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        _init_git_repo(repo_path)
        _create_initial_commit(repo_path)

        subdir = repo_path / "src" / "nested"
        subdir.mkdir(parents=True)

        functions = create_project_functions(tmp_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(subdir)
            result = functions["source_path"]()
            assert result == str(repo_path.resolve())
        finally:
            os.chdir(original_cwd)

    def test_source_path_from_worktree_root(self, tmp_path: Path) -> None:
        """Test source_path() returns worktree root when called from worktree."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        _init_git_repo(repo_path)
        _create_initial_commit(repo_path)

        worktree_path = tmp_path / "worktree"
        _add_worktree(repo_path, worktree_path, "feature-branch")

        functions = create_project_functions(tmp_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(worktree_path)
            result = functions["source_path"]()
            assert result == str(worktree_path.resolve())
        finally:
            os.chdir(original_cwd)

    def test_source_path_from_worktree_subdirectory(self, tmp_path: Path) -> None:
        """Test source_path() finds worktree root when called from worktree subdirectory."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        _init_git_repo(repo_path)
        _create_initial_commit(repo_path)

        worktree_path = tmp_path / "worktree"
        _add_worktree(repo_path, worktree_path, "feature-branch")

        subdir = worktree_path / "src" / "nested"
        subdir.mkdir(parents=True)

        functions = create_project_functions(tmp_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(subdir)
            result = functions["source_path"]()
            assert result == str(worktree_path.resolve())
        finally:
            os.chdir(original_cwd)

    def test_source_path_outside_git_repo_returns_empty_string(self, tmp_path: Path) -> None:
        """Test source_path() returns empty string when not in a git repository."""
        non_git_dir = tmp_path / "not_a_repo"
        non_git_dir.mkdir()

        functions = create_project_functions(tmp_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(non_git_dir)
            result = functions["source_path"]()
            assert result == ""
        finally:
            os.chdir(original_cwd)

    def test_source_path_returns_absolute_path(self, tmp_path: Path) -> None:
        """Test source_path() returns absolute path string."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        _init_git_repo(repo_path)
        _create_initial_commit(repo_path)

        functions = create_project_functions(tmp_path)

        original_cwd = os.getcwd()
        try:
            os.chdir(repo_path)
            result = functions["source_path"]()
            # Should be absolute path
            assert Path(result).is_absolute()
            assert result == str(repo_path.resolve())
        finally:
            os.chdir(original_cwd)

    def test_dest_path_returns_source_path_when_dest_path_not_provided(self, tmp_path: Path) -> None:
        """Test dest_path() returns source_path when dest_path parameter is None (clone context)."""
        source_path = tmp_path / "source"
        source_path.mkdir()

        functions = create_project_functions(source_path)

        result = functions["dest_path"]()

        assert result == str(source_path.resolve())

    def test_dest_path_returns_provided_path_when_set(self, tmp_path: Path) -> None:
        """Test dest_path() returns the provided path when dest_path is set (add context)."""
        source_path = tmp_path / "source"
        source_path.mkdir()
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        functions = create_project_functions(source_path, dest_path=worktree_path)

        result = functions["dest_path"]()

        assert result == str(worktree_path.resolve())

    def test_dest_path_returns_absolute_path(self, tmp_path: Path) -> None:
        """Test dest_path() returns absolute path string."""
        source_path = tmp_path / "source"
        source_path.mkdir()
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        functions = create_project_functions(source_path, dest_path=worktree_path)

        result = functions["dest_path"]()

        assert Path(result).is_absolute()
        assert result == str(worktree_path.resolve())

    def test_dest_path_clone_context(self, tmp_path: Path) -> None:
        """Test dest_path() in clone context (dest_path equals source_path)."""
        source_path = tmp_path / "clone_target"
        source_path.mkdir()

        # In clone context, dest_path is set to the same as source_path
        functions = create_project_functions(source_path, dest_path=source_path)

        result = functions["dest_path"]()

        assert result == str(source_path.resolve())

    def test_dest_path_add_context(self, tmp_path: Path) -> None:
        """Test dest_path() in add context (dest_path is worktree path)."""
        source_path = tmp_path / "source_repo"
        source_path.mkdir()
        worktree_path = tmp_path / "worktrees" / "feature-branch"
        worktree_path.mkdir(parents=True)

        # In add context, dest_path is the worktree path
        functions = create_project_functions(source_path, dest_path=worktree_path)

        result = functions["dest_path"]()

        assert result == str(worktree_path.resolve())
        # Verify it's different from source_path
        assert result != str(source_path.resolve())

    def test_file_exists_returns_true_for_existing_file(self, tmp_path: Path) -> None:
        """Test file_exists() returns True for existing file."""
        test_file = tmp_path / "package.json"
        test_file.touch()

        functions = create_project_functions(tmp_path)

        assert functions["file_exists"]("package.json") is True

    def test_file_exists_returns_false_for_missing_file(self, tmp_path: Path) -> None:
        """Test file_exists() returns False for missing file."""
        functions = create_project_functions(tmp_path)

        assert functions["file_exists"]("nonexistent.txt") is False

    def test_file_exists_returns_false_for_directory(self, tmp_path: Path) -> None:
        """Test file_exists() returns False for directory."""
        test_dir = tmp_path / "src"
        test_dir.mkdir()

        functions = create_project_functions(tmp_path)

        assert functions["file_exists"]("src") is False

    def test_dir_exists_returns_true_for_existing_directory(self, tmp_path: Path) -> None:
        """Test dir_exists() returns True for existing directory."""
        test_dir = tmp_path / "src"
        test_dir.mkdir()

        functions = create_project_functions(tmp_path)

        assert functions["dir_exists"]("src") is True

    def test_dir_exists_returns_false_for_missing_directory(self, tmp_path: Path) -> None:
        """Test dir_exists() returns False for missing directory."""
        functions = create_project_functions(tmp_path)

        assert functions["dir_exists"]("nonexistent") is False

    def test_dir_exists_returns_false_for_file(self, tmp_path: Path) -> None:
        """Test dir_exists() returns False for file."""
        test_file = tmp_path / "package.json"
        test_file.touch()

        functions = create_project_functions(tmp_path)

        assert functions["dir_exists"]("package.json") is False

    def test_path_exists_returns_true_for_file(self, tmp_path: Path) -> None:
        """Test path_exists() returns True for existing file."""
        test_file = tmp_path / "package.json"
        test_file.touch()

        functions = create_project_functions(tmp_path)

        assert functions["path_exists"]("package.json") is True

    def test_path_exists_returns_true_for_directory(self, tmp_path: Path) -> None:
        """Test path_exists() returns True for existing directory."""
        test_dir = tmp_path / "src"
        test_dir.mkdir()

        functions = create_project_functions(tmp_path)

        assert functions["path_exists"]("src") is True

    def test_path_exists_returns_false_for_missing_path(self, tmp_path: Path) -> None:
        """Test path_exists() returns False for missing path."""
        functions = create_project_functions(tmp_path)

        assert functions["path_exists"]("nonexistent") is False


class TestFunctionRegistryContainsAllFunctions:
    """Tests verifying the function registry contains expected functions."""

    def test_registry_contains_uri_functions(self) -> None:
        """Test registry includes all URI functions."""
        context = TemplateContext(uri=parse_uri("https://github.com/user/repo.git"))
        functions = create_function_registry(context)

        assert "host" in functions
        assert "port" in functions
        assert "protocol" in functions
        assert "uri" in functions
        assert "path" in functions

    def test_registry_contains_branch_functions(self) -> None:
        """Test registry includes all branch functions."""
        context = TemplateContext(branch="feature/test")
        functions = create_function_registry(context)

        assert "branch" in functions
        assert "norm_branch" in functions

    def test_registry_contains_tag_functions(self) -> None:
        """Test registry includes all tag functions."""
        context = TemplateContext(tags={"env": "prod"})
        functions = create_function_registry(context)

        assert "tag" in functions
        assert "tag_exist" in functions
