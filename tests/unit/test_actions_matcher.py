"""Unit tests for project action matching and execution in src/gww/actions/matcher.py."""

import pytest
from pathlib import Path
from unittest.mock import patch

from gww.actions.matcher import (
    MatcherError,
    find_matching_projects,
    get_source_actions,
    get_worktree_actions,
)
from gww.config.validator import Action, ProjectRule


class TestFindMatchingProjects:
    """Tests for find_matching_projects function.
    
    Note: These tests use simple boolean predicates since the implementation
    passes context as names (variables) to simpleeval. The file_exists/dir_exists
    functions are in the context but simpleeval treats them as variables not functions.
    """

    def test_matches_always_true_predicate(self, tmp_path: Path) -> None:
        """Test matching project with always-true predicate."""
        rule = ProjectRule(
            predicate='True',
            after_clone=[Action(action_type="command", args=["echo found"])],
        )

        result = find_matching_projects([rule], tmp_path)

        assert len(result) == 1
        assert result[0] == rule

    def test_no_match_with_false_predicate(self, tmp_path: Path) -> None:
        """Test no match with false predicate."""
        rule = ProjectRule(
            predicate='False',
            after_clone=[Action(action_type="command", args=["echo"])],
        )

        result = find_matching_projects([rule], tmp_path)

        assert len(result) == 0

    def test_command_with_template_functions(self, tmp_path: Path) -> None:
        """Test command action with template functions gets evaluated."""
        dest = tmp_path / "worktree"
        dest.mkdir()
        rule = ProjectRule(
            predicate='True',
            after_clone=[Action(action_type="command", args=["./setup.sh dest_path()"])],
        )

        result = get_source_actions([rule], tmp_path, dest_path=dest)

        assert len(result) == 1
        action_type, args = result[0]
        assert action_type == "command"
        # dest_path() should be evaluated and shlex.split applied
        assert args == ["./setup.sh", str(dest.resolve())]

    def test_command_with_tag_function(self, tmp_path: Path) -> None:
        """Test command action with tag() function."""
        rule = ProjectRule(
            predicate='True',
            after_clone=[Action(action_type="command", args=["claude -p tag('prompt')"])],
        )

        result = get_source_actions([rule], tmp_path, tags={"prompt": "/review"})

        assert len(result) == 1
        action_type, args = result[0]
        assert action_type == "command"
        assert args == ["claude", "-p", "/review"]

    def test_command_with_quoted_args(self, tmp_path: Path) -> None:
        """Test command action with quoted arguments."""
        rule = ProjectRule(
            predicate='True',
            after_clone=[Action(action_type="command", args=["echo 'hello world'"])],
        )

        result = get_source_actions([rule], tmp_path)

        assert len(result) == 1
        action_type, args = result[0]
        assert action_type == "command"
        assert args == ["echo", "hello world"]

    def test_matches_source_path_predicate(self, tmp_path: Path) -> None:
        """Test matching project with source_path variable predicate."""
        rule = ProjectRule(
            predicate='source_path() != ""',
            after_clone=[Action(action_type="command", args=["echo"])],
        )

        result = find_matching_projects([rule], tmp_path)

        assert len(result) == 1

    def test_matches_multiple_rules(self, tmp_path: Path) -> None:
        """Test matching multiple project rules."""
        rule1 = ProjectRule(
            predicate='True',
            after_clone=[Action(action_type="command", args=["npm install"])],
        )
        rule2 = ProjectRule(
            predicate='True',
            after_clone=[Action(action_type="command", args=["pip install"])],
        )

        result = find_matching_projects([rule1, rule2], tmp_path)

        assert len(result) == 2
        assert rule1 in result
        assert rule2 in result

    def test_empty_rules_list_returns_empty(self, tmp_path: Path) -> None:
        """Test that empty rules list returns empty result."""
        result = find_matching_projects([], tmp_path)

        assert len(result) == 0

    def test_partial_match_rules(self, tmp_path: Path) -> None:
        """Test with mix of matching and non-matching rules."""
        rule1 = ProjectRule(
            predicate='True',
            after_clone=[Action(action_type="command", args=["action1"])],
        )
        rule2 = ProjectRule(
            predicate='False',
            after_clone=[Action(action_type="command", args=["action2"])],
        )
        rule3 = ProjectRule(
            predicate='True',
            after_clone=[Action(action_type="command", args=["action3"])],
        )

        result = find_matching_projects([rule1, rule2, rule3], tmp_path)

        assert len(result) == 2
        assert rule1 in result
        assert rule2 not in result
        assert rule3 in result

    def test_invalid_predicate_raises_matcher_error(self, tmp_path: Path) -> None:
        """Test that invalid predicate raises MatcherError."""
        rule = ProjectRule(
            predicate='undefined_variable',
            after_clone=[Action(action_type="command", args=["echo"])],
        )

        with pytest.raises(MatcherError, match="Error evaluating predicate"):
            find_matching_projects([rule], tmp_path)

    def test_predicate_with_source_path_variable(self, tmp_path: Path) -> None:
        """Test predicate that uses source_path variable."""
        rule = ProjectRule(
            predicate='source_path() != ""',
            after_clone=[Action(action_type="command", args=["echo"])],
        )

        result = find_matching_projects([rule], tmp_path)

        # source_path is set, so predicate should be True
        assert len(result) == 1

    def test_matches_with_tag_exist_predicate(self, tmp_path: Path) -> None:
        """Test matching project with tag_exist() predicate."""
        rule = ProjectRule(
            predicate='tag_exist("env")',
            after_clone=[Action(action_type="command", args=["echo"])],
        )

        result = find_matching_projects([rule], tmp_path, tags={"env": "production"})

        assert len(result) == 1
        assert result[0] == rule

    def test_no_match_when_tag_not_exists(self, tmp_path: Path) -> None:
        """Test no match when tag_exist() returns False."""
        rule = ProjectRule(
            predicate='tag_exist("env")',
            after_clone=[Action(action_type="command", args=["echo"])],
        )

        result = find_matching_projects([rule], tmp_path, tags={"other": "value"})

        assert len(result) == 0

    def test_matches_with_tag_value_predicate(self, tmp_path: Path) -> None:
        """Test matching project with tag() value comparison."""
        rule = ProjectRule(
            predicate='tag("env") == "production"',
            after_clone=[Action(action_type="command", args=["echo"])],
        )

        result = find_matching_projects([rule], tmp_path, tags={"env": "production"})

        assert len(result) == 1

    def test_no_match_with_different_tag_value(self, tmp_path: Path) -> None:
        """Test no match when tag value doesn't match predicate."""
        rule = ProjectRule(
            predicate='tag("env") == "production"',
            after_clone=[Action(action_type="command", args=["echo"])],
        )

        result = find_matching_projects([rule], tmp_path, tags={"env": "development"})

        assert len(result) == 0

    def test_tag_returns_empty_string_when_not_exists(self, tmp_path: Path) -> None:
        """Test tag() returns empty string when tag doesn't exist."""
        rule = ProjectRule(
            predicate='tag("missing") == ""',
            after_clone=[Action(action_type="command", args=["echo"])],
        )

        result = find_matching_projects([rule], tmp_path, tags={})

        assert len(result) == 1

    def test_tag_exist_with_empty_value(self, tmp_path: Path) -> None:
        """Test tag_exist() returns True even when tag has empty value."""
        rule = ProjectRule(
            predicate='tag_exist("flag")',
            after_clone=[Action(action_type="command", args=["echo"])],
        )

        result = find_matching_projects([rule], tmp_path, tags={"flag": ""})

        assert len(result) == 1

    def test_tag_with_empty_value_in_predicate(self, tmp_path: Path) -> None:
        """Test tag() with empty value in predicate."""
        rule = ProjectRule(
            predicate='tag("flag") == ""',
            after_clone=[Action(action_type="command", args=["echo"])],
        )

        result = find_matching_projects([rule], tmp_path, tags={"flag": ""})

        assert len(result) == 1

    def test_multiple_tags_in_predicate(self, tmp_path: Path) -> None:
        """Test using multiple tags in predicate."""
        rule = ProjectRule(
            predicate='tag_exist("env") and tag("env") == "production"',
            after_clone=[Action(action_type="command", args=["echo"])],
        )

        result = find_matching_projects(
            [rule], tmp_path, tags={"env": "production", "version": "1.0"}
        )

        assert len(result) == 1

    def test_tag_functions_with_complex_predicate(self, tmp_path: Path) -> None:
        """Test tag functions in complex predicate with logical operators."""
        rule = ProjectRule(
            predicate='tag_exist("env") and (tag("env") == "production" or tag("env") == "staging")',
            after_clone=[Action(action_type="command", args=["echo"])],
        )

        # Test with production
        result1 = find_matching_projects(
            [rule], tmp_path, tags={"env": "production"}
        )
        assert len(result1) == 1

        # Test with staging
        result2 = find_matching_projects([rule], tmp_path, tags={"env": "staging"})
        assert len(result2) == 1

        # Test with development (should not match)
        result3 = find_matching_projects(
            [rule], tmp_path, tags={"env": "development"}
        )
        assert len(result3) == 0

    def test_tag_functions_with_no_tags_provided(self, tmp_path: Path) -> None:
        """Test tag functions when no tags are provided."""
        rule = ProjectRule(
            predicate='tag_exist("env")',
            after_clone=[Action(action_type="command", args=["echo"])],
        )

        result = find_matching_projects([rule], tmp_path)

        assert len(result) == 0

    def test_tag_functions_with_partial_tags(self, tmp_path: Path) -> None:
        """Test tag functions when only some tags are provided."""
        rule1 = ProjectRule(
            predicate='tag_exist("env")',
            after_clone=[Action(action_type="command", args=["action1"])],
        )
        rule2 = ProjectRule(
            predicate='tag_exist("version")',
            after_clone=[Action(action_type="command", args=["action2"])],
        )

        result = find_matching_projects(
            [rule1, rule2], tmp_path, tags={"env": "production"}
        )

        assert len(result) == 1
        assert result[0] == rule1


