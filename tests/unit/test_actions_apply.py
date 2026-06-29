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
    RuleActions,
    apply_actions,
)
from gww.actions.types import Action
from gww.config.validator import Action as RawAction
from gww.config.validator import ProjectRule


def make_project(tmp_path: Path, *rules: ProjectRule) -> list[ProjectRule]:
    """Helper: pretend a project lives at tmp_path for predicate evaluation."""
    return list(rules)


class TestApplyActionsMatching:
    """apply_actions must return one :class:`RuleActions` bundle per rule whose
    ``when`` predicate evaluated True, with the requested ``kind``'s actions."""

    def test_returns_no_bundles_when_no_rules_match(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="False",
            after_clone=[RawAction(action_type="command", args=["echo"])],
        )

        bundles = apply_actions(
            [rule], tmp_path, {}, dest_path=tmp_path, kind="after_clone"
        )

        assert bundles == []

    def test_returns_bundle_from_matching_rule(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[RawAction(action_type="command", args=["echo hi"])],
        )

        bundles = apply_actions(
            [rule], tmp_path, {}, dest_path=tmp_path, kind="after_clone"
        )

        assert len(bundles) == 1
        assert isinstance(bundles[0], RuleActions)
        assert isinstance(bundles[0].actions[0], CommandAction)

    def test_after_clone_kind_returns_only_clone_actions(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[RawAction(action_type="command", args=["clone-cmd"])],
            after_add=[RawAction(action_type="command", args=["add-cmd"])],
        )

        bundles = apply_actions(
            [rule], tmp_path, {}, dest_path=tmp_path, kind="after_clone"
        )

        assert len(bundles) == 1
        assert isinstance(bundles[0].actions[0], CommandAction)
        assert bundles[0].actions[0].command == "clone-cmd"

    def test_after_add_kind_returns_only_add_actions(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[RawAction(action_type="command", args=["clone-cmd"])],
            after_add=[RawAction(action_type="command", args=["add-cmd"])],
        )

        bundles = apply_actions(
            [rule], tmp_path, {}, dest_path=tmp_path, kind="after_add"
        )

        assert len(bundles) == 1
        assert isinstance(bundles[0].actions[0], CommandAction)
        assert bundles[0].actions[0].command == "add-cmd"

    def test_preserves_action_order(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[
                RawAction(action_type="command", args=["first"]),
                RawAction(action_type="abs_copy", args=["/tmp/a", "b"]),
                RawAction(action_type="command", args=["third"]),
            ],
        )

        bundles = apply_actions(
            [rule], tmp_path, {}, dest_path=tmp_path, kind="after_clone"
        )

        assert [type(a).__name__ for a in bundles[0].actions] == [
            "CommandAction",
            "AbsCopyAction",
            "CommandAction",
        ]

    def test_collects_bundles_from_multiple_matching_rules(self, tmp_path: Path) -> None:
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

        bundles = apply_actions(
            rules, tmp_path, {}, dest_path=tmp_path, kind="after_clone"
        )

        assert [
            a.command
            for bundle in bundles
            for a in bundle.actions
            if isinstance(a, CommandAction)
        ] == ["a", "b"]

    def test_invalid_predicate_raises_matcher_error(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="undefined_variable",
            after_clone=[RawAction(action_type="command", args=["echo"])],
        )

        with pytest.raises(MatcherError, match="Error evaluating 'when'"):
            apply_actions(
                [rule], tmp_path, {}, dest_path=tmp_path, kind="after_clone"
            )

    def test_matched_rule_without_kind_emits_empty_bundle(self, tmp_path: Path) -> None:
        """A rule that matches but only has the *other* kind must still emit a
        bundle — its ``actions`` list is just empty. Keeps the CLI loop's
        bundle-counting predictable."""
        rule = ProjectRule(
            when="True",
            after_add=[RawAction(action_type="command", args=["add-only"])],
        )

        bundles = apply_actions(
            [rule], tmp_path, {}, dest_path=tmp_path, kind="after_clone"
        )

        assert len(bundles) == 1
        assert bundles[0].actions == []


