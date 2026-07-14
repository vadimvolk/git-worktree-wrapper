"""Summary formatting and confirmation prompt for ``gww clean``.

Pure IO/formatting: the end-of-execution summary line and the destructive
batch confirmation prompt.
"""

from __future__ import annotations


def _prompt_confirmation(
    filter_label: str,
    provider_label: str | None,
) -> bool:
    """Prompt the user to confirm the destructive batch.

    Reads one line from stdin. ``y`` (case-insensitive, with optional
    leading whitespace) confirms; anything else (including EOF) is a
    decline. The prompt format matches the locked Phase 1 contract from
    the handoff.

    Args:
        filter_label: ``"--merged"`` or ``"--all"`` for the prompt.
        provider_label: Provider kind (``"github"``/...) when
            ``filter_label == "--merged"`` and a provider resolved;
            otherwise ``None`` (renders the bare ``"--merged"`` label).

    Returns:
        ``True`` if the user confirmed with ``y``, ``False`` otherwise.
    """
    label = filter_label
    if filter_label == "--merged" and provider_label:
        label = f"{filter_label} (provider: {provider_label})"
    try:
        answer = input(f"Filter: {label}. Delete matching worktrees? [y/N] ")
    except EOFError:
        return False
    return answer.strip().lower() == "y"


def _format_summary(
    *,
    removed: int,
    kept: int,
    failed: int,
    timed_out: int,
    dry_run: bool,
) -> str:
    """Build the end-of-execution summary line per the locked format.

    Zero counts are omitted for terseness. ``failed`` is always 0 in
    dry-run mode (no side effects ran).

    Args:
        removed: Number of worktrees removed (or "would remove").
        kept: Number of worktrees left in place.
        failed: Number of per-worktree ``git worktree remove`` /
            ``git branch -d`` failures.
        timed_out: Number of per-branch provider-command timeouts.
        dry_run: Whether this is a dry-run summary.

    Returns:
        The summary line, terminated by no trailing newline.
    """
    parts: list[str] = []
    if dry_run:
        parts.append(f"Would remove {removed}; would keep {kept}")
        if timed_out > 0:
            parts.append(f"{timed_out} timed out")
    else:
        parts.append(f"Removed {removed}; kept {kept}")
        if failed > 0:
            parts.append(f"{failed} failed")
        if timed_out > 0:
            parts.append(f"{timed_out} timed out")
    return "; ".join(parts)
