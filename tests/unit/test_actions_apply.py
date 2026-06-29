"""Unit tests for gww.actions.apply_actions and the typed action classes it builds."""

from __future__ import annotations

import subprocess
from pathlib import Path

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
from gww.template.functions import TemplateContext


def _ctx(
    source_path: Path,
    *,
    dest_path: Path | None = None,
    tags: dict[str, str] | None = None,
    uri: object = None,
    branch: str | None = None,
) -> TemplateContext:
    """Helper: build a TemplateContext for project-rule evaluation tests."""
    return TemplateContext(
        uri=uri,  # type: ignore[arg-type]
        branch=branch,
        source_path=source_path,
        dest_path=dest_path if dest_path is not None else source_path,
        tags=tags or {},
    )


class TestApplyActionsMatching:
    """apply_actions must return only the actions from rules whose ``when``
    predicate evaluated True, and from the requested kind (``after_clone``
    vs ``after_add``)."""

    def test_returns_no_actions_when_no_rules_match(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="False",
            after_clone=[RawAction(action_type="command", args=["echo"])],
        )

        result = apply_actions([rule], _ctx(tmp_path), kind="after_clone")

        assert result == []

    def test_returns_actions_from_matching_rule(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[RawAction(action_type="command", args=["echo hi"])],
        )

        result = apply_actions([rule], _ctx(tmp_path), kind="after_clone")

        assert len(result) == 1
        assert isinstance(result[0], CommandAction)

    def test_after_clone_kind_returns_only_clone_actions(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[RawAction(action_type="command", args=["clone-cmd"])],
            after_add=[RawAction(action_type="command", args=["add-cmd"])],
        )

        result = apply_actions([rule], _ctx(tmp_path), kind="after_clone")

        assert len(result) == 1
        assert isinstance(result[0], CommandAction)
        assert result[0].command == "clone-cmd"

    def test_after_add_kind_returns_only_add_actions(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[RawAction(action_type="command", args=["clone-cmd"])],
            after_add=[RawAction(action_type="command", args=["add-cmd"])],
        )

        result = apply_actions([rule], _ctx(tmp_path), kind="after_add")

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

        result = apply_actions([rule], _ctx(tmp_path), kind="after_clone")

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

        result = apply_actions(rules, _ctx(tmp_path), kind="after_clone")

        assert [a.command for a in result if isinstance(a, CommandAction)] == ["a", "b"]

    def test_invalid_predicate_raises_matcher_error(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="undefined_variable",
            after_clone=[RawAction(action_type="command", args=["echo"])],
        )

        with pytest.raises(MatcherError, match="Error evaluating 'when'"):
            apply_actions([rule], _ctx(tmp_path), kind="after_clone")


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

        result = apply_actions([rule], _ctx(tmp_path), kind="after_clone")

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

        context = _ctx(tmp_path, tags={"prompt": "/review"})
        result = apply_actions([rule], context, kind="after_clone")

        assert isinstance(result[0], CommandAction)
        assert result[0].command == "claude"
        assert result[0].args == ["-p", "/review"]

    def test_command_action_with_quoted_args_splits_correctly(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[RawAction(action_type="command", args=["echo 'hello world'"])],
        )

        result = apply_actions([rule], _ctx(tmp_path), kind="after_clone")

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

        result = apply_actions([rule], _ctx(tmp_path), kind="after_clone")

        assert len(result) == 1
        assert isinstance(result[0], AbsCopyAction)
        assert result[0].source == "/tmp/source.txt"
        assert result[0].destination == "dst.txt"

    def test_rel_copy_action_built_with_default_destination(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_add=[RawAction(action_type="rel_copy", args=["local.properties"])],
        )

        result = apply_actions([rule], _ctx(tmp_path), kind="after_add")

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

        result = apply_actions([rule], _ctx(tmp_path), kind="after_add")

        assert isinstance(result[0], RelCopyAction)
        assert result[0].source == "a.txt"
        assert result[0].destination == "b.txt"

    def test_predicate_using_tag_function(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when='tag("env") == "production"',
            after_clone=[RawAction(action_type="command", args=["echo"])],
        )

        matching = apply_actions(
            [rule], _ctx(tmp_path, tags={"env": "production"}), kind="after_clone",
        )
        not_matching = apply_actions(
            [rule], _ctx(tmp_path, tags={"env": "dev"}), kind="after_clone",
        )

        assert len(matching) == 1
        assert not_matching == []

    def test_unknown_action_type_raises_matcher_error(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[RawAction(action_type="unsupported", args=[])],
        )

        with pytest.raises(MatcherError, match="Unknown action type"):
            apply_actions([rule], _ctx(tmp_path), kind="after_clone")


