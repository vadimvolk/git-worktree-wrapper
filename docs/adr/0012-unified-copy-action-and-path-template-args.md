# 0012 — Unified `copy` action and path-template args

Two former action shapes (`abs_copy` for absolute-path sources, `rel_copy` for source-repo-relative sources) are replaced by a single `copy` action that takes template-evaluated `from` and `to` arguments. Two former template functions (`source_path()` cwd-based and `dest_path()`) are unified into context-based `source_path(extra?)` and `current_worktree(extra?)`. Configuration authors express both former flows (and a third — directory-tree copies) through one action whose `from` is whatever template they choose (`source_path('foo')`, `current_worktree('bar')`, an absolute literal, …) and whose `to` is the destination they want.

## Why unify into one action

The `abs_copy` / `rel_copy` split encoded the *base directory* of the source (`abs_copy` = any absolute path; `rel_copy` = `source_dir / self.source`) rather than the user's intent. Once `source_path(extra?)` and `current_worktree(extra?)` resolve to absolute paths, the `rel_copy` flavour becomes `copy: ["source_path('foo')", "dest.txt"]` and the `abs_copy` flavour becomes `copy: ["/abs/path", "dest.txt"]` or `copy: ["~/path", "dest.txt"]` — different only in the template, not in the action. Keeping two action classes forces the user to pick *up front*, when the right answer depends on the rule.

Also: users reaching for "inherit this file from the repo into every worktree" had to know that `rel_copy` did that and `abs_copy` did not — a non-obvious mapping. With `source_path('local.properties')` the rule reads as English ("from the source's `local.properties`").

## Why directory support in the same `copy` action

Once the action takes a template-evaluated `from` rather than a hard-coded `Path(self.source) / source_dir`, the only thing distinguishing files from directories in the implementation is `shutil.copy2` vs `shutil.copytree`. Hiding that distinction in a separate `dir_copy` action type would force users to write "is it a file or a directory?" in their config — answering a question the file system already knows. The selection is by resolved source type (`is_file()` → `copy2`; `is_dir()` → `copytree`), not by action name.

Three consequences fall out:

1. Files copy with `shutil.copy2`, which silently overwrites an existing destination file — preserving the existing `abs_copy` / `rel_copy` behaviour for the file case.
2. Directories copy with `shutil.copytree(src, dst, dirs_exist_ok=True)`, which merges into an existing destination directory — the closest analog to "silent overwrite" for trees. Plain `copytree` (fails on existing dest) forces the user to clean up before each worktree add, which is the wrong default for the "share config across worktrees" use case.
3. The destination's parent is created with `mkdir(parents=True, exist_ok=True)` before either operation — same behaviour the existing actions had.

## Why rename `dest_path()` to `current_worktree()` and add optional-arg signatures

`dest_path()` was named after the `Action` protocol's `target_dir` parameter — plumbing rather than concept. From a user's perspective, `dest_path()` is always the worktree they are acting on: for `after_clone`, where source and destination coincide, it is the freshly-cloned source; for `after_add`, it is the newly-added worktree. `current_worktree()` reads as "the worktree I am in / configuring"; `dest_path()` reads as "the destination parameter". The rename is pure vocabulary; the implementation is unchanged.

The optional-`extra` argument on both `source_path` and `current_worktree` lets a template like `npm install --prefix current_worktree()` (root path) and `cp source_path('local.properties') current_worktree('local.properties')` (joined path) be expressed with the same calling form. Treating empty-string `extra` as "no join" (`current_worktree('') == current_worktree()`) keeps the call symmetric and lets users feed it from `tag('relpath')` without gating on `tag_exist`.

The former cwd-based `source_path()` (which descended from `Path.cwd()` to find the enclosing git repo) is removed. Its behaviour was the *opposite* of what `current_worktree()` needs — cwd-based "what repo am I in" cannot answer "what source repo does this `gww clone / add` operation target", and the context already carries that. Anyone needing the old semantics in a templates context can compose `host() + path(-2) + path(-1)` plus a config-side source path; documenting it as a fallback is not worth the extra function.

## Uniform semantics across operations