class TestGetSourceActions:
    """Tests for get_source_actions function."""

    def test_returns_source_actions_for_matching_rules(self, tmp_path: Path) -> None:
        """Test returning source actions for matching project rules."""
        rule = ProjectRule(
            predicate='True',
            after_clone=[
                Action(action_type="abs_copy", args=["~/default.properties", "local.properties"]),
                Action(action_type="command", args=["./setup.sh"]),
            ],
        )

        result = get_source_actions([rule], tmp_path)

        assert len(result) == 2
        assert result[0] == ("abs_copy", ["~/default.properties", "local.properties"])
        # Command is now a single string that gets parsed with shlex
        assert result[1] == ("command", ["./setup.sh"])

    def test_returns_empty_for_no_matches(self, tmp_path: Path) -> None:
        """Test returning empty list when no rules match."""
        rule = ProjectRule(
            predicate='False',
            after_clone=[Action(action_type="command", args=["echo"])],
        )

        result = get_source_actions([rule], tmp_path)

        assert len(result) == 0

    def test_returns_actions_from_multiple_matching_rules(self, tmp_path: Path) -> None:
        """Test returning actions from multiple matching rules."""
        rule1 = ProjectRule(
            predicate='True',
            after_clone=[Action(action_type="command", args=["action1"])],
        )
        rule2 = ProjectRule(
            predicate='True',
            after_clone=[Action(action_type="command", args=["action2"])],
        )

        result = get_source_actions([rule1, rule2], tmp_path)

        assert len(result) == 2
        # Commands are parsed with shlex, single words remain as single-element lists
        assert ("command", ["action1"]) in result
        assert ("command", ["action2"]) in result

    def test_ignores_after_add_actions(self, tmp_path: Path) -> None:
        """Test that get_source_actions ignores after_add actions."""
        rule = ProjectRule(
            predicate='True',
            after_clone=[Action(action_type="command", args=["source-cmd"])],
            after_add=[Action(action_type="command", args=["worktree-cmd"])],
        )

        result = get_source_actions([rule], tmp_path)

        assert len(result) == 1
        assert result[0] == ("command", ["source-cmd"])


