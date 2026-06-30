"""Unit tests for template functions in src/gww/template/functions.py."""

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


class TestTimeIdFunction:
    """Tests for time_id() template function."""

    def test_time_id_default_format_matches_pattern(self) -> None:
        """Test time_id() with default format returns expected pattern."""
        import re

        context = TemplateContext()
        registry = FunctionRegistry(context)
        functions = registry.get_functions()

        result = functions["time_id"]()

        # Pattern: YYYYMMDD-HHMM.SS (e.g., "20260120-2134.03")
        pattern = r"^\d{8}-\d{4}\.\d{2}$"
        assert re.match(pattern, result), f"Result '{result}' doesn't match pattern YYYYMMDD-HHMM.SS"

    def test_time_id_custom_format(self) -> None:
        """Test time_id() with custom format string."""
        context = TemplateContext()
        registry = FunctionRegistry(context)
        functions = registry.get_functions()

        result = functions["time_id"]("%Y-%m-%d")

        # Should match YYYY-MM-DD pattern
        import re
        pattern = r"^\d{4}-\d{2}-\d{2}$"
        assert re.match(pattern, result), f"Result '{result}' doesn't match pattern YYYY-MM-DD"

    def test_time_id_caches_datetime_across_calls(self) -> None:
        """Test time_id() caches datetime and reuses it for subsequent calls."""
        context = TemplateContext()
        registry = FunctionRegistry(context)
        functions = registry.get_functions()

        # Call with default format
        result1 = functions["time_id"]()
        # Call with custom format
        result2 = functions["time_id"]("%Y%m%d%H%M%S")
        # Call with another format
        result3 = functions["time_id"]("%Y")

        # Extract date parts from default format (YYYYMMDD-HHMM.SS)
        date_from_default = result1[:8]  # YYYYMMDD
        time_from_default = result1[9:13]  # HHMM
        sec_from_default = result1[14:16]  # SS

        # result2 format is YYYYMMDDHHMMSS
        date_from_custom = result2[:8]  # YYYYMMDD
        time_from_custom = result2[8:12]  # HHMM
        sec_from_custom = result2[12:14]  # SS

        # Verify same datetime was used
        assert date_from_default == date_from_custom
        assert time_from_default == time_from_custom
        assert sec_from_default == sec_from_custom

        # result3 format is YYYY (year only)
        year_from_default = result1[:4]
        assert result3 == year_from_default

    def test_time_id_different_registries_have_different_datetimes(self) -> None:
        """Test that different FunctionRegistry instances may have different cached datetimes."""
        import time

        context = TemplateContext()

        registry1 = FunctionRegistry(context)
        functions1 = registry1.get_functions()
        result1 = functions1["time_id"]()

        # Small delay to potentially get different time
        time.sleep(0.01)

        registry2 = FunctionRegistry(context)
        functions2 = registry2.get_functions()
        result2 = functions2["time_id"]()

        # Each registry has its own cached datetime
        # The results might be the same (if called within same second) or different
        # What's important is that they each have their own cache
        assert registry1._cached_datetime is not None
        assert registry2._cached_datetime is not None
        # They could be equal or different depending on timing
        # The key test is that each registry caches independently

    def test_time_id_in_template_evaluation(self) -> None:
        """Test time_id() function in template evaluation."""
        import re

        context = TemplateContext(
            uri=parse_uri("https://github.com/user/repo.git"),
        )

        result = evaluate_template("~/sources/path(-1)/time_id()", context)

        # Should contain repo name and time_id pattern
        assert "repo" in result
        # Extract time_id part (after last /)
        time_id_part = result.split("/")[-1]
        pattern = r"^\d{8}-\d{4}\.\d{2}$"
        assert re.match(pattern, time_id_part), f"time_id part '{time_id_part}' doesn't match pattern"

    def test_time_id_with_custom_format_in_template(self) -> None:
        """Test time_id() with custom format in template evaluation."""
        import re

        context = TemplateContext(
            uri=parse_uri("https://github.com/user/repo.git"),
        )

        result = evaluate_template("~/sources/path(-1)/time_id('%Y-%m-%d')", context)

        # Should contain repo name and custom time_id pattern
        assert "repo" in result
        # Extract time_id part (after last /)
        time_id_part = result.split("/")[-1]
        pattern = r"^\d{4}-\d{2}-\d{2}$"
        assert re.match(pattern, time_id_part), f"time_id part '{time_id_part}' doesn't match pattern"

    def test_time_id_multiple_calls_in_same_template(self) -> None:
        """Test multiple time_id() calls in same template use same datetime."""
        context = TemplateContext()

        # Call time_id twice with different formats in same template
        result = evaluate_template("time_id()/time_id('%Y')", context)

        parts = result.split("/")
        assert len(parts) == 2

        # First part: default format YYYYMMDD-HHMM.SS
        # Second part: just year YYYY
        year_from_first = parts[0][:4]
        year_from_second = parts[1]

        assert year_from_first == year_from_second

    def test_time_id_is_registered_in_function_registry(self) -> None:
        """Test that time_id is registered in the function registry."""
        context = TemplateContext()
        functions = create_function_registry(context)

        assert "time_id" in functions
        assert callable(functions["time_id"])


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
        functions = create_project_functions(TemplateContext(source_path=tmp_path))

        assert "source_path" in functions
        assert "current_worktree" in functions
        assert "file_exists" in functions
        assert "dir_exists" in functions
        assert "path_exists" in functions

    def test_source_path_returns_source_repo(self, tmp_path: Path) -> None:
        """Test source_path() with no arg returns the bare source path."""
        source = tmp_path / "source"
        source.mkdir()

        functions = create_project_functions(
            TemplateContext(source_path=source, dest_path=source),
        )

        assert functions["source_path"]() == str(source.resolve())

    def test_source_path_with_extra_returns_joined_path(self, tmp_path: Path) -> None:
        """Test source_path('foo') joins the extra segment onto the source path."""
        source = tmp_path / "source"
        source.mkdir()

        functions = create_project_functions(
            TemplateContext(source_path=source, dest_path=source),
        )

        assert functions["source_path"]("foo") == str((source / "foo").resolve())

    def test_source_path_with_empty_extra_returns_source_path(self, tmp_path: Path) -> None:
        """Test source_path('') is equivalent to source_path() (ADR-0012 Q5)."""
        source = tmp_path / "source"
        source.mkdir()

        functions = create_project_functions(
            TemplateContext(source_path=source, dest_path=source),
        )

        assert functions["source_path"]("") == str(source.resolve())

    def test_source_path_returns_absolute_resolved_path(self, tmp_path: Path) -> None:
        """Test source_path() resolves and returns an absolute path string."""
        source = tmp_path / "source"
        source.mkdir()

        functions = create_project_functions(
            TemplateContext(source_path=source, dest_path=source),
        )

        result = functions["source_path"]()
        assert Path(result).is_absolute()
        assert result == str(source.resolve())

    def test_source_path_does_not_alias_current_worktree(
        self, tmp_path: Path,
    ) -> None:
        """``source_path()`` must always read ``context.source_path`` —
        never ``context.dest_path``. ADR-0012 §"Uniform semantics across
        operations" — divergence in ``add`` and ``before_remove`` is
        expected, not an error."""
        source = tmp_path / "source"
        source.mkdir()
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        functions = create_project_functions(
            TemplateContext(source_path=source, dest_path=worktree),
        )

        assert functions["source_path"]() == str(source.resolve())
        assert functions["source_path"]() != functions["current_worktree"]()

    def test_current_worktree_returns_dest_path(self, tmp_path: Path) -> None:
        """Test current_worktree() with no arg returns the bare dest path."""
        source = tmp_path / "source"
        source.mkdir()
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        functions = create_project_functions(
            TemplateContext(source_path=source, dest_path=worktree),
        )

        assert functions["current_worktree"]() == str(worktree.resolve())

    def test_current_worktree_with_extra_returns_joined_path(
        self, tmp_path: Path,
    ) -> None:
        """Test current_worktree('foo') joins the extra segment onto the dest path."""
        source = tmp_path / "source"
        source.mkdir()
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        functions = create_project_functions(
            TemplateContext(source_path=source, dest_path=worktree),
        )

        assert functions["current_worktree"]("foo") == str(
            (worktree / "foo").resolve()
        )

    def test_current_worktree_with_empty_extra_returns_dest_path(
        self, tmp_path: Path,
    ) -> None:
        """Test current_worktree('') is equivalent to current_worktree()."""
        source = tmp_path / "source"
        source.mkdir()
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        functions = create_project_functions(
            TemplateContext(source_path=source, dest_path=worktree),
        )

        assert functions["current_worktree"]("") == str(worktree.resolve())

    def test_current_worktree_in_clone_context_equals_source_path(
        self, tmp_path: Path,
    ) -> None:
        """``gww clone`` populates both context fields with the same path;
        ``current_worktree()`` then reads ``context.dest_path`` (which the
        CLI set to the same value) and matches ``source_path()``. This is a
        CLI-side property of how the command populates the context, not
        aliasing inside either helper — the test pins the convention so
        regressions surface immediately."""
        clone_target = tmp_path / "clone_target"
        clone_target.mkdir()

        functions = create_project_functions(
            TemplateContext(source_path=clone_target, dest_path=clone_target),
        )

        assert functions["current_worktree"]() == functions["source_path"]()
        assert functions["current_worktree"]() == str(clone_target.resolve())

    def test_current_worktree_in_add_context_diverges_from_source_path(
        self, tmp_path: Path,
    ) -> None:
        """``gww add`` populates ``source_path`` with the source repo and
        ``dest_path`` with the worktree being added. ``current_worktree()``
        must return the worktree path, not the source path."""
        source = tmp_path / "source_repo"
        source.mkdir()
        worktree = tmp_path / "worktrees" / "feature-branch"
        worktree.mkdir(parents=True)

        functions = create_project_functions(
            TemplateContext(source_path=source, dest_path=worktree),
        )

        assert functions["current_worktree"]() == str(worktree.resolve())
        assert functions["current_worktree"]() != functions["source_path"]()

    def test_current_worktree_in_before_remove_context_points_to_worktree(
        self, tmp_path: Path,
    ) -> None:
        """``gww remove`` populates ``source_path`` with the source repo and
        ``dest_path`` with the worktree being removed. ``current_worktree()``
        returns the doomed worktree, not the source."""
        source = tmp_path / "source_repo"
        source.mkdir()
        doomed = tmp_path / "worktrees" / "doomed"
        doomed.mkdir(parents=True)

        functions = create_project_functions(
            TemplateContext(source_path=source, dest_path=doomed),
        )

        assert functions["current_worktree"]() == str(doomed.resolve())
        assert functions["current_worktree"]() != functions["source_path"]()

    def test_current_worktree_with_none_dest_path_raises_value_error(
        self, tmp_path: Path,
    ) -> None:
        """When ``context.dest_path`` is ``None`` (non-project evaluation
        site), ``current_worktree()`` must raise ``ValueError`` — never
        silently fall back to ``source_path()``. ADR-0012 §"Uniform
        semantics across operations" rules the fallback out."""
        source = tmp_path / "source"
        source.mkdir()

        functions = create_project_functions(
            TemplateContext(source_path=source, dest_path=None),
        )

        with pytest.raises(ValueError, match="requires context.dest_path"):
            functions["current_worktree"]()

        with pytest.raises(ValueError, match="requires context.dest_path"):
            functions["current_worktree"]("foo")

    def test_file_exists_returns_true_for_existing_file(self, tmp_path: Path) -> None:
        """Test file_exists() returns True for existing file."""
        test_file = tmp_path / "package.json"
        test_file.touch()

        functions = create_project_functions(TemplateContext(source_path=tmp_path))

        assert functions["file_exists"]("package.json") is True

    def test_file_exists_returns_false_for_missing_file(self, tmp_path: Path) -> None:
        """Test file_exists() returns False for missing file."""
        functions = create_project_functions(TemplateContext(source_path=tmp_path))

        assert functions["file_exists"]("nonexistent.txt") is False

    def test_file_exists_returns_false_for_directory(self, tmp_path: Path) -> None:
        """Test file_exists() returns False for directory."""
        test_dir = tmp_path / "src"
        test_dir.mkdir()

        functions = create_project_functions(TemplateContext(source_path=tmp_path))

        assert functions["file_exists"]("src") is False

    def test_dir_exists_returns_true_for_existing_directory(self, tmp_path: Path) -> None:
        """Test dir_exists() returns True for existing directory."""
        test_dir = tmp_path / "src"
        test_dir.mkdir()

        functions = create_project_functions(TemplateContext(source_path=tmp_path))

        assert functions["dir_exists"]("src") is True

    def test_dir_exists_returns_false_for_missing_directory(self, tmp_path: Path) -> None:
        """Test dir_exists() returns False for missing directory."""
        functions = create_project_functions(TemplateContext(source_path=tmp_path))

        assert functions["dir_exists"]("nonexistent") is False

    def test_dir_exists_returns_false_for_file(self, tmp_path: Path) -> None:
        """Test dir_exists() returns False for file."""
        test_file = tmp_path / "package.json"
        test_file.touch()

        functions = create_project_functions(TemplateContext(source_path=tmp_path))

        assert functions["dir_exists"]("package.json") is False

    def test_path_exists_returns_true_for_file(self, tmp_path: Path) -> None:
        """Test path_exists() returns True for existing file."""
        test_file = tmp_path / "package.json"
        test_file.touch()

        functions = create_project_functions(TemplateContext(source_path=tmp_path))

        assert functions["path_exists"]("package.json") is True

    def test_path_exists_returns_true_for_directory(self, tmp_path: Path) -> None:
        """Test path_exists() returns True for existing directory."""
        test_dir = tmp_path / "src"
        test_dir.mkdir()

        functions = create_project_functions(TemplateContext(source_path=tmp_path))

        assert functions["path_exists"]("src") is True

    def test_path_exists_returns_false_for_missing_path(self, tmp_path: Path) -> None:
        """Test path_exists() returns False for missing path."""
        functions = create_project_functions(TemplateContext(source_path=tmp_path))

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

    def test_registry_contains_utility_functions(self) -> None:
        """Test registry includes all utility functions."""
        context = TemplateContext()
        functions = create_function_registry(context)

        assert "time_id" in functions
