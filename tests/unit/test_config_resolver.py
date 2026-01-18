"""Unit tests for configuration resolver in src/gww/config/resolver.py."""

import pytest
from pathlib import Path
from unittest.mock import patch

from gww.config.resolver import (
    ResolverError,
    find_matching_source_rule,
    resolve_source_path,
    resolve_worktree_path,
    get_source_path_for_worktree,
)
from gww.config.validator import Config, SourceRule
from gww.utils.uri import parse_uri


class TestFindMatchingSourceRule:
    """Tests for find_matching_source_rule function."""

    def test_matches_github_predicate(self) -> None:
        """Test matching GitHub predicate with 'github' in host."""
        github_rule = SourceRule(
            name="github",
            predicate='"github" in host()',
            sources="~/sources/github/path(-2)/path(-1)",
        )
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default",
            sources={"github": github_rule},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = find_matching_source_rule(config, uri)

        assert result is not None
        assert result.name == "github"

    def test_matches_gitlab_predicate(self) -> None:
        """Test matching GitLab predicate."""
        gitlab_rule = SourceRule(
            name="gitlab",
            predicate='"gitlab" in host()',
            sources="~/sources/gitlab/path(-2)/path(-1)",
        )
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default",
            sources={"gitlab": gitlab_rule},
        )
        uri = parse_uri("https://gitlab.com/group/project.git")

        result = find_matching_source_rule(config, uri)

        assert result is not None
        assert result.name == "gitlab"

    def test_no_match_returns_none(self) -> None:
        """Test that no match returns None."""
        github_rule = SourceRule(
            name="github",
            predicate='"github" in host()',
        )
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default",
            sources={"github": github_rule},
        )
        uri = parse_uri("https://example.com/user/repo.git")

        result = find_matching_source_rule(config, uri)

        assert result is None

    def test_first_match_wins(self) -> None:
        """Test that first matching rule wins."""
        rule1 = SourceRule(name="rule1", predicate="True")
        rule2 = SourceRule(name="rule2", predicate="True")
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default",
            sources={"rule1": rule1, "rule2": rule2},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = find_matching_source_rule(config, uri)

        assert result is not None
        assert result.name == "rule1"

    def test_empty_sources_returns_none(self) -> None:
        """Test that empty sources dict returns None."""
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default",
            sources={},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = find_matching_source_rule(config, uri)

        assert result is None

    def test_predicate_with_path_access(self) -> None:
        """Test predicate that accesses path segments."""
        rule = SourceRule(
            name="myorg",
            predicate='path()[0] == "myorg"',
        )
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default",
            sources={"myorg": rule},
        )
        uri = parse_uri("https://git.example.com/myorg/project.git")

        result = find_matching_source_rule(config, uri)

        assert result is not None
        assert result.name == "myorg"

    def test_predicate_with_protocol_check(self) -> None:
        """Test predicate that checks protocol."""
        rule = SourceRule(
            name="ssh",
            predicate='protocol() == "ssh"',
        )
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default",
            sources={"ssh": rule},
        )
        uri = parse_uri("git@github.com:user/repo.git")

        result = find_matching_source_rule(config, uri)

        assert result is not None
        assert result.name == "ssh"

    def test_predicate_with_port_check(self) -> None:
        """Test predicate that checks port."""
        rule = SourceRule(
            name="custom",
            predicate='port() == "3000"',
        )
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default",
            sources={"custom": rule},
        )
        uri = parse_uri("http://git.example.com:3000/org/repo.git")

        result = find_matching_source_rule(config, uri)

        assert result is not None
        assert result.name == "custom"

    def test_invalid_predicate_raises_resolver_error(self) -> None:
        """Test that invalid predicate raises ResolverError."""
        rule = SourceRule(
            name="invalid",
            predicate="undefined_variable",
        )
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default",
            sources={"invalid": rule},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        with pytest.raises(ResolverError, match="Error evaluating predicate"):
            find_matching_source_rule(config, uri)

    def test_not_in_predicate_forms(self) -> None:
        """Test that both 'not "github" in host' and '"github" not in host' work correctly."""
        # Test with 'not "github" in host' form
        non_github_rule1 = SourceRule(
            name="non_github1",
            predicate='not "github" in host()',
        )
        # Test with '"github" not in host' form
        non_github_rule2 = SourceRule(
            name="non_github2",
            predicate='"github" not in host()',
        )
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default",
            sources={
                "non_github1": non_github_rule1,
                "non_github2": non_github_rule2,
            },
        )

        # Test with GitHub URI - should NOT match either rule
        github_uri = parse_uri("https://github.com/user/repo.git")
        result1 = find_matching_source_rule(config, github_uri)
        # Since "github" IS in host, both predicates should be False
        assert result1 is None

        # Test with non-GitHub URI - should match both rules
        non_github_uri = parse_uri("https://gitlab.com/user/repo.git")
        result2 = find_matching_source_rule(config, non_github_uri)
        assert result2 is not None
        assert result2.name == "non_github1"  # First matching rule wins

        # Test second form separately
        config2 = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default",
            sources={"non_github2": non_github_rule2},
        )
        result3 = find_matching_source_rule(config2, non_github_uri)
        assert result3 is not None
        assert result3.name == "non_github2"

    def test_matches_with_tag_exist_predicate(self) -> None:
        """Test matching source rule with tag_exist() predicate."""
        rule = SourceRule(
            name="tagged",
            predicate='tag_exist("env")',
        )
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default",
            sources={"tagged": rule},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = find_matching_source_rule(config, uri, tags={"env": "production"})

        assert result is not None
        assert result.name == "tagged"

    def test_no_match_when_tag_not_exists(self) -> None:
        """Test no match when tag_exist() returns False."""
        rule = SourceRule(
            name="tagged",
            predicate='tag_exist("env")',
        )
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default",
            sources={"tagged": rule},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = find_matching_source_rule(config, uri, tags={"other": "value"})

        assert result is None

    def test_matches_with_tag_value_predicate(self) -> None:
        """Test matching source rule with tag() value comparison."""
        rule = SourceRule(
            name="production",
            predicate='tag("env") == "production"',
        )
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default",
            sources={"production": rule},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = find_matching_source_rule(config, uri, tags={"env": "production"})

        assert result is not None
        assert result.name == "production"

    def test_no_match_with_different_tag_value(self) -> None:
        """Test no match when tag value doesn't match predicate."""
        rule = SourceRule(
            name="production",
            predicate='tag("env") == "production"',
        )
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default",
            sources={"production": rule},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = find_matching_source_rule(config, uri, tags={"env": "development"})

        assert result is None

    def test_tag_returns_empty_string_when_not_exists(self) -> None:
        """Test tag() returns empty string when tag doesn't exist."""
        rule = SourceRule(
            name="empty",
            predicate='tag("missing") == ""',
        )
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default",
            sources={"empty": rule},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = find_matching_source_rule(config, uri, tags={})

        assert result is not None
        assert result.name == "empty"

    def test_tag_exist_with_empty_value(self) -> None:
        """Test tag_exist() returns True even when tag has empty value."""
        rule = SourceRule(
            name="flagged",
            predicate='tag_exist("flag")',
        )
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default",
            sources={"flagged": rule},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = find_matching_source_rule(config, uri, tags={"flag": ""})

        assert result is not None
        assert result.name == "flagged"

    def test_tag_with_empty_value_in_predicate(self) -> None:
        """Test tag() with empty value in predicate."""
        rule = SourceRule(
            name="empty_flag",
            predicate='tag("flag") == ""',
        )
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default",
            sources={"empty_flag": rule},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = find_matching_source_rule(config, uri, tags={"flag": ""})

        assert result is not None
        assert result.name == "empty_flag"

    def test_tag_functions_with_uri_and_tag_predicate(self) -> None:
        """Test tag functions combined with URI predicates."""
        rule = SourceRule(
            name="github_prod",
            predicate='"github" in host() and tag("env") == "production"',
        )
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default",
            sources={"github_prod": rule},
        )
        github_uri = parse_uri("https://github.com/user/repo.git")

        # Should match with production tag
        result1 = find_matching_source_rule(
            config, github_uri, tags={"env": "production"}
        )
        assert result1 is not None
        assert result1.name == "github_prod"

        # Should not match with development tag
        result2 = find_matching_source_rule(
            config, github_uri, tags={"env": "development"}
        )
        assert result2 is None

        # Should not match non-GitHub URI even with production tag
        gitlab_uri = parse_uri("https://gitlab.com/user/repo.git")
        result3 = find_matching_source_rule(
            config, gitlab_uri, tags={"env": "production"}
        )
        assert result3 is None

    def test_multiple_tags_in_predicate(self) -> None:
        """Test using multiple tags in predicate."""
        rule = SourceRule(
            name="multi_tag",
            predicate='tag_exist("env") and tag("env") == "production" and tag_exist("version")',
        )
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default",
            sources={"multi_tag": rule},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = find_matching_source_rule(
            config, uri, tags={"env": "production", "version": "1.0"}
        )

        assert result is not None
        assert result.name == "multi_tag"

    def test_tag_functions_with_complex_predicate(self) -> None:
        """Test tag functions in complex predicate with logical operators."""
        rule = SourceRule(
            name="complex",
            predicate='tag_exist("env") and (tag("env") == "production" or tag("env") == "staging")',
        )
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default",
            sources={"complex": rule},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        # Test with production
        result1 = find_matching_source_rule(config, uri, tags={"env": "production"})
        assert result1 is not None
        assert result1.name == "complex"

        # Test with staging
        result2 = find_matching_source_rule(config, uri, tags={"env": "staging"})
        assert result2 is not None
        assert result2.name == "complex"

        # Test with development (should not match)
        result3 = find_matching_source_rule(config, uri, tags={"env": "development"})
        assert result3 is None

    def test_tag_functions_with_no_tags_provided(self) -> None:
        """Test tag functions when no tags are provided."""
        rule = SourceRule(
            name="tagged",
            predicate='tag_exist("env")',
        )
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default",
            sources={"tagged": rule},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = find_matching_source_rule(config, uri)

        assert result is None

    def test_tag_functions_with_partial_tags(self) -> None:
        """Test tag functions when only some tags are provided."""
        rule1 = SourceRule(
            name="env_rule",
            predicate='tag_exist("env")',
        )
        rule2 = SourceRule(
            name="version_rule",
            predicate='tag_exist("version")',
        )
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default",
            sources={"env_rule": rule1, "version_rule": rule2},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = find_matching_source_rule(config, uri, tags={"env": "production"})

        assert result is not None
        assert result.name == "env_rule"