class TestGetWorktreeActions:
    """Tests for get_worktree_actions function."""

    def test_returns_worktree_actions_for_matching_rules(self, tmp_path: Path) -> None:
        """Test returning worktree actions for matching project rules."""
        rule = ProjectRule(
            predicate='True',
            after_clone=[],
            after_add=[
                Action(action_type="rel_copy", args=["local.properties"]),
                Action(action_type="command", args=["./init-worktree.sh"]),
            ],
        )

        result = get_worktree_actions([rule], tmp_path)

        assert len(result) == 2
        assert result[0] == ("rel_copy", ["local.properties"])
        # Command is now a single string that gets parsed with shlex
        assert result[1] == ("command", ["./init-worktree.sh"])

    def test_returns_empty_for_no_matches(self, tmp_path: Path) -> None:
        """Test returning empty list when no rules match."""
        rule = ProjectRule(
            predicate='False',
            after_add=[Action(action_type="command", args=["echo"])],
        )

        result = get_worktree_actions([rule], tmp_path)

        assert len(result) == 0

    def test_ignores_after_clone_actions(self, tmp_path: Path) -> None:
        """Test that get_worktree_actions ignores after_clone actions."""
        rule = ProjectRule(
            predicate='True',
            after_clone=[Action(action_type="command", args=["source-cmd"])],
            after_add=[Action(action_type="command", args=["worktree-cmd"])],
        )

        result = get_worktree_actions([rule], tmp_path)

        assert len(result) == 1
        assert result[0] == ("command", ["worktree-cmd"])


