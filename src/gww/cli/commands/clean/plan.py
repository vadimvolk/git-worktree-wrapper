"""Worktree enumeration and candidate filtering for ``gww clean``.

Turns ``git worktree list`` into the set of branches eligible for cleaning,
excluding the main checkout, bare/detached worktrees, the default branch, and
any protected main branch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from gww.cli.context import CommandExit
from gww.git.branch import get_default_branch, is_main_branch
from gww.git.repository import GitCommandError
from gww.git.worktree import Worktree, list_worktrees


def _resolve_default_branch(source_path: Path) -> str:
    """Return the source's default branch name (``main`` / ``master``).

    Used both as the comparison branch for the ``--merged`` git fallback
    and as the filter that excludes the main checkout from the cleanable
    set. Falls back to the heuristic from :func:`get_default_branch`.

    Args:
        source_path: Path to the source repository.

    Returns:
        ``"main"`` or ``"master"`` -- whichever exists locally; the
        remote ``origin`` is consulted if neither local branch exists.

    Raises:
        CommandExit: With code 1 if the source has neither ``main`` nor
            ``master`` locally or on ``origin`` -- a configured but
            broken repo.
    """
    try:
        return get_default_branch(source_path)
    except Exception as e:  # BranchError or GitCommandError
        raise CommandExit(
            1,
            f"Error: Could not determine default branch for {source_path}: {e}",
        ) from e


def _enumerate_worktrees(source_path: Path) -> list[Worktree]:
    """Return the worktrees attached to ``source_path``.

    The first entry of ``git worktree list --porcelain`` is the source
    repository itself (the "main checkout"); callers filter it out via
    :meth:`Worktree.is_bare` / path comparison, not here, so that policy
    lives in one place.

    Args:
        source_path: Path to the source repository.

    Returns:
        List of :class:`gww.git.worktree.Worktree` objects in source
        iteration order.

    Raises:
        CommandExit: With code 1 if the worktree listing fails.
    """
    try:
        return list_worktrees(source_path)
    except GitCommandError as e:
        raise CommandExit(1, f"Error listing worktrees: {e}") from e


def _main_checkout_path(source_path: Path) -> Path:
    """Return the main checkout path -- the entry that is never cleanable.

    Args:
        source_path: Path to the source repository (already the "main"
            checkout by construction).

    Returns:
        Resolved source path.
    """
    return source_path.resolve()


def _is_main_worktree(worktree_path: Path, main_path: Path) -> bool:
    """Test whether ``worktree_path`` is the source's main checkout.

    Resolves symlinks / ``..`` segments on both sides before comparing so
    the test holds even when one path is reached via different
    components.

    Args:
        worktree_path: Path of the worktree being considered.
        main_path: Resolved path of the source's main checkout.

    Returns:
        ``True`` if the worktree IS the main checkout.
    """
    try:
        return worktree_path.resolve() == main_path
    except OSError:
        return False


@dataclass(frozen=True)
class CandidatePlan:
    """Worktrees eligible for cleaning, with their branch->path mapping.

    Attributes:
        default_branch: The source's default branch (main/master), excluded
            from candidates and used as the --merged git-fallback base.
        branches: Candidate branch names, in worktree iteration order.
        worktree_by_branch: Branch name -> worktree path. Git enforces one
            worktree per branch, so keys never collide.
    """

    default_branch: str
    branches: list[str] = field(default_factory=list)
    worktree_by_branch: dict[str, Path] = field(default_factory=dict)


def build_candidate_plan(source_path: Path, main_path: Path) -> CandidatePlan:
    """Enumerate worktrees and filter to cleanable candidates.

    Excludes: the main checkout, bare/detached worktrees, the default branch,
    and any main branch (:func:`is_main_branch`).

    Args:
        source_path: Path to the source repository.
        main_path: Resolved path of the source's main checkout.

    Returns:
        A :class:`CandidatePlan` with the default branch and candidate mapping.

    Raises:
        CommandExit: code 1 if worktree listing or default-branch resolution
            fails (propagated from :func:`_enumerate_worktrees` /
            :func:`_resolve_default_branch`).
    """
    default_branch = _resolve_default_branch(source_path)
    worktrees = _enumerate_worktrees(source_path)

    branches: list[str] = []
    worktree_by_branch: dict[str, Path] = {}
    for wt in worktrees:
        if _is_main_worktree(wt.path, main_path):
            continue
        if wt.is_bare or wt.is_detached:
            continue
        if wt.branch is None or wt.branch == default_branch:
            continue
        if is_main_branch(wt.branch):
            continue
        branches.append(wt.branch)
        worktree_by_branch[wt.branch] = wt.path

    return CandidatePlan(
        default_branch=default_branch,
        branches=branches,
        worktree_by_branch=worktree_by_branch,
    )
