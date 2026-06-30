# 0011 — `before_remove` action kind

A new action section, `before_remove`, joins the existing `after_clone` and `after_add` kinds in the project-rule config. It runs before `git worktree remove` is invoked by `gww remove`, against the worktree that is about to be deleted. The kind reuses the existing per-rule `critical` flag (failing critical → exit 1, no remove; failing non-critical → exit 0, remove still proceeds) and the same three action types (`abs_copy`, `rel_copy`, `command`). `--force` does not bypass or alter `before_remove` execution — it stays a git-only signal. `gww remove` gains `--tag key=value` so `before_remove` predicates can discriminate the same way `clone` and `add` predicates can.

## Why one flag across all kinds

The alternative was a separate per-kind criticality flag (e.g. `blocking: true` for `before_remove`) or hard-coded "always critical" for `before_remove` because removal is destructive. We picked the shared `critical` flag because the matching model is already per-rule, and the user's intent for a rule is one decision ("must succeed / may fail") regardless of when the rule runs. Encoding that decision once keeps the config surface flat and lets users move a rule between `after_*` and `before_remove` without rethinking failure semantics.

## Why `--force` stays git-only

`--force` on `gww remove` currently means exactly one thing: pass `--force` to `git worktree remove` so git will delete a dirty worktree without prompting. Reusing the same flag to mean "skip cleanup" or "treat failures as non-critical" overloads the signal: users who pass `--force` because of a transient git-level dirty state would silently skip their archive step. The clean separation is `--force` = git behavior, `critical: false` = cleanup behavior. Users who genuinely want to bypass cleanup can delete the rule or set `critical: false` on it.

## Why allow all three action types in `before_remove`

The validator has never enforced type-vs-kind compatibility (`after_clone` accepts `rel_copy` even though the only meaningful copy direction is into the source). Maintaining that looseness means `before_remove` accepts `abs_copy`, `rel_copy`, and `command`; the common case is `command("…")` (archive, cleanup, notify), and the rare cases copy into a doomed directory and produce a runtime `ActionError`. Tightening the validator to reject `abs_copy`/`rel_copy` in `before_remove` would surprise users who expect symmetry with `after_*` and would require either a parallel restriction in `after_clone` (also accepting `rel_copy` against the source) or asymmetric enforcement.

## Why `dest_path()` is the worktree, not the source

In `before_remove` the worktree is the directory every meaningful action needs to see — it is what `git worktree remove` is about to delete, what `command("archive", dest_path())` archives, what `rel_copy` would copy out of. Making `dest_path()` resolve to the worktree (with `source_path()` still the source repo, as in `after_add`) keeps the action API uniform: `target_dir` is always the directory the action runs against, and `dest_path()` always names it. The alternative — `dest_path()` resolving to the source repo because the source "survives" — would make actions that need the worktree path call a different accessor than actions in `after_*`, breaking the symmetry that makes `dest_path()` a useful mnemonic.

## Why `gww remove` needs `--tag`

`before_remove` predicates have no other way to be called conditionally on user intent at the time of removal. `branch()`, `host()`, `file_exists()` are all available, but none of them carry "I am about to delete this and want it archived only when I asked for archival" — that intent is only knowable from a CLI flag. Without `--tag`, users would have to encode "archive on delete" in a one-off script that runs `command("…")` directly, defeating the purpose of declarative rules.

## Why read branch from the worktree when removing by path

`gww remove` accepts both `<branch>` and `<path>`. When the user gives a path, `branch()` would otherwise be `None` and any `before_remove` predicate referencing it would raise — forcing the user to invoke by branch to make cleanup work, which is a regression from today's surface. Reading the branch from `git -C <worktree> rev-parse --abbrev-ref HEAD` (with the same `""`-on-detached-HEAD soft-fail policy `clone` uses) keeps `branch()` always meaningful and lets predicates work identically whether the user invoked `gww remove feature` or `gww remove ~/Developer/worktrees/proj/feature`.

## Considered Options

- **Reuse `critical` flag across all kinds.** Chosen — see above.
- **Always-critical for `before_remove`.** Rejected: removal is destructive but cleanup failure is not always user-blocking (e.g. notification-only steps). Forcing critical on every rule removes user choice without buying safety — users who want blocking can already set `critical: true`.
- **Separate `blocking` flag for `before_remove`.** Rejected: doubles the vocabulary for one decision the user already has a knob for.
- **`--force` skips `before_remove`.** Rejected: overloading a git-level flag with a gww-level meaning.
- **`--force` downgrades criticality.** Rejected: same overloading concern, in a sneakier form.
- **Restrict `before_remove` to `command` only.** Rejected: breaks validator symmetry, surprising to users, no real safety win.
- **Make `dest_path()` resolve to the source repo in `before_remove`.** Rejected: makes the most useful actions (`command("archive", dest_path())`) call the wrong accessor.
- **Refuse `before_remove` when user passes a path.** Rejected: regresses the existing `gww remove <path>` surface for no benefit; reading branch from the worktree solves the underlying need.
- **Ship `before_remove` without `--tag` on `gww remove`.** Rejected: leaves `before_remove` predicates without a way to express user-intent-at-removal-time, which is the dominant use case.

## Consequences

- The `ActionKind` literal grows from two to three members; existing configs remain valid because `before_remove` is optional.
- `gww remove`'s argparse gains `--tag` (repeatable); shell completion scripts need updating to advertise it.
- `gww remove`'s `CommandContext` gains a `tags` field (or relies on the same `parse_tags` helper that other commands use); the per-invocation `TemplateContext` for `before_remove` populates it.
- A new `try_get_current_branch`-style helper is needed for the path-based branch lookup (or reuse of the existing one), with the same detached-HEAD soft-fail.
- The action execution summary now appears in `gww remove` too; failure semantics on `remove` exit non-zero match `clone`/`add` (1 for critical, 0 for non-critical with summary suppressed-success-line policy not applicable here because `remove` does not print a path on success).