class TestActionsExecution:
    """Tests for action execution context (T025 continued)."""

    def test_abs_copy_action_args_format(self, tmp_path: Path) -> None:
        """Test abs_copy action arguments are properly formatted."""
        rule = ProjectRule(
            predicate='True',
            after_clone=[
                Action(action_type="abs_copy", args=["~/configs/default.properties", "local.properties"])
            ],
        )

        result = get_source_actions([rule], tmp_path)

        assert len(result) == 1
        action_type, args = result[0]
        assert action_type == "abs_copy"
        assert len(args) == 2
        assert args[0] == "~/configs/default.properties"
        assert args[1] == "local.properties"

    def test_rel_copy_action_args_format(self, tmp_path: Path) -> None:
        """Test rel_copy action arguments are properly formatted."""
        rule = ProjectRule(
            predicate='True',
            after_add=[
                Action(action_type="rel_copy", args=["local.properties", "settings.properties"])
            ],
        )

        result = get_worktree_actions([rule], tmp_path)

        assert len(result) == 1
        action_type, args = result[0]
        assert action_type == "rel_copy"
        assert len(args) == 2
        assert args[0] == "local.properties"
        assert args[1] == "settings.properties"

    def test_command_action_with_multiple_args(self, tmp_path: Path) -> None:
        """Test command action with multiple arguments (single string, parsed with shlex)."""
        rule = ProjectRule(
            predicate='True',
            after_clone=[
                # Command is now a single string that gets parsed with shlex
                Action(action_type="command", args=["make build --verbose"])
            ],
        )

        result = get_source_actions([rule], tmp_path)

        assert len(result) == 1
        action_type, args = result[0]
        assert action_type == "command"
        assert args == ["make", "build", "--verbose"]

    def test_actions_order_preserved(self, tmp_path: Path) -> None:
        """Test that action order is preserved."""
        rule = ProjectRule(
            predicate='True',
            after_clone=[
                Action(action_type="command", args=["first-cmd"]),
                Action(action_type="abs_copy", args=["src", "dst"]),
                Action(action_type="command", args=["third-cmd"]),
            ],
        )

        result = get_source_actions([rule], tmp_path)

        assert len(result) == 3
        assert result[0][1] == ["first-cmd"]
        assert result[1][0] == "abs_copy"
        assert result[2][1] == ["third-cmd"]