class TestResolveSourcePath:
    """Tests for resolve_source_path function."""

    def test_uses_default_when_no_match(self) -> None:
        """Test that default_sources is used when no rule matches."""
        config = Config(
            default_sources="~/sources/default/path(-2)/path(-1)",
            default_worktrees="~/worktrees/default",
            sources={},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = resolve_source_path(config, uri)

        assert result.name == "repo"
        assert "user" in str(result)

    def test_uses_matching_rule_sources(self) -> None:
        """Test that matching rule's sources template is used."""
        github_rule = SourceRule(
            name="github",
            predicate='"github" in host()',
            sources="~/sources/github/path(-2)/path(-1)",
        )
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default",
            sources={"github": github_rule},
        )
        uri = parse_uri("https://github.com/vadimvolk/ansible.git")

        result = resolve_source_path(config, uri)

        assert "github" in str(result)
        assert "vadimvolk" in str(result)
        assert "ansible" in str(result)

    def test_uses_default_when_rule_has_no_sources(self) -> None:
        """Test fallback to default when rule has no sources template."""
        rule = SourceRule(
            name="github",
            predicate='"github" in host()',
            sources=None,  # No sources template
        )
        config = Config(
            default_sources="~/sources/default/path(-1)",
            default_worktrees="~/worktrees/default",
            sources={"github": rule},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = resolve_source_path(config, uri)

        assert "default" in str(result)

    def test_path_is_absolute(self) -> None:
        """Test that resolved path is absolute."""
        config = Config(
            default_sources="~/sources/default/path(-1)",
            default_worktrees="~/worktrees/default",
            sources={},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = resolve_source_path(config, uri)

        assert result.is_absolute()

    def test_expands_tilde(self) -> None:
        """Test that ~ is expanded to home directory."""
        config = Config(
            default_sources="~/sources/default/path(-1)",
            default_worktrees="~/worktrees/default",
            sources={},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = resolve_source_path(config, uri)

        assert "~" not in str(result)

    def test_invalid_template_raises_resolver_error(self) -> None:
        """Test that invalid template raises ResolverError."""
        config = Config(
            default_sources="~/sources/path(999)",  # Out of range
            default_worktrees="~/worktrees/default",
            sources={},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        with pytest.raises(ResolverError, match="Error evaluating source path"):
            resolve_source_path(config, uri)


class TestResolveWorktreePath:
    """Tests for resolve_worktree_path function."""

    def test_resolves_worktree_path_with_branch(self) -> None:
        """Test resolving worktree path with branch."""
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default/path(-1)/norm_branch()",
            sources={},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = resolve_worktree_path(config, uri, "feature/new-ui")

        assert "repo" in str(result)
        assert "feature-new-ui" in str(result)

    def test_uses_matching_rule_worktrees(self) -> None:
        """Test that matching rule's worktrees template is used."""
        github_rule = SourceRule(
            name="github",
            predicate='"github" in host()',
            sources="~/sources/github",
            worktrees="~/worktrees/github/path(-2)/path(-1)/branch()",
        )
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default",
            sources={"github": github_rule},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = resolve_worktree_path(config, uri, "main")

        assert "github" in str(result)
        assert "user" in str(result)
        assert "repo" in str(result)
        assert "main" in str(result)

    def test_uses_default_when_rule_has_no_worktrees(self) -> None:
        """Test fallback to default when rule has no worktrees template."""
        rule = SourceRule(
            name="github",
            predicate='"github" in host()',
            sources="~/sources/github",
            worktrees=None,
        )
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default/norm_branch()",
            sources={"github": rule},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = resolve_worktree_path(config, uri, "feature/test")

        assert "default" in str(result)
        assert "feature-test" in str(result)

    def test_norm_branch_with_custom_separator(self) -> None:
        """Test norm_branch() with custom separator."""
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default/norm_branch('_')",
            sources={},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = resolve_worktree_path(config, uri, "feature/new/ui")

        assert "feature_new_ui" in str(result)


class TestGetSourcePathForWorktree:
    """Tests for get_source_path_for_worktree function."""

    def test_returns_same_as_resolve_source_path(self) -> None:
        """Test that get_source_path_for_worktree returns same as resolve_source_path."""
        config = Config(
            default_sources="~/sources/default/path(-2)/path(-1)",
            default_worktrees="~/worktrees/default",
            sources={},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result1 = get_source_path_for_worktree(config, uri)
        result2 = resolve_source_path(config, uri)

        assert result1 == result2


class TestMigrationPathCalculation:
    """Tests for migration path calculation (T055)."""

    def test_calculates_new_path_for_github(self) -> None:
        """Test calculating new path for GitHub repository."""
        github_rule = SourceRule(
            name="github",
            predicate='"github" in host()',
            sources="~/sources/github/path(-2)/path(-1)",
        )
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default",
            sources={"github": github_rule},
        )
        uri = parse_uri("https://github.com/org/project.git")

        result = resolve_source_path(config, uri)

        assert "github" in str(result)
        assert "org" in str(result)
        assert "project" in str(result)

    def test_calculates_new_path_for_gitlab_nested(self) -> None:
        """Test calculating new path for GitLab with nested groups."""
        gitlab_rule = SourceRule(
            name="gitlab",
            predicate='"gitlab" in host()',
            sources="~/sources/gitlab/path(-3)/path(-2)/path(-1)",
        )
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default",
            sources={"gitlab": gitlab_rule},
        )
        uri = parse_uri("https://gitlab.com/group/subgroup/project.git")

        result = resolve_source_path(config, uri)

        assert "gitlab" in str(result)
        assert "group" in str(result)
        assert "subgroup" in str(result)
        assert "project" in str(result)

    def test_uses_default_for_unknown_host(self) -> None:
        """Test that default path is used for unknown hosts."""
        github_rule = SourceRule(
            name="github",
            predicate='"github" in host()',
            sources="~/sources/github/path(-1)",
        )
        config = Config(
            default_sources="~/sources/default/path(-2)/path(-1)",
            default_worktrees="~/worktrees/default",
            sources={"github": github_rule},
        )
        uri = parse_uri("https://custom.example.com/myorg/myproject.git")

        result = resolve_source_path(config, uri)

        assert "default" in str(result)
        assert "myorg" in str(result)
        assert "myproject" in str(result)

    def test_resolve_source_path_with_tag_in_template(self) -> None:
        """Test resolve_source_path with tag() function in template."""
        config = Config(
            default_sources="~/sources/tag('env')/path(-2)/path(-1)",
            default_worktrees="~/worktrees/default",
            sources={},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = resolve_source_path(config, uri, tags={"env": "production"})

        assert "production" in str(result)
        assert "user" in str(result)
        assert "repo" in str(result)

    def test_resolve_source_path_with_tag_in_rule_template(self) -> None:
        """Test resolve_source_path with tag() in rule's sources template."""
        rule = SourceRule(
            name="github",
            predicate='"github" in host()',
            sources="~/sources/tag('env')/github/path(-2)/path(-1)",
        )
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default",
            sources={"github": rule},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = resolve_source_path(config, uri, tags={"env": "dev"})

        assert "dev" in str(result)
        assert "github" in str(result)
        assert "user" in str(result)
        assert "repo" in str(result)

    def test_resolve_source_path_with_multiple_tags_in_template(self) -> None:
        """Test resolve_source_path with multiple tag() functions in template."""
        config = Config(
            default_sources="~/sources/tag('env')/tag('version')/path(-1)",
            default_worktrees="~/worktrees/default",
            sources={},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = resolve_source_path(
            config, uri, tags={"env": "production", "version": "1.0"}
        )

        assert "production" in str(result)
        assert "1.0" in str(result)
        assert "repo" in str(result)

    def test_resolve_source_path_with_missing_tag_in_template(self) -> None:
        """Test resolve_source_path with missing tag() returns empty string."""
        config = Config(
            default_sources="~/sources/tag('missing')/path(-1)",
            default_worktrees="~/worktrees/default",
            sources={},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = resolve_source_path(config, uri, tags={})

        # Should still work, tag('missing') returns empty string
        assert "repo" in str(result)

    def test_resolve_worktree_path_with_tag_in_template(self) -> None:
        """Test resolve_worktree_path with tag() function in template."""
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/tag('env')/path(-1)/norm_branch()",
            sources={},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = resolve_worktree_path(
            config, uri, "feature/test", tags={"env": "production"}
        )

        assert "production" in str(result)
        assert "repo" in str(result)
        assert "feature-test" in str(result)

    def test_resolve_worktree_path_with_tag_in_rule_template(self) -> None:
        """Test resolve_worktree_path with tag() in rule's worktrees template."""
        rule = SourceRule(
            name="github",
            predicate='"github" in host()',
            sources="~/sources/github",
            worktrees="~/worktrees/tag('env')/github/path(-1)/norm_branch()",
        )
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default",
            sources={"github": rule},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = resolve_worktree_path(
            config, uri, "feature/new-ui", tags={"env": "dev"}
        )

        assert "dev" in str(result)
        assert "github" in str(result)
        assert "repo" in str(result)
        assert "feature-new-ui" in str(result)

    def test_resolve_worktree_path_with_multiple_tags(self) -> None:
        """Test resolve_worktree_path with multiple tag() functions."""
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/tag('env')/tag('version')/path(-1)/norm_branch()",
            sources={},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = resolve_worktree_path(
            config,
            uri,
            "main",
            tags={"env": "production", "version": "2.0"},
        )

        assert "production" in str(result)
        assert "2.0" in str(result)
        assert "repo" in str(result)
        assert "main" in str(result)
