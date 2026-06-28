"""Execute a :class:`Migration` plan produced by the planner.

The executor has a single inner loop. The only branch between copy and
inplace modes is which :mod:`shutil` operation moves each plan into place;
everything else (parent-directory creation, post-move worktree repair,
already-at-target reporting, summary printing) is shared.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Callable, Literal, Optional

from gww.git.repository import GitCommandError
from gww.git.worktree import (
    read_gitdir,
    repair_worktrees,
    worktree_id_from_gitdir,
)
from gww.migration.planner import Migration, MigrationPlan, Skip

Mode = Literal["copy", "inplace"]

# One shutil callable per mode. ``copytree`` preserves symlinks (matches
# ``shutil -a`` behaviour), ``move`` does a true rename when source and
# destination live on the same filesystem and falls back to copy+remove.
_MOVE: dict[Mode, Callable[[str, str], object]] = {
    "copy": lambda src, dst: shutil.copytree(src, dst, symlinks=True),
    "inplace": shutil.move,
}


def fix_copied_worktree_gitfile(
    new_worktree_path: Path,
    new_source_path: Path,
) -> None:
    """Rewrite a copied worktree's ``.git`` file to point at the new source.

    After :func:`shutil.copytree` the ``.git`` file in the new worktree still
    references the old source's ``.git/worktrees/<id>``. Extract the
    worktree id (using the shared gitfile parser) and point the file at the
    matching directory in ``new_source_path``.

    No-op if ``.git`` is a directory (source repo), missing, unparseable, or
    not of the ``.../worktrees/<id>`` shape.
    """
    git_file = new_worktree_path / ".git"
    gitdir = read_gitdir(git_file)
    if gitdir is None:
        return
    wt_id = worktree_id_from_gitdir(gitdir)
    if wt_id is None:
        return
    new_gitdir = str(new_source_path / ".git" / "worktrees" / wt_id)
    git_file.write_text(f"gitdir: {new_gitdir}\n")


def _format_skipped_items(items: list[Skip]) -> str:
    """Group skips by reason and render a multi-line summary, or empty."""
    if not items:
        return ""

    reason_counts: dict[str, tuple[int, int]] = {}  # reason -> (sources, worktrees)
    for skip in items:
        sources, worktrees = reason_counts.get(skip.reason, (0, 0))
        if skip.is_worktree:
            reason_counts[skip.reason] = (sources, worktrees + 1)
        else:
            reason_counts[skip.reason] = (sources + 1, worktrees)

    total_sources = sum(s for s, _ in reason_counts.values())
    total_worktrees = sum(w for _, w in reason_counts.values())

    lines: list[str] = []
    if total_sources > 0 and total_worktrees > 0:
        src_word = "source" if total_sources == 1 else "sources"
        wt_word = "worktree" if total_worktrees == 1 else "worktrees"
        lines.append(f"Ignored {total_sources} {src_word}, {total_worktrees} {wt_word}:")
    elif total_sources > 0:
        src_word = "source" if total_sources == 1 else "sources"
        lines.append(f"Ignored {total_sources} {src_word}:")
    elif total_worktrees > 0:
        wt_word = "worktree" if total_worktrees == 1 else "worktrees"
        lines.append(f"Ignored {total_worktrees} {wt_word}:")

    for reason, (sources, worktrees) in sorted(reason_counts.items()):
        parts: list[str] = []
        if sources > 0:
            parts.append(f"{sources} source{'s' if sources != 1 else ''}")
        if worktrees > 0:
            parts.append(f"{worktrees} worktree{'s' if worktrees != 1 else ''}")
        lines.append(f"  - {reason}: {', '.join(parts)}")

    return "\n".join(lines)


def _repair_after_move(
    plan: MigrationPlan,
    new_source: Optional[Path],
    verbose: int,
    quiet: bool,
) -> None:
    """Run ``git worktree repair`` for the source that owns this plan."""
    if plan.source_path is None:
        return
    target_source = new_source or plan.source_path
    try:
        if verbose > 0 and not quiet:
            print(f"Repairing worktree paths in {target_source}", file=sys.stderr)
        if new_source is not None:
            repair_worktrees(target_source)
        else:
            repair_worktrees(target_source, [plan.new_path])
    except GitCommandError as e:
        print(
            f"Warning: Failed to repair worktree paths for {plan.new_path}: {e}",
            file=sys.stderr,
        )


def _empty_source_dirs(plans: list[MigrationPlan], roots: list[Path], quiet: bool) -> None:
    """Recursively remove empty directories left behind after inplace moves.

    ``shutil.move`` already removes the moved leaf, so we start walking from
    the first surviving ancestor and remove empty parents up to (but not
    including) the user-supplied input roots.
    """
    if not plans:
        return
    vacated = [p.old_path.resolve() for p in plans]
    roots_set = set(roots)
    # Process deepest paths first so parents can be removed after children.
    vacated_sorted = sorted(vacated, key=lambda p: len(p.parts), reverse=True)
    for start_path in vacated_sorted:
        # If the leaf is already gone (typical), walk up to the first
        # surviving ancestor before attempting cleanup.
        current = start_path
        while current not in roots_set and not current.exists() and current.parent != current:
            current = current.parent
        while True:
            if current in roots_set:
                break
            if not current.exists() or not current.is_dir():
                break
            try:
                if any(current.iterdir()):
                    break
                current.rmdir()
                current = current.parent
            except OSError:
                break


def _resolve_new_source(plan: MigrationPlan, source_plans: list[MigrationPlan]) -> Optional[Path]:
    """If this worktree's source repo is also being migrated, return the new path."""
    if plan.source_path is None:
        return None
    plan_source = plan.source_path.resolve()
    for sp in source_plans:
        if sp.old_path.resolve() == plan_source:
            return sp.new_path
    return None


