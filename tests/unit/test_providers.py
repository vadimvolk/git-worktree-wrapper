"""Unit tests for provider resolution.

Providers select by a ``when`` predicate over the source's origin URI —
the same mechanism as ``sources:`` rules (ADR-0021). This module covers
:func:`gww.config.resolver.find_matching_provider`, the shared
:func:`gww.config.rule_matching.first_matching_rule` primitive, and
``providers:`` validation.
"""

from __future__ import annotations

import pytest

from gww.config.resolver import find_matching_provider
from gww.config.rule_matching import ResolverError, first_matching_rule
from gww.config.validator import (
    Config,
    ConfigValidationError,
    ProviderConfig,
    SourceRule,
    validate_config,
)
from gww.utils.uri import parse_uri


def _pcfg(name: str, when: str, filter: str = "true") -> ProviderConfig:
    return ProviderConfig(name=name, when=when, filter=filter)


def _config(providers: dict[str, ProviderConfig]) -> Config:
    return Config(
        default_sources="~/sources/default",
        default_worktrees="~/worktrees/default",
        providers=providers,
    )


class TestFindMatchingProvider:
    """``find_matching_provider`` returns the first provider whose ``when``
    predicate matches the URI, in config order."""

    def test_returns_none_when_no_providers_declared(self) -> None:
        config = _config({})
        uri = parse_uri("https://github.com/user/repo.git")
        assert find_matching_provider(config, uri) is None

    def test_returns_none_when_no_when_matches(self) -> None:
        config = _config(
            {
                "github": _pcfg("github", '"github" in host()'),
                "gitlab": _pcfg("gitlab", '"gitlab" in host()'),
            }
        )
        uri = parse_uri("https://codeberg.org/user/repo.git")
        assert find_matching_provider(config, uri) is None

    def test_matches_when_predicate_matches(self) -> None:
        config = _config({"github": _pcfg("github", '"github" in host()')})
        uri = parse_uri("https://github.com/user/repo.git")
        result = find_matching_provider(config, uri)
        assert result is not None
        assert result.name == "github"

    def test_first_match_wins_in_config_order(self) -> None:
        config = _config(
            {
                "first": _pcfg("first", "True"),
                "second": _pcfg("second", '"github" in host()'),
            }
        )
        uri = parse_uri("https://github.com/user/repo.git")
        result = find_matching_provider(config, uri)
        assert result is not None
        assert result.name == "first"

    def test_substring_match_is_not_anchored(self) -> None:
        """``"github" in host()`` matches any host containing the substring
        (unlike the old anchored regex)."""
        config = _config({"github": _pcfg("github", '"github" in host()')})
        assert find_matching_provider(
            config, parse_uri("https://mygithub.com/user/repo.git")
        ) is not None
        assert find_matching_provider(
            config, parse_uri("https://api.github.com/user/repo.git")
        ) is not None

    def test_when_with_path_access(self) -> None:
        config = _config({"myorg": _pcfg("myorg", 'path(0) == "myorg"')})
        uri = parse_uri("https://git.example.com/myorg/project.git")
        result = find_matching_provider(config, uri)
        assert result is not None
        assert result.name == "myorg"

    def test_when_with_tag(self) -> None:
        config = _config({"tagged": _pcfg("tagged", 'tag_exist("forge")')})
        uri = parse_uri("https://example.com/user/repo.git")
        assert find_matching_provider(config, uri, {}) is None
        result = find_matching_provider(config, uri, {"forge": "gitea"})
        assert result is not None
        assert result.name == "tagged"

    def test_invalid_when_raises_resolver_error(self) -> None:
        config = _config({"invalid": _pcfg("invalid", "undefined_variable")})
        uri = parse_uri("https://github.com/user/repo.git")
        with pytest.raises(
            ResolverError, match="Error evaluating 'when' for provider 'invalid'"
        ):
            find_matching_provider(config, uri)


class TestFirstMatchingRule:
    """The shared primitive underpinning both source-rule and provider
    selection."""

    def test_returns_none_on_empty(self) -> None:
        uri = parse_uri("https://github.com/user/repo.git")
        from gww.config.resolver import _build_uri_context

        context = _build_uri_context(uri)
        assert first_matching_rule({}, context, label="provider") is None

    def test_first_match_wins(self) -> None:
        uri = parse_uri("https://github.com/user/repo.git")
        from gww.config.resolver import _build_uri_context

        context = _build_uri_context(uri)
        rules = {
            "a": SourceRule(name="a", when="True"),
            "b": SourceRule(name="b", when="True"),
        }
        result = first_matching_rule(rules, context, label="source rule")
        assert result is not None
        assert result.name == "a"

    def test_error_message_uses_label(self) -> None:
        uri = parse_uri("https://github.com/user/repo.git")
        from gww.config.resolver import _build_uri_context

        context = _build_uri_context(uri)
        rules = {"x": SourceRule(name="x", when="undefined_variable")}
        with pytest.raises(
            ResolverError, match="Error evaluating 'when' for widget 'x'"
        ):
            first_matching_rule(rules, context, label="widget")


