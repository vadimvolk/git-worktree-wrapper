"""Unit tests for CLI argument parsing on the ``remove`` command.

Confirms that ``--tag`` is accepted on ``gww remove`` and propagated into the
:class:`CommandContext.tags` mapping. This is the parser side of the
``before_remove`` action plumbing — actions predicates may rely on
``tag('foo')`` once the worktree is being removed.

Mirrors the existing ``clone``/``add`` parser behaviour: ``--tag`` is
repeatable and accepts both ``key=value`` and bare-key forms.
"""

from __future__ import annotations

from gww.cli.context import CommandContext
from gww.cli.main import create_parser


class TestRemoveCommandTagParsing:
    """``gww remove`` must accept ``--tag key=value`` arguments."""

    def test_remove_without_tag(self) -> None:
        parser = create_parser()
        args = parser.parse_args(["remove", "feature"])

        ctx = CommandContext.from_args(args)

        assert ctx.branch_or_path == "feature"
        assert ctx.tags == {}

    def test_remove_with_single_tag(self) -> None:
        parser = create_parser()
        args = parser.parse_args(["remove", "feature", "--tag", "keep=archive"])

        ctx = CommandContext.from_args(args)

        assert ctx.tags == {"keep": "archive"}

    def test_remove_with_multiple_tags_accumulate(self) -> None:
        parser = create_parser()
        args = parser.parse_args([
            "remove",
            "feature",
            "--tag", "keep=archive",
            "--tag", "env=prod",
            "-t", "bare",
        ])

        ctx = CommandContext.from_args(args)

        assert ctx.tags == {"keep": "archive", "env": "prod", "bare": ""}

    def test_remove_with_force_and_tag(self) -> None:
        """``-f`` and ``--tag`` must coexist."""
        parser = create_parser()
        args = parser.parse_args([
            "remove", "feature", "--force", "--tag", "k=v",
        ])

        ctx = CommandContext.from_args(args)

        assert ctx.force is True
        assert ctx.tags == {"k": "v"}