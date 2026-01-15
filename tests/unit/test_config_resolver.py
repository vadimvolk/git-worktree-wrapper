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
            predicate='"github" in host',
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
            predicate='"gitlab" in host',
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
            predicate='"github" in host',
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
            predicate='path[0] == "myorg"',
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
            predicate='protocol == "ssh"',
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
            predicate='port == "3000"',
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
            predicate='not "github" in host',
        )
        # Test with '"github" not in host' form
        non_github_rule2 = SourceRule(
            name="non_github2",
            predicate='"github" not in host',
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
            predicate='"github" in host',
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
            predicate='"github" in host',
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

    def test_resolves_worktree_path_with_worktree_name(self) -> None:
        """Test resolving worktree path with worktree name."""
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default/path(-1)/norm_prefix_branch()",
            sources={},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = resolve_worktree_path(config, uri, "feature/new-ui", "my-feature")

        assert "repo" in str(result)
        assert "my-feature-feature-new-ui" in str(result)

    def test_uses_matching_rule_worktrees(self) -> None:
        """Test that matching rule's worktrees template is used."""
        github_rule = SourceRule(
            name="github",
            predicate='"github" in host',
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
            predicate='"github" in host',
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

    def test_worktree_function_returns_empty_when_no_name(self) -> None:
        """Test worktree() returns empty string when no name provided."""
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default/worktree()norm_branch()",
            sources={},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = resolve_worktree_path(config, uri, "main", worktree_name=None)

        # Should not have double slashes or issues from empty worktree()
        assert "main" in str(result)

    def test_prefix_worktree_returns_empty_when_no_name(self) -> None:
        """Test prefix_worktree() returns empty when no worktree name."""
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default/prefix_worktree('-')norm_branch()",
            sources={},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = resolve_worktree_path(config, uri, "feature/test", worktree_name=None)

        # Should not have prefix, just norm_branch
        path_str = str(result)
        assert "feature-test" in path_str

    def test_prefix_worktree_with_default_prefix(self) -> None:
        """Test prefix_worktree() uses default '-' prefix when no argument provided."""
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default/norm_branch()prefix_worktree()",
            sources={},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = resolve_worktree_path(config, uri, "feature/test", worktree_name="my-work")

        # Should have default "-" prefix before worktree name
        path_str = str(result)
        assert "feature-test" in path_str
        assert "-my-work" in path_str

    def test_prefix_worktree_with_explicit_prefix(self) -> None:
        """Test prefix_worktree() with explicit prefix for backward compatibility."""
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default/norm_branch()prefix_worktree('/')",
            sources={},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = resolve_worktree_path(config, uri, "feature/test", worktree_name="my-work")

        # Should have explicit "/" prefix before worktree name
        path_str = str(result)
        assert "feature-test" in path_str
        assert "/my-work" in path_str

    def test_prefix_branch_with_worktree_name_and_default_prefix(self) -> None:
        """Test prefix_branch() with worktree name and default prefix."""
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default/path(-1)/prefix_branch()",
            sources={},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = resolve_worktree_path(config, uri, "feature/new-ui", worktree_name="my-work")

        # Should have worktree name, default "-" prefix, and branch (non-normalized)
        path_str = str(result)
        assert "repo" in path_str
        assert "my-work-feature/new-ui" in path_str

    def test_prefix_branch_with_worktree_name_and_custom_prefix(self) -> None:
        """Test prefix_branch() with worktree name and custom prefix."""
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default/path(-1)/prefix_branch('/')",
            sources={},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = resolve_worktree_path(config, uri, "feature/new-ui", worktree_name="my-work")

        # Should have worktree name, custom "/" prefix, and branch (non-normalized)
        path_str = str(result)
        assert "repo" in path_str
        assert "my-work/feature/new-ui" in path_str

    def test_prefix_branch_without_worktree_name(self) -> None:
        """Test prefix_branch() without worktree name returns just branch."""
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default/path(-1)/prefix_branch()",
            sources={},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = resolve_worktree_path(config, uri, "feature/new-ui", worktree_name=None)

        # Should return just branch (non-normalized) when no worktree name
        path_str = str(result)
        assert "repo" in path_str
        assert "feature/new-ui" in path_str

    def test_prefix_branch_preserves_branch_name_as_is(self) -> None:
        """Test prefix_branch() preserves branch name without normalization."""
        config = Config(
            default_sources="~/sources/default",
            default_worktrees="~/worktrees/default/path(-1)/prefix_branch()",
            sources={},
        )
        uri = parse_uri("https://github.com/user/repo.git")

        result = resolve_worktree_path(config, uri, "feature/new/ui", worktree_name="my-work")

        # Should preserve "/" in branch name (not normalized)
        path_str = str(result)
        assert "my-work-feature/new/ui" in path_str
        # Verify it's not normalized (should have slashes, not dashes)
        assert "feature/new/ui" in path_str or "my-work-feature/new/ui" in path_str


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
            predicate='"github" in host',
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
            predicate='"gitlab" in host',
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
            predicate='"github" in host',
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
