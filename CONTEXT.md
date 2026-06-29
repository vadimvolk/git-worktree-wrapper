# Git Worktree Wrapper

A CLI that wraps `git worktree` with configurable path templates, condition-based routing, and project-specific post-clone/post-add actions.

## Language

**Quiet mode**:
The state enabled by the `-q` / `--quiet` flag. When on, all subprocess output (git and external commands invoked from `command` actions) is captured, and gww's own status messages printed via `CommandContext.say()` are suppressed. When off (the default), subprocess output streams to the terminal and `say()` lines are visible.
_Avoid_: silent mode, mute, hush.

**Verbose mode**:
The state enabled by the `-v` / `--verbose` flag (repeatable). When on and quiet is off, gww's own diagnostic messages printed via `CommandContext.verbose_msg()` go to stderr. Verbose does not affect subprocess output streaming — that's governed by quiet alone.
_Avoid_: debug mode, loud mode.

**Pass-through stdout**:
A boolean parameter on `_run_git`, `clone_repository`, `pull_repository`, `add_worktree`, `remove_worktree`, `prune_worktrees`, `repair_worktrees`, and `CommandAction.run`. When `True`, the subprocess inherits both stdout and stderr from the parent process (so the user sees git's progress and the external command's output in real time); when `False` (the default for internal checks), both streams are captured into `CompletedProcess`. Used only by user-facing call sites in `clone`/`pull`/`add`/`remove`/`migrate`, which pass `pass_through_stdout=not ctx.quiet`.
_Avoid_: stream stdout (the name is intentionally about the mechanism — *passing the fd through*, not about which stream).

**`say()`**:
`CommandContext.say(message)` writes a status line to stdout, gated on `not quiet`. Used for the final result line of a command (e.g. the path of a freshly-cloned source or added worktree).
_Avoid_: print, log.

**`verbose_msg()`**:
`CommandContext.verbose_msg(message)` writes a diagnostic line to stderr, gated on `verbose > 0 and not quiet`. Used for in-progress narration ("Cloning …", "Executing N actions …").
_Avoid_: debug print, log.

**Subprocess output**:
Anything written to stdout or stderr by a child process spawned by gww — most commonly `git`, but also any external command declared in a `command` action. Visible to the user only when the call site passes `pass_through_stdout=True`. Independent of gww's own messages.
_Avoid_: command output, program output.

**CommandExit**:
Exception raised by a command to terminate with a specific exit code and a stderr message. Converted to a return code by the `@exit_on_error` decorator on each `run_<command>` entry point. Exit code 1 for runtime errors, 2 for configuration errors.
_Avoid_: SystemExit, raise.

**Project rule**:
A single entry from the `actions:` list in the config, evaluated against a `when:` predicate. A rule that matches produces zero or more `after_clone` and `after_add` actions.
_Avoid_: hook, callback.

**Critical rule**:
A project rule with `critical: true` (the default) in the `actions:` config. When any action in a critical rule fails, the command exits 1, the `say()` success line is suppressed, and the failure is reported in the action execution summary. Other rules still run after a critical rule fails.
_Avoid_: required rule, mandatory rule, fatal rule.

**Non-critical rule**:
A project rule with `critical: false`. When an action in a non-critical rule fails, the failure is reported in the action execution summary but the command exits 0. The `say()` success line is still suppressed when the summary is non-empty — criticality affects the exit code, not the success-line policy.
_Avoid_: optional rule, best-effort rule, lenient rule.

**Matcher failure**:
A failure to evaluate a `when:` predicate or `command:` template, raised as `MatcherError` from `gww.actions.apply_actions`. Treated as a configuration error — the command exits 2 with no actions executed, even if the git operation already succeeded.
_Avoid_: template error, evaluation error, predicate failure.

**Action execution summary**:
The grouped failure block printed to stderr at the end of the action loop in `clone`/`add`. Lists each failing rule by index, its criticality flag, and the failing action's error. Its non-emptiness is what gates the `say()` success line: the line is suppressed whenever this summary has any entry, whether critical or non-critical.
_Avoid_: failure report, error log, action error output.

**Checked-out branch**:
A git branch (refs/heads/&lt;name&gt;) that is currently checked out in some worktree of a given source repository. Discovered via `git worktree list --porcelain` (the `branch ` line). Detached-HEAD worktrees are excluded from this set. Informally called a "worktree branch" in some docs, but that conflates the branch with its worktree — keep the canonical term strict.
_Avoid_: worktree branch (informal only), bound branch.