class TestProviderConfigValidation:
    """The validator accepts ``providers:`` blocks and rejects malformed
    entries. Providers require a non-empty ``when`` and ``filter`` string
    (ADR-0021)."""

    def test_valid_provider_block_loads(self) -> None:
        data = {
            "default_sources": "~/sources",
            "default_worktrees": "~/worktrees",
            "providers": {
                "github": {
                    "when": '"github" in host()',
                    "filter": "gh pr list --head branch() --state merged",
                },
            },
        }
        config = validate_config(data)
        assert "github" in config.providers
        assert config.providers["github"].name == "github"
        assert config.providers["github"].when == '"github" in host()'

    def test_free_form_provider_name_allowed(self) -> None:
        """Names are free-form — no github/gitlab/gitea constraint."""
        data = {
            "default_sources": "~/sources",
            "default_worktrees": "~/worktrees",
            "providers": {
                "my-self-hosted-forge": {
                    "when": '"git.example.com" in host()',
                    "filter": "true",
                },
            },
        }
        config = validate_config(data)
        assert config.providers["my-self-hosted-forge"].name == "my-self-hosted-forge"

    def test_empty_providers_block_is_allowed(self) -> None:
        data = {
            "default_sources": "~/sources",
            "default_worktrees": "~/worktrees",
            "providers": {},
        }
        config = validate_config(data)
        assert config.providers == {}

    def test_missing_providers_block_is_allowed(self) -> None:
        data = {
            "default_sources": "~/sources",
            "default_worktrees": "~/worktrees",
        }
        config = validate_config(data)
        assert config.providers == {}

    def test_providers_must_be_a_mapping(self) -> None:
        data = {
            "default_sources": "~/sources",
            "default_worktrees": "~/worktrees",
            "providers": ["not", "a", "mapping"],
        }
        with pytest.raises(ConfigValidationError, match="must be a mapping"):
            validate_config(data)

    def test_provider_block_must_be_a_mapping(self) -> None:
        data = {
            "default_sources": "~/sources",
            "default_worktrees": "~/worktrees",
            "providers": {"github": "not a mapping"},
        }
        with pytest.raises(ConfigValidationError, match="must be a mapping"):
            validate_config(data)

    def test_missing_when_rejected(self) -> None:
        data = {
            "default_sources": "~/sources",
            "default_worktrees": "~/worktrees",
            "providers": {"github": {"filter": "true"}},
        }
        with pytest.raises(ConfigValidationError, match="missing required 'when'"):
            validate_config(data)

    def test_empty_when_rejected(self) -> None:
        data = {
            "default_sources": "~/sources",
            "default_worktrees": "~/worktrees",
            "providers": {"github": {"when": "   ", "filter": "true"}},
        }
        with pytest.raises(ConfigValidationError, match="cannot be empty"):
            validate_config(data)

    def test_when_must_be_string(self) -> None:
        data = {
            "default_sources": "~/sources",
            "default_worktrees": "~/worktrees",
            "providers": {"github": {"when": 42, "filter": "true"}},
        }
        with pytest.raises(ConfigValidationError, match="must be a string"):
            validate_config(data)

    def test_missing_filter_rejected(self) -> None:
        data = {
            "default_sources": "~/sources",
            "default_worktrees": "~/worktrees",
            "providers": {"github": {"when": '"github" in host()'}},
        }
        with pytest.raises(ConfigValidationError, match="filter"):
            validate_config(data)

    def test_empty_filter_rejected(self) -> None:
        data = {
            "default_sources": "~/sources",
            "default_worktrees": "~/worktrees",
            "providers": {
                "github": {"when": '"github" in host()', "filter": "   "},
            },
        }
        with pytest.raises(ConfigValidationError, match="cannot be empty"):
            validate_config(data)

    def test_filter_must_be_string(self) -> None:
        data = {
            "default_sources": "~/sources",
            "default_worktrees": "~/worktrees",
            "providers": {
                "github": {"when": '"github" in host()', "filter": 42},
            },
        }
        with pytest.raises(ConfigValidationError, match="filter"):
            validate_config(data)

    def test_lingering_host_patterns_key_ignored(self) -> None:
        """A leftover ``host_patterns`` key is silently ignored — unknown
        keys aren't rejected today, and there's no back-compat migration."""
        data = {
            "default_sources": "~/sources",
            "default_worktrees": "~/worktrees",
            "providers": {
                "github": {
                    "host_patterns": [r"^github\.com$"],
                    "when": '"github" in host()',
                    "filter": "true",
                },
            },
        }
        config = validate_config(data)
        assert config.providers["github"].when == '"github" in host()'
        assert not hasattr(config.providers["github"], "host_patterns")
