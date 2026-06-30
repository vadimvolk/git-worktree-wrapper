"""Unit tests for gww.actions.apply_actions and the typed action classes it builds."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from gww.actions import (
    ActionError,
    CommandAction,
    CopyAction,
    MatcherError,
    RuleActions,
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
    """apply_actions must return one :class:`RuleActions` bundle per rule whose
    ``when`` predicate evaluated True, with the requested ``kind``'s actions."""

    def test_returns_no_bundles_when_no_rules_match(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="False",
            after_clone=[RawAction(action_type="command", args=["echo"])],
        )

        bundles = apply_actions([rule], _ctx(tmp_path), kind="after_clone")

        assert bundles == []

    def test_returns_bundle_from_matching_rule(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[RawAction(action_type="command", args=["echo hi"])],
        )

        bundles = apply_actions([rule], _ctx(tmp_path), kind="after_clone")

        assert len(bundles) == 1
        assert isinstance(bundles[0], RuleActions)
        assert isinstance(bundles[0].actions[0], CommandAction)

    def test_after_clone_kind_returns_only_clone_actions(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[RawAction(action_type="command", args=["clone-cmd"])],
            after_add=[RawAction(action_type="command", args=["add-cmd"])],
        )

        bundles = apply_actions([rule], _ctx(tmp_path), kind="after_clone")

        assert len(bundles) == 1
        assert isinstance(bundles[0].actions[0], CommandAction)
        assert bundles[0].actions[0].command == "clone-cmd"

    def test_after_add_kind_returns_only_add_actions(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[RawAction(action_type="command", args=["clone-cmd"])],
            after_add=[RawAction(action_type="command", args=["add-cmd"])],
        )

        bundles = apply_actions([rule], _ctx(tmp_path), kind="after_add")

        assert len(bundles) == 1
        assert isinstance(bundles[0].actions[0], CommandAction)
        assert bundles[0].actions[0].command == "add-cmd"

    def test_before_remove_kind_returns_only_before_remove_actions(
        self, tmp_path: Path,
    ) -> None:
        """``apply_actions(kind="before_remove")`` must read the rule's
        ``before_remove`` field, not ``after_clone``/``after_add``."""
        rule = ProjectRule(
            when="True",
            after_clone=[RawAction(action_type="command", args=["clone-cmd"])],
            after_add=[RawAction(action_type="command", args=["add-cmd"])],
            before_remove=[
                RawAction(action_type="command", args=["before-remove-cmd"]),
            ],
        )

        bundles = apply_actions([rule], _ctx(tmp_path), kind="before_remove")

        assert len(bundles) == 1
        assert len(bundles[0].actions) == 1
        assert isinstance(bundles[0].actions[0], CommandAction)
        assert bundles[0].actions[0].command == "before-remove-cmd"

    def test_rule_with_only_after_clone_emits_empty_bundle_for_before_remove(
        self, tmp_path: Path,
    ) -> None:
        """A rule that matches but only has ``after_clone`` actions must still
        emit a bundle for ``kind="before_remove"`` — the bundle's
        ``actions`` list is just empty. Mirrors the after_clone/after_add
        symmetry."""
        rule = ProjectRule(
            when="True",
            after_clone=[RawAction(action_type="command", args=["clone-only"])],
        )

        bundles = apply_actions([rule], _ctx(tmp_path), kind="before_remove")

        assert len(bundles) == 1
        assert bundles[0].actions == []

    def test_matcher_error_on_before_remove_command_template(
        self, tmp_path: Path,
    ) -> None:
        """A ``before_remove`` command whose template fails to evaluate
        propagates as ``MatcherError`` (same path as ``after_clone``)."""
        rule = ProjectRule(
            when="True",
            before_remove=[
                RawAction(action_type="command", args=["echo undefined_var()"]),
            ],
        )

        with pytest.raises(MatcherError, match="Error evaluating command template"):
            apply_actions([rule], _ctx(tmp_path), kind="before_remove")

    def test_preserves_action_order(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[
                RawAction(action_type="command", args=["first"]),
                RawAction(action_type="copy", args=["/tmp/a", "b"]),
                RawAction(action_type="command", args=["third"]),
            ],
        )

        bundles = apply_actions([rule], _ctx(tmp_path), kind="after_clone")

        assert [type(a).__name__ for a in bundles[0].actions] == [
            "CommandAction",
            "CopyAction",
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

        bundles = apply_actions(rules, _ctx(tmp_path), kind="after_clone")

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
            apply_actions([rule], _ctx(tmp_path), kind="after_clone")

    def test_matched_rule_without_kind_emits_empty_bundle(self, tmp_path: Path) -> None:
        """A rule that matches but only has the *other* kind must still emit a
        bundle — its ``actions`` list is just empty. Keeps the CLI loop's
        bundle-counting predictable."""
        rule = ProjectRule(
            when="True",
            after_add=[RawAction(action_type="command", args=["add-only"])],
        )

        bundles = apply_actions([rule], _ctx(tmp_path), kind="after_clone")

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

        bundles = apply_actions(rules, _ctx(tmp_path), kind="after_clone")

        assert [b.index for b in bundles] == [1]

    def test_bundle_carries_predicate_text(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text("# hi")

        rule = ProjectRule(
            when='file_exists("CLAUDE.md")',
            after_clone=[RawAction(action_type="command", args=["echo"])],
        )

        bundles = apply_actions([rule], _ctx(tmp_path), kind="after_clone")

        assert bundles[0].predicate == 'file_exists("CLAUDE.md")'

    def test_default_criticality_is_true(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[RawAction(action_type="command", args=["echo"])],
        )

        bundles = apply_actions([rule], _ctx(tmp_path), kind="after_clone")

        assert bundles[0].critical is True

    def test_explicit_critical_false_is_propagated(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            critical=False,
            after_clone=[RawAction(action_type="command", args=["echo"])],
        )

        bundles = apply_actions([rule], _ctx(tmp_path), kind="after_clone")

        assert bundles[0].critical is False


class TestApplyActionsBuildsTypedObjects:
    """apply_actions must turn RawAction into the correct typed class."""

    def test_command_action_with_template_function_evaluates_context(
        self, tmp_path: Path,
    ) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[
                RawAction(action_type="command", args=["./setup.sh current_worktree()"]),
            ],
        )

        bundles = apply_actions([rule], _ctx(tmp_path), kind="after_clone")

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

        context = _ctx(tmp_path, tags={"prompt": "/review"})
        bundles = apply_actions([rule], context, kind="after_clone")

        action = bundles[0].actions[0]
        assert isinstance(action, CommandAction)
        assert action.command == "claude"
        assert action.args == ["-p", "/review"]

    def test_command_action_with_quoted_args_splits_correctly(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when="True",
            after_clone=[RawAction(action_type="command", args=["echo 'hello world'"])],
        )

        bundles = apply_actions([rule], _ctx(tmp_path), kind="after_clone")

        action = bundles[0].actions[0]
        assert isinstance(action, CommandAction)
        assert action.command == "echo"
        assert action.args == ["hello world"]

    def test_copy_action_built_from_absolute_args(self, tmp_path: Path) -> None:
        """``copy`` with literal absolute source and destination: args pass
        through unchanged (no template functions to evaluate)."""
        rule = ProjectRule(
            when="True",
            after_clone=[
                RawAction(action_type="copy", args=["/tmp/source.txt", "dst.txt"]),
            ],
        )

        bundles = apply_actions([rule], _ctx(tmp_path), kind="after_clone")

        action = bundles[0].actions[0]
        assert isinstance(action, CopyAction)
        assert action.source == "/tmp/source.txt"
        assert action.destination == "dst.txt"

    def test_copy_action_evaluates_source_path_template(
        self, tmp_path: Path,
    ) -> None:
        """``copy`` args go through the template engine: ``source_path('foo')``
        resolves to an absolute path before the action runs."""
        source_file = tmp_path / "marker.txt"
        source_file.write_text("hi")

        rule = ProjectRule(
            when="True",
            after_add=[
                RawAction(
                    action_type="copy",
                    args=["source_path('marker.txt')", "copied.txt"],
                ),
            ],
        )

        bundles = apply_actions([rule], _ctx(tmp_path), kind="after_add")

        action = bundles[0].actions[0]
        assert isinstance(action, CopyAction)
        assert action.source == str(source_file.resolve())
        assert action.destination == "copied.txt"

    def test_copy_action_evaluates_current_worktree_template(
        self, tmp_path: Path,
    ) -> None:
        """``copy``'s second arg is also template-evaluated."""
        source_file = tmp_path / "marker.txt"
        source_file.write_text("hi")
        worktree = tmp_path / "wt"
        worktree.mkdir()

        rule = ProjectRule(
            when="True",
            after_add=[
                RawAction(
                    action_type="copy",
                    args=[
                        "source_path('marker.txt')",
                        "current_worktree('copied.txt')",
                    ],
                ),
            ],
        )

        bundles = apply_actions(
            [rule],
            _ctx(tmp_path, dest_path=worktree),
            kind="after_add",
        )

        action = bundles[0].actions[0]
        assert isinstance(action, CopyAction)
        assert action.source == str(source_file.resolve())
        assert action.destination == str((worktree / "copied.txt").resolve())

    def test_copy_action_evaluates_mixed_static_and_template_text(
        self, tmp_path: Path,
    ) -> None:
        """``copy`` args are preprocessed by the template engine: literal
        text is kept verbatim while a function call inside the same arg
        string is replaced by its return value."""
        source_file = tmp_path / "marker.txt"
        source_file.write_text("hi")

        rule = ProjectRule(
            when="True",
            after_add=[
                RawAction(
                    action_type="copy",
                    args=[
                        f"prefix-{source_file.name}",
                        "copied.txt",
                    ],
                ),
            ],
        )

        bundles = apply_actions([rule], _ctx(tmp_path), kind="after_add")

        action = bundles[0].actions[0]
        assert isinstance(action, CopyAction)
        assert action.source == f"prefix-{source_file.name}"
        assert action.destination == "copied.txt"

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
            apply_actions([rule], _ctx(tmp_path), kind="after_clone")


class TestApplyActionsUriContext:
    """Project rules can reference URI functions in their ``when`` predicates
    once the calling command threads a parsed URI into the evaluation context
    (regression coverage for the bug where ``host()`` raised "No URI context
    available" inside project predicates)."""

    def test_predicate_using_host_function_matches(self, tmp_path: Path) -> None:
        from gww.utils.uri import parse_uri

        rule = ProjectRule(
            when='"somehost" in host()',
            after_clone=[RawAction(action_type="command", args=["echo matched"])],
        )

        uri = parse_uri("https://somehost.example.com/user/repo.git")
        context = _ctx(tmp_path, uri=uri)

        bundles = apply_actions([rule], context, kind="after_clone")

        assert len(bundles) == 1
        action = bundles[0].actions[0]
        assert isinstance(action, CommandAction)
        assert action.command == "echo"
        assert action.args == ["matched"]

    def test_predicate_using_host_function_does_not_match(self, tmp_path: Path) -> None:
        from gww.utils.uri import parse_uri

        rule = ProjectRule(
            when='"somehost" in host()',
            after_clone=[RawAction(action_type="command", args=["echo matched"])],
        )

        uri = parse_uri("https://other.example.com/user/repo.git")
        context = _ctx(tmp_path, uri=uri)

        bundles = apply_actions([rule], context, kind="after_clone")

        assert bundles == []

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
        bundles = apply_actions([rule], context, kind="after_add")

        assert len(bundles) == 1

    def test_predicate_using_branch_function_does_not_match(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when='branch() == "feature/x"',
            after_add=[RawAction(action_type="command", args=["echo"])],
        )

        context = _ctx(tmp_path, branch="main")
        bundles = apply_actions([rule], context, kind="after_add")

        assert bundles == []

    def test_predicate_using_norm_branch_function(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when='norm_branch() == "feature-x"',
            after_add=[RawAction(action_type="command", args=["echo"])],
        )

        context = _ctx(tmp_path, branch="feature/x")
        bundles = apply_actions([rule], context, kind="after_add")

        assert len(bundles) == 1

    def test_empty_branch_evaluates_without_raising(self, tmp_path: Path) -> None:
        """Soft-fail branch detection returns ``""``; predicates still evaluate."""
        rule = ProjectRule(
            when='branch() == ""',
            after_add=[RawAction(action_type="command", args=["echo detached"])],
        )

        context = _ctx(tmp_path, branch="")
        bundles = apply_actions([rule], context, kind="after_add")

        assert len(bundles) == 1

    def test_branch_function_without_context_raises(self, tmp_path: Path) -> None:
        rule = ProjectRule(
            when='branch() == "main"',
            after_add=[RawAction(action_type="command", args=["echo"])],
        )

        with pytest.raises(MatcherError, match="No branch context available"):
            apply_actions([rule], _ctx(tmp_path), kind="after_add")
