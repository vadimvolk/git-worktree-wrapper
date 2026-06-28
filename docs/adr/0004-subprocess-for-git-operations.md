# 0004 — subprocess to invoke git directly for worktree operations

All git operations — clone, worktree add/remove, status checks, branch listing — are implemented by spawning the `git` binary via `subprocess.run` rather than going through `GitPython` or `pygit2`/`libgit2`. We pay the per-call process-spawn cost in exchange for zero new dependencies, exact behavioral parity with what users see when they run git themselves, and user-friendly stderr messages on failure.

## Considered Options

- **`pygit2` / `libgit2`** — Rejected: native dependency (libgit2 must be present or built), more complex API, occasional behavioral divergences from the `git` binary (especially around worktree edge cases).
- **`GitPython`** — Rejected: similar trade-offs to pygit2 (extra dependency, in-process abstractions) without gaining anything the subprocess path lacks.

## Implementation Notes

- Always pass commands as argv lists (no shell interpolation).
- Use `--porcelain` for stable, parseable output (status checks, listings).
- Honor `--git-dir` and `--work-tree` so worktree operations work correctly from outside the worktree itself.
- Capture stderr and surface it to the user; do not silently swallow git errors.
- `git diff --quiet` is a faster alternative for dirty checks if profiling shows it matters.

## Comparison

| Criteria | subprocess + git | pygit2 / libgit2 |
|---|---|---|
| Dependencies | none (git binary assumed) | pygit2 + libgit2 |
| Performance | slower (process spawn) | faster (in-process) |
| Behavior match | exact (uses same git) | very good, some edge cases |
| Error messages | user-friendly (git's own) | programmatic flags |
| Worktree support | via flags | via repo path |