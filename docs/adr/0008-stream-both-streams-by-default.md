# 0008 — Stream both git and external-command output by default, capture under `-q`

By default (no `-q`) every user-facing subprocess invocation in gww — `git clone`, `git pull`, `git worktree add`, `git worktree remove`, `git worktree repair`, and any external command declared in a `command` action — inherits both stdout and stderr from the parent process, so the user sees git's progress (`Cloning into '…'`, `Receiving objects: 100%`, `Preparing worktree (new branch 'X')`, `Already up to date.`, …) in real time. Under `-q` / `--quiet` the same calls capture both streams into `CompletedProcess`, restoring the historic silent behavior. The threading is done with a single boolean parameter, `pass_through_stdout`, on `_run_git`, `clone_repository`, `pull_repository`, `add_worktree`, `remove_worktree`, `prune_worktrees`, `repair_worktrees`, and `CommandAction.run`. CLI commands compute `pass_through_stdout=not ctx.quiet` once and forward it.

## Why both streams, not just stdout

We initially picked a hybrid — stream stdout, capture stderr — so `GitCommandError` could keep embedding git's stderr text on failure. Implementation showed that assumption was wrong: `git clone` writes `Cloning into '…'` and `done.` to **stderr**, and `git worktree add` writes `Preparing worktree (new branch 'X')` to **stderr**. Streaming stdout alone would have hidden the very progress lines users care about for the two loudest commands (`clone`, `add`), while `git pull` — the one command that does put progress on stdout — would have streamed. So the rule is symmetric: when streaming, stream both.

The trade-off is that on failure, `GitCommandError` no longer embeds the captured stderr text — only the command line and exit code. We accepted that because the user already saw the stderr scroll past in real time, so re-printing it would be redundant; the failure path still surfaces through `CommandExit` which writes the message to stderr, preserving the contract from ADR-0004.

## Considered Options

- **Capture both streams always (the prior default).** Rejected: hides git's progress by default, which is the behavior the user wanted to invert. Surfaces only via error messages after the fact, which is the wrong moment — the user has already moved on.
- **Hybrid — stream stdout, capture stderr.** Rejected: git writes user-facing progress to both streams depending on the subcommand; capturing stderr silently drops `Cloning into '…'`, `done.`, and `Preparing worktree (new branch 'X')`. Would have shipped a bug.
- **Tee (capture AND pass through both streams).** Rejected: requires `Popen` + threads or non-blocking reads to copy each stream into a buffer while also writing to the terminal. More moving parts, no observable benefit beyond preserving the embedded stderr in `GitCommandError` — a benefit the user already gets for free by seeing the stderr in real time.
- **Merge stderr into stdout via `stderr=subprocess.STDOUT`, then stream the merged stream.** Rejected: still needs the tee pattern to both display and capture, so it collapses back into the previous option without simplifying anything. Also destroys the stdout/stderr separation that downstream tooling (loggers, CI) might rely on.

## Notes for future readers

- `pass_through_stdout` is threaded explicitly through every wrapper function, not via a thread-local or context-var. The cost is a few extra parameters; the benefit is that each call site reads as a deliberate choice rather than depending on hidden ambient state.
- The `_run_git` parameter name is `pass_through_stdout`, not `stream_stdout` or `pass_through`. We considered renaming it again but settled on the name because it describes the mechanism (passing the file descriptor through to the parent) rather than the audience ("show to user"), which leaves room for future fine-grained control without another rename.
- The default for internal quick checks (`rev-parse --abbrev-ref HEAD`, `status --porcelain`, `branch --list`) is unchanged: `pass_through_stdout=False`, both streams captured. These calls produce no user-visible output either way, but capturing is faster and prevents spurious lines from leaking through if a future git version changes what it prints.