class TestApplyActionsUriContext:
    """Project rules can reference URI functions in their ``when`` predicates
    once the calling command threads a parsed :class:`ParsedURI` into the
    evaluation context (regression coverage for the bug where ``host()``
    raised "No URI context available" inside project predicates)."""

    def test_predicate_using_host_function_matches(self, tmp_path: Path) -> None:
        from gww.utils.uri import parse_uri

        rule = ProjectRule(
            when='"somehost" in host()',
            after_clone=[RawAction(action_type="command", args=["echo matched"])],
        )

        uri = parse_uri("https://somehost.example.com/user/repo.git")
        context = _ctx(tmp_path, uri=uri)

        result = apply_actions([rule], context, kind="after_clone")

        assert len(result) == 1
        assert isinstance(result[0], CommandAction)
        assert result[0].command == "echo"
        assert result[0].args == ["matched"]

    def test_predicate_using_host_function_does_not_match(self, tmp_path: Path) -> None:
        from gww.utils.uri import parse_uri

        rule = ProjectRule(
            when='"somehost" in host()',
            after_clone=[RawAction(action_type="command", args=["echo matched"])],
        )

        uri = parse_uri("https://other.example.com/user/repo.git")
        context = _ctx(tmp_path, uri=uri)

        result = apply_actions([rule], context, kind="after_clone")

        assert result == []

    def test_host_function_without_uri_raises(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when='"somehost" in host()',
            after_clone=[RawAction(action_type="command", args=["echo"])],
        )

        with pytest.raises(MatcherError, match="No URI context available"):
            apply_actions([rule], _ctx(tmp_path), kind="after_clone")


class TestApplyActionsBranchContext:
    """Project rules can reference ``branch()`` / ``norm_branch()`` in their
    ``when`` predicates once the calling command populates the branch on the
    evaluation context."""

    def test_predicate_using_branch_function_matches(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when='branch() == "feature/x"',
            after_add=[RawAction(action_type="command", args=["echo"])],
        )

        context = _ctx(tmp_path, branch="feature/x")
        result = apply_actions([rule], context, kind="after_add")

        assert len(result) == 1

    def test_predicate_using_branch_function_does_not_match(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when='branch() == "feature/x"',
            after_add=[RawAction(action_type="command", args=["echo"])],
        )

        context = _ctx(tmp_path, branch="main")
        result = apply_actions([rule], context, kind="after_add")

        assert result == []

    def test_predicate_using_norm_branch_function(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when='norm_branch() == "feature-x"',
            after_add=[RawAction(action_type="command", args=["echo"])],
        )

        context = _ctx(tmp_path, branch="feature/x")
        result = apply_actions([rule], context, kind="after_add")

        assert len(result) == 1

    def test_empty_branch_evaluates_without_raising(self, tmp_path: Path) -> None:
        """Soft-fail branch detection returns ``""``; predicates still evaluate."""
        rule = ProjectRule(
            when='branch() == ""',
            after_add=[RawAction(action_type="command", args=["echo detached"])],
        )

        context = _ctx(tmp_path, branch="")
        result = apply_actions([rule], context, kind="after_add")

        assert len(result) == 1

    def test_branch_function_without_context_raises(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when='branch() == "main"',
            after_add=[RawAction(action_type="command", args=["echo"])],
        )

        with pytest.raises(MatcherError, match="No branch context available"):
            apply_actions([rule], _ctx(tmp_path), kind="after_add")