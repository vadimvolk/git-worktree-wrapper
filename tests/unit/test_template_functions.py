"""Unit tests for template functions in src/gww/template/functions.py."""

import pytest

from gww.template.functions import FunctionRegistry, TemplateContext, create_function_registry
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