class TestRuleActionsMetadata:
    """The bundle returned by apply_actions must carry the rule's index,
    predicate text, and criticality flag so the CLI loop can attribute
    failures and choose exit codes."""

    def test_bundle_carries_rule_index(self, tmp_path: Path) -> None:
        rules = [
            ProjectRule(
                when="False",
                after_clone=[RawAction(action_type="command", args=["x"])],
            ),
            ProjectRule(
                when="True",
                after_clone=[RawAction(action_type="command", args=["y"])],
            ),
        ]

        bundles = apply_actions(
            rules, tmp_path, {}, dest_path=tmp_path, kind="after_clone"
        )

        assert [b.index for b in bundles] == [1]

    def test_bundle_carries_predicate_text(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text("# hi")

        rule = ProjectRule(
            when='file_exists("CLAUDE.md")',
            after_clone=[RawAction(action_type="command", args=["echo"])],
        )

        bundles = apply_actions(
            [rule], tmp_path, {}, dest_path=tmp_path, kind="after_clone"
        )

        assert bundles[0].predicate == 'file_exists("CLAUDE.md")'

    def test_default_criticality_is_true(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[RawAction(action_type="command", args=["echo"])],
        )

        bundles = apply_actions(
            [rule], tmp_path, {}, dest_path=tmp_path, kind="after_clone"
        )

        assert bundles[0].critical is True

    def test_explicit_critical_false_is_propagated(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            critical=False,
            after_clone=[RawAction(action_type="command", args=["echo"])],
        )

        bundles = apply_actions(
            [rule], tmp_path, {}, dest_path=tmp_path, kind="after_clone"
        )

        assert bundles[0].critical is False


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

        bundles = apply_actions(
            [rule], tmp_path, {}, dest_path=tmp_path, kind="after_clone"
        )

        action = bundles[0].actions[0]
        assert isinstance(action, CommandAction)
        assert action.command == "./setup.sh"
        assert action.args == [str(tmp_path)]

    def test_command_action_with_tag_value(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[
                RawAction(action_type="command", args=["claude -p tag('prompt')"]),
            ],
        )

        bundles = apply_actions(
            [rule], tmp_path, {"prompt": "/review"},
            dest_path=tmp_path, kind="after_clone",
        )

        action = bundles[0].actions[0]
        assert isinstance(action, CommandAction)
        assert action.command == "claude"
        assert action.args == ["-p", "/review"]

    def test_command_action_with_quoted_args_splits_correctly(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[RawAction(action_type="command", args=["echo 'hello world'"])],
        )

        bundles = apply_actions(
            [rule], tmp_path, {}, dest_path=tmp_path, kind="after_clone"
        )

        action = bundles[0].actions[0]
        assert isinstance(action, CommandAction)
        assert action.command == "echo"
        assert action.args == ["hello world"]

    def test_abs_copy_action_built_from_args(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[
                RawAction(action_type="abs_copy", args=["/tmp/source.txt", "dst.txt"]),
            ],
        )

        bundles = apply_actions(
            [rule], tmp_path, {}, dest_path=tmp_path, kind="after_clone"
        )

        action = bundles[0].actions[0]
        assert isinstance(action, AbsCopyAction)
        assert action.source == "/tmp/source.txt"
        assert action.destination == "dst.txt"

    def test_rel_copy_action_built_with_default_destination(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_add=[RawAction(action_type="rel_copy", args=["local.properties"])],
        )

        bundles = apply_actions(
            [rule], tmp_path, {}, dest_path=tmp_path, kind="after_add"
        )

        action = bundles[0].actions[0]
        assert isinstance(action, RelCopyAction)
        assert action.source == "local.properties"
        assert action.destination is None

    def test_rel_copy_action_built_with_explicit_destination(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_add=[
                RawAction(action_type="rel_copy", args=["a.txt", "b.txt"]),
            ],
        )

        bundles = apply_actions(
            [rule], tmp_path, {}, dest_path=tmp_path, kind="after_add"
        )

        action = bundles[0].actions[0]
        assert isinstance(action, RelCopyAction)
        assert action.source == "a.txt"
        assert action.destination == "b.txt"

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
            apply_actions(
                [rule], tmp_path, {}, dest_path=tmp_path, kind="after_clone"
            )

    def test_command_template_failure_raises_matcher_error(
        self, tmp_path: Path,
    ) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[
                RawAction(action_type="command", args=["echo undefined_var()"]),
            ],
        )

        with pytest.raises(MatcherError, match="Error evaluating command template"):
            apply_actions(
                [rule], tmp_path, {}, dest_path=tmp_path, kind="after_clone"
            )