def _print_summary(
    migrated_sources: int,
    migrated_worktrees: int,
    info_skips: list[Skip],
    already_at_target: list[Path],
    failed: int,
    mode_label: str,
    quiet: bool,
) -> None:
    if quiet:
        return
    if migrated_sources > 0 and migrated_worktrees > 0:
        print(f"{mode_label} {migrated_sources} sources, {migrated_worktrees} worktrees")
    elif migrated_sources > 0:
        print(f"{mode_label} {migrated_sources} sources")
    elif migrated_worktrees > 0:
        print(f"{mode_label} {migrated_worktrees} worktrees")

    skip_msg = _format_skipped_items(info_skips)
    if skip_msg:
        print(skip_msg)

    if already_at_target:
        print(f"Already at target: {len(already_at_target)} repositories")
    if failed:
        print(f"Failed {failed} repositories")


def execute(
    migration: Migration,
    input_roots: list[Path],
    mode: Mode,
    dry_run: bool,
    quiet: bool,
    verbose: int,
) -> int:
    """Execute the planned migrations.

    Args:
        migration: Plan returned by :func:`gww.migration.planner.plan_migration`.
        input_roots: Original input directories (used for inplace cleanup).
        mode: ``"copy"`` to copy, ``"inplace"`` to move.
        dry_run: If ``True``, only print what would happen.
        quiet: If ``True``, suppress non-error output.
        verbose: Verbosity level.

    Returns:
        Exit code (0 for success, 1 if any individual migration failed).
    """
    move = _MOVE[mode]
    mode_verb = "Copying" if mode == "copy" else "Moving"
    mode_label = "Migrated" if mode == "copy" else "Moved"

    if migration.already_at_target and not quiet:
        for path in migration.already_at_target:
            print(f"Already at target: {path}")

    if not migration.plans:
        if not quiet:
            for skip in migration.info_skips:
                print(f"{skip.path}: {skip.reason}")
            print("No repositories to migrate.")
            skip_msg = _format_skipped_items(migration.info_skips)
            if skip_msg:
                print(skip_msg)
            if migration.already_at_target:
                print(f"Already at target: {len(migration.already_at_target)} repositories")
        return 0

    if not quiet:
        for plan in migration.plans:
            kind = "Worktree" if plan.is_worktree else "Source"
            print(f"{kind}: {plan.old_path} -> {plan.new_path}")
        for skip in migration.info_skips:
            print(f"{skip.path}: {skip.reason}")

    if dry_run:
        if not quiet:
            print(f"Would migrate {len(migration.plans)} repositories")
            if migration.info_skips:
                print(f"Would skip {len(migration.info_skips)} repositories")
        return 0

    source_plans = [p for p in migration.plans if not p.is_worktree]
    worktree_plans = [p for p in migration.plans if p.is_worktree]

    migrated_sources = 0
    migrated_worktrees = 0
    failed = 0

    # Worktrees first so the source's .git/worktrees/<id> directory exists
    # in time for the later source moves to be safe (inplace only — copy
    # just rewrites the .git pointer).
    for plan in worktree_plans:
        try:
            if not quiet:
                print(f"{mode_verb} worktree {plan.old_path} -> {plan.new_path}")
            plan.new_path.parent.mkdir(parents=True, exist_ok=True)
            move(str(plan.old_path), str(plan.new_path))
            migrated_worktrees += 1
            new_source = _resolve_new_source(plan, source_plans)
            if mode == "copy" and new_source is not None:
                fix_copied_worktree_gitfile(plan.new_path, new_source)
            _repair_after_move(plan, new_source, verbose, quiet)
        except OSError as e:
            print(f"Error migrating {plan.old_path}: {e}", file=sys.stderr)
            failed += 1

    for plan in source_plans:
        try:
            if not quiet:
                print(f"{mode_verb} repository {plan.old_path} -> {plan.new_path}")
            plan.new_path.parent.mkdir(parents=True, exist_ok=True)
            move(str(plan.old_path), str(plan.new_path))
            migrated_sources += 1
            # Repair the source only if a worktree that referenced it was
            # moved in this run.
            repaired = False
            for wt_plan in worktree_plans:
                if wt_plan.source_path is not None and wt_plan.source_path.resolve() == plan.old_path.resolve():
                    _repair_after_move(plan, None, verbose, quiet)
                    repaired = True
                    break
            del repaired
        except OSError as e:
            print(f"Error migrating {plan.old_path}: {e}", file=sys.stderr)
            failed += 1

    if mode == "inplace":
        _empty_source_dirs(migration.plans, input_roots, quiet)

    _print_summary(
        migrated_sources,
        migrated_worktrees,
        migration.info_skips,
        migration.already_at_target,
        failed,
        mode_label,
        quiet,
    )

    return 1 if failed > 0 else 0