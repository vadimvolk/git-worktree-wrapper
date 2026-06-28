"""Unit tests for gww.actions.apply_actions and the typed action classes it builds."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from gww.actions import (
    AbsCopyAction,
    ActionError,
    CommandAction,
    MatcherError,
    RelCopyAction,
    apply_actions,
)
from gww.actions.types import Action
from gww.config.validator import Action as RawAction
from gww.config.validator import ProjectRule


def make_project(tmp_path: Path, *rules: ProjectRule) -> list[ProjectRule]:
    """Helper: pretend a project lives at tmp_path for predicate evaluation."""
    return list(rules)


class TestApplyActionsMatching:
    """apply_actions must return only the actions from rules whose ``when``
    predicate evaluated True, and from the requested kind (``after_clone``
    vs ``after_add``)."""

    def test_returns_no_actions_when_no_rules_match(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="False",
            after_clone=[RawAction(action_type="command", args=["echo"])],
        )

        result = apply_actions([rule], tmp_path, {}, dest_path=tmp_path, kind="after_clone")

        assert result == []

    def test_returns_actions_from_matching_rule(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[RawAction(action_type="command", args=["echo hi"])],
        )

        result = apply_actions([rule], tmp_path, {}, dest_path=tmp_path, kind="after_clone")

        assert len(result) == 1
        assert isinstance(result[0], CommandAction)

    def test_after_clone_kind_returns_only_clone_actions(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[RawAction(action_type="command", args=["clone-cmd"])],
            after_add=[RawAction(action_type="command", args=["add-cmd"])],
        )

        result = apply_actions([rule], tmp_path, {}, dest_path=tmp_path, kind="after_clone")

        assert len(result) == 1
        assert isinstance(result[0], CommandAction)
        assert result[0].command == "clone-cmd"

    def test_after_add_kind_returns_only_add_actions(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[RawAction(action_type="command", args=["clone-cmd"])],
            after_add=[RawAction(action_type="command", args=["add-cmd"])],
        )

        result = apply_actions([rule], tmp_path, {}, dest_path=tmp_path, kind="after_add")

        assert len(result) == 1
        assert isinstance(result[0], CommandAction)
        assert result[0].command == "add-cmd"

    def test_preserves_action_order(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[
                RawAction(action_type="command", args=["first"]),
                RawAction(action_type="abs_copy", args=["/tmp/a", "b"]),
                RawAction(action_type="command", args=["third"]),
            ],
        )

        result = apply_actions([rule], tmp_path, {}, dest_path=tmp_path, kind="after_clone")

        assert [type(a).__name__ for a in result] == [
            "CommandAction",
            "AbsCopyAction",
            "CommandAction",
        ]

    def test_collects_actions_from_multiple_matching_rules(self, tmp_path: Path) -> None:
        rules = [
            ProjectRule(
                when="True",
                after_clone=[RawAction(action_type="command", args=["a"])],
            ),
            ProjectRule(
                when="True",
                after_clone=[RawAction(action_type="command", args=["b"])],
            ),
        ]

        result = apply_actions(rules, tmp_path, {}, dest_path=tmp_path, kind="after_clone")

        assert [a.command for a in result if isinstance(a, CommandAction)] == ["a", "b"]

    def test_invalid_predicate_raises_matcher_error(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="undefined_variable",
            after_clone=[RawAction(action_type="command", args=["echo"])],
        )

        with pytest.raises(MatcherError, match="Error evaluating 'when'"):
            apply_actions([rule], tmp_path, {}, dest_path=tmp_path, kind="after_clone")


class TestApplyActionsBuildsTypedObjects:
    """apply_actions must turn RawAction into the correct typed class."""

    def test_command_action_with_template_function_evaluates_context(
        self, tmp_path: Path,
    ) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[
                RawAction(action_type="command", args=["./setup.sh dest_path()"]),
            ],
        )

        result = apply_actions([rule], tmp_path, {}, dest_path=tmp_path, kind="after_clone")

        assert len(result) == 1
        assert isinstance(result[0], CommandAction)
        assert result[0].command == "./setup.sh"
        assert result[0].args == [str(tmp_path)]

    def test_command_action_with_tag_value(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[
                RawAction(action_type="command", args=["claude -p tag('prompt')"]),
            ],
        )

        result = apply_actions(
            [rule], tmp_path, {"prompt": "/review"},
            dest_path=tmp_path, kind="after_clone",
        )

        assert isinstance(result[0], CommandAction)
        assert result[0].command == "claude"
        assert result[0].args == ["-p", "/review"]

    def test_command_action_with_quoted_args_splits_correctly(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[RawAction(action_type="command", args=["echo 'hello world'"])],
        )

        result = apply_actions([rule], tmp_path, {}, dest_path=tmp_path, kind="after_clone")

        assert isinstance(result[0], CommandAction)
        assert result[0].command == "echo"
        assert result[0].args == ["hello world"]

    def test_abs_copy_action_built_from_args(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[
                RawAction(action_type="abs_copy", args=["/tmp/source.txt", "dst.txt"]),
            ],
        )

        result = apply_actions([rule], tmp_path, {}, dest_path=tmp_path, kind="after_clone")

        assert len(result) == 1
        assert isinstance(result[0], AbsCopyAction)
        assert result[0].source == "/tmp/source.txt"
        assert result[0].destination == "dst.txt"

    def test_rel_copy_action_built_with_default_destination(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_add=[RawAction(action_type="rel_copy", args=["local.properties"])],
        )

        result = apply_actions([rule], tmp_path, {}, dest_path=tmp_path, kind="after_add")

        assert len(result) == 1
        assert isinstance(result[0], RelCopyAction)
        assert result[0].source == "local.properties"
        assert result[0].destination is None

    def test_rel_copy_action_built_with_explicit_destination(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_add=[
                RawAction(action_type="rel_copy", args=["a.txt", "b.txt"]),
            ],
        )

        result = apply_actions([rule], tmp_path, {}, dest_path=tmp_path, kind="after_add")

        assert isinstance(result[0], RelCopyAction)
        assert result[0].source == "a.txt"
        assert result[0].destination == "b.txt"

    def test_predicate_using_tag_function(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when='tag("env") == "production"',
            after_clone=[RawAction(action_type="command", args=["echo"])],
        )

        matching = apply_actions(
            [rule], tmp_path, {"env": "production"},
            dest_path=tmp_path, kind="after_clone",
        )
        not_matching = apply_actions(
            [rule], tmp_path, {"env": "dev"},
            dest_path=tmp_path, kind="after_clone",
        )

        assert len(matching) == 1
        assert not_matching == []

    def test_unknown_action_type_raises_matcher_error(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[RawAction(action_type="unsupported", args=[])],
        )

        with pytest.raises(MatcherError, match="Unknown action type"):
            apply_actions([rule], tmp_path, {}, dest_path=tmp_path, kind="after_clone")