# 0020 — One public `run_git`; the test seam is the function, not a fake

Every invocation of the `git` binary routes through a single public function `run_git(args, cwd, *, check=True, pass_through_stdout=False) -> CompletedProcess` in `src/gww/git/repository.py`. This is today's `_run_git` promoted to public and made the one seam: `worktree.py` and `branch.py` import it by its public name instead of a leading-underscore private, and the three `gww clean` bypasses (`_run_git_pass_through`, the raw `subprocess.run` in `_git_merged_branch_set`, and the git-argv calls) route through it. Callers that must abort on failure pass `check=True` (it raises `GitCommandError`); callers that want the exit code without aborting a batch pass `check=False` and read `.returncode` / `.stdout`. We deliberately do **not** build an in-memory git fake — the test seam is "one function to patch," not a simulated git.

## Considered Options

- **Add an in-memory git fake as a second adapter** (the architecture-review "After" diagram) — rejected. A fake that simulates git's porcelain output, exit codes, and stderr text reintroduces exactly the behavioral divergence ADR-0004 paid a process-spawn cost to avoid; it becomes a second, lying implementation of git with its own maintenance surface. The logic worth unit-testing (porcelain parsing, the clean verdict function, summary formatting) is pure or can be made pure without faking git.
- **A richer return type / result object split by raise-vs-exit-code** (e.g. a `RuleRunResult`) — rejected. `CompletedProcess` + the existing `check` flag already spans both contracts; a new type is redundant.
- **A separate new module for the runner** — rejected. `repository.py` already houses the runner and is where the sibling modules import from; a new file is churn without locality gain.

## Consequences

- `_run_git` is renamed to `run_git`; the two cross-module imports and test patch targets (`gww.git.worktree.run_git`) update in lockstep. The privacy marker no longer lies about the cross-module coupling.
- `_run_provider_command` (clean.py) stays out of scope: it runs provider CLIs (`gh`/`glab`/`tea`) via `shell=True` with `set -o pipefail`, not the `git` binary with an argv list. It belongs to the provider layer (ADR-0017/0018) and has different security properties.
- `_git_merged_branch_set` now spawns git through `run_git(check=False)`. A missing git binary surfaces as `GitCommandError` (caught and turned into the existing empty-set fallback by the caller) instead of a bare `FileNotFoundError` — a small, deliberate improvement in error consistency on the `--merged` git-fallback path. The "empty set on non-zero returncode" logic stays in the caller.

## Relationship to ADR-0004

ADR-0004 fixes *subprocess + git binary* as the mechanism. This ADR does not reopen that: it keeps subprocess+git and only consolidates the invocation into one public seam. The rejected in-memory fake is the thing that *would* have eroded ADR-0004's parity guarantee, which is why it is rejected here rather than left open.