Both path-bearing helpers follow a fixed mapping that does not vary by operation:

- `source_path(extra?)` is `context.source_path` (optionally joined with `extra`).
- `current_worktree(extra?)` is `context.dest_path` (optionally joined with `extra`).

Neither function aliases the other under any condition. They may resolve to the same path string during `gww clone` — because the CLI populates *both* context fields with the clone target (ADR-0009, "What is available per operation" table) — but that is a CLI-side decision, not a function-side alias. They diverge in `gww add` and `gww remove` because the CLI populates `context.source_path` with the source repo and `context.dest_path` with the worktree (added or being removed). The mapping itself never changes.

This principle absorbs and supersedes the per-operation decisions that the old `dest_path()` had to navigate. For `before_remove` specifically, the decision in [ADR-0011 ("Why `dest_path()` is the worktree, not the source")](0011-before-remove-action-kind.md) — that the worktree being deleted is what `dest_path()` names, with `source_path()` still pointing at the source repo — survives the rename unchanged, phrased in the new vocabulary: `current_worktree()` is the worktree being removed; `source_path()` is its parent source repo. The asymmetry is preserved verbatim.

`current_worktree()` does **not** fall back to `source_path()` when `context.dest_path` is `None`. The fallback the old `dest_path()` carried was a defensive default for non-project evaluation sites where `dest_path` could be unset. Re-introducing it under the new name would re-introduce the aliasing that this section rules out. Both functions are project-only; the calling command (`clone`, `add`, `before_remove`) always populates `dest_path` before invoking project predicates; the fallback is dead code and is removed.

## What is available where

Both new functions live in `create_project_functions` (project-only), as before. They are **not** added to the universal `FunctionRegistry`:

| Context | `source_path()` | `current_worktree()` |
|---|---|---|
| Project-rule `when` predicates | source repo path | target of the operation |
| Project-rule `command` templates | source repo path | target of the operation |
| Source-rule `when` predicates | not registered | not registered |
| `default_sources` / `default_worktrees` templates | not registered | not registered |

Source-rule predicates and the default path templates evaluate *before* the git operation runs — there is no source repo or worktree yet to point at. Documenting the functions as project-only matches where the user can use them and avoids defining a behaviour for an undefined-context case.

## Considered Options

- **Keep `abs_copy` and `rel_copy` as deprecated aliases of `copy`.** Rejected: doubles the test matrix (every test still has to cover the old shapes), keeps `_describe_action` returning `"abscopy"`, and is the kind of half-life a feature never sheds.
- **Separate `dir_copy` action for directories.** Rejected: pushes a "is this a file or a directory?" decision onto the user that the file system already knows.
- **`shutil.copytree` with the default `dirs_exist_ok=False` (error on existing dest).** Rejected: forces the user to delete or rename each inherited directory before every `gwa` run, which defeats the "share config across worktrees" use case.
- **Drop `dest_path()` quietly; only register `current_worktree()`.** Rejected: leaves users on a current commit with broken configs that suddenly do not evaluate. Pure rename with no alias is the gentler migration.
- **Add the optional-arg signatures as new functions (`source_path_at`, `worktree_at`).** Rejected: doubles the registry for no benefit. The signature change is additive (existing `source_path()` callers keep working), so widening in place is strictly cheaper.

## Notes for future readers

- `_describe_action` in `src/gww/cli/context.py` strips the `Action` suffix from the class name and lowercases — `CopyAction` → `"copy"` in failure messages, matching the YAML action type. That incidentally also fixes the existing `"abscopy"` label that the same code produced for `AbsCopyAction`.
- `Action.run()` still carries the `source_dir: Optional[Path]` parameter even though `CopyAction` and `CommandAction` both ignore it — kept to avoid touching the call sites in `gww/cli/commands/{clone,add}.py` as part of this refactor. A future cleanup could drop it; intentionally out of scope here.
- The destination for `copy` is always relative to `current_worktree()` when written as a relative path; an absolute destination path bypasses the relative resolution. This matches how `shutil.copy2` / `shutil.copytree` resolve `dst` and mirrors the existing `abs_copy` semantics for absolute destinations.
