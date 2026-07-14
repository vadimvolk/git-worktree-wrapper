"""Unit tests for the provider resolution module (``gww.providers``)."""

from __future__ import annotations

import pytest

from gww.config.validator import ConfigValidationError, ProviderConfig, validate_config
from gww.providers import match_provider


class TestMatchProvider:
    """``match_provider`` walks user-declared providers in config order and
    returns the first one whose pattern matches the source's origin host."""

    def _pcfg(self, kind: str, patterns: list[str], merged: str = "true") -> ProviderConfig:
        return ProviderConfig(kind=kind, host_patterns=patterns, merged=merged)

    def test_returns_none_when_no_providers_declared(self) -> None:
        assert match_provider({}, "github.com") is None

    def test_returns_none_when_no_pattern_matches(self) -> None:
        providers = {
            "github": self._pcfg("github", [r"^github\.com$"]),
            "gitlab": self._pcfg("gitlab", [r"^gitlab\.com$"]),
        }
        assert match_provider(providers, "codeberg.org") is None

    def test_matches_when_pattern_matches(self) -> None:
        providers = {
            "github": self._pcfg("github", [r"^github\.com$"]),
        }
        result = match_provider(providers, "github.com")
        assert result is not None
        assert result.kind == "github"

    def test_first_match_wins_in_config_order(self) -> None:
        providers = {
            "first": self._pcfg("first", [r"^.*\.example\.com$"]),
            "second": self._pcfg("second", [r"^github\.com$"]),
        }
        result = match_provider(providers, "github.com.example.com")
        assert result is not None
        assert result.kind == "first"

    def test_multiple_patterns_first_match_wins(self) -> None:
        providers = {
            "github": self._pcfg(
                "github",
                [r"^github\.com$", r"^.*\.github\.com$"],
            ),
        }
        result = match_provider(providers, "api.github.com")
        assert result is not None
        assert result.kind == "github"

    def test_regex_patterns_supported(self) -> None:
        providers = {
            "github": self._pcfg("github", [r"^.*\.?github\.com$"]),
        }
        assert match_provider(providers, "github.com") is not None
        assert match_provider(providers, "api.github.com") is not None
        assert match_provider(providers, "gitlab.com") is None

    def test_anchored_patterns(self) -> None:
        """Patterns are matched with ``re.fullmatch`` so ``^github.com$``
        does NOT match ``mygithub.com``."""
        providers = {
            "github": self._pcfg("github", [r"^github\.com$"]),
        }
        assert match_provider(providers, "mygithub.com") is None


class TestProviderConfigValidation:
    """The validator accepts ``providers:`` blocks and rejects malformed
    entries. Bad regex must be caught at config-validation time
    (ADR-0019)."""

    def test_valid_provider_block_loads(self) -> None:
        data = {
            "default_sources": "~/sources",
            "default_worktrees": "~/worktrees",
            "providers": {
                "github": {
                    "host_patterns": [r"^github\.com$"],
                    "merged": "gh pr list --head branch() --state merged",
                },
            },
        }
        config = validate_config(data)
        assert "github" in config.providers
        assert config.providers["github"].kind == "github"
        assert config.providers["github"].host_patterns == [r"^github\.com$"]

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

    def test_missing_host_patterns_rejected(self) -> None:
        data = {
            "default_sources": "~/sources",
            "default_worktrees": "~/worktrees",
            "providers": {"github": {"merged": "true"}},
        }
        with pytest.raises(ConfigValidationError, match="host_patterns"):
            validate_config(data)

    def test_empty_host_patterns_rejected(self) -> None:
        data = {
            "default_sources": "~/sources",
            "default_worktrees": "~/worktrees",
            "providers": {"github": {"host_patterns": [], "merged": "true"}},
        }
        with pytest.raises(ConfigValidationError, match="non-empty"):
            validate_config(data)

    def test_host_patterns_not_a_list_rejected(self) -> None:
        data = {
            "default_sources": "~/sources",
            "default_worktrees": "~/worktrees",
            "providers": {
                "github": {"host_patterns": "^github\\.com$", "merged": "true"},
            },
        }
        with pytest.raises(ConfigValidationError, match="non-empty"):
            validate_config(data)

    def test_host_pattern_must_be_string(self) -> None:
        data = {
            "default_sources": "~/sources",
            "default_worktrees": "~/worktrees",
            "providers": {
                "github": {"host_patterns": [42], "merged": "true"},
            },
        }
        with pytest.raises(ConfigValidationError, match="must be a string"):
            validate_config(data)

    def test_invalid_regex_rejected(self) -> None:
        data = {
            "default_sources": "~/sources",
            "default_worktrees": "~/worktrees",
            "providers": {
                "github": {"host_patterns": ["("], "merged": "true"},
            },
        }
        with pytest.raises(ConfigValidationError, match="valid regex"):
            validate_config(data)

    def test_missing_merged_rejected(self) -> None:
        data = {
            "default_sources": "~/sources",
            "default_worktrees": "~/worktrees",
            "providers": {
                "github": {"host_patterns": [r"^github\.com$"]},
            },
        }
        with pytest.raises(ConfigValidationError, match="merged"):
            validate_config(data)

    def test_empty_merged_rejected(self) -> None:
        data = {
            "default_sources": "~/sources",
            "default_worktrees": "~/worktrees",
            "providers": {
                "github": {
                    "host_patterns": [r"^github\.com$"],
                    "merged": "   ",
                },
            },
        }
        with pytest.raises(ConfigValidationError, match="cannot be empty"):
            validate_config(data)

    def test_merged_must_be_string(self) -> None:
        data = {
            "default_sources": "~/sources",
            "default_worktrees": "~/worktrees",
            "providers": {
                "github": {
                    "host_patterns": [r"^github\.com$"],
                    "merged": 42,
                },
            },
        }
        with pytest.raises(ConfigValidationError, match="merged"):
            validate_config(data)