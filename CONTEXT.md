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

**Project rule evaluation context**:
The :class:`TemplateContext` instance a project rule's `when` predicate and command templates evaluate against. Carries every piece of state that the calling command (`clone` or `add`) actually knows — URI, branch, tags, source path, destination path — so authors can mix `host()`, `branch()`, `tag()`, `file_exists()`, `dest_path()` and friends in the same predicate. Each command populates it from its own operation; see URI-as-seen-by-`clone`-vs-`add` for the asymmetry.
_Avoid_: URI context, action context (too narrow — the context also feeds command templates and tags, not just URI predicates).

**URI as seen by `clone` vs `add`**:
In `clone`, the URI in the project rule context is whatever the user typed on the command line. In `add`, it is whatever `git remote get-url origin` of the source repository returns *now*. If the user later rewrote the remote (`git remote set-url …` from HTTPS to SSH, host rename, etc.), the `clone` rule still sees the original URL while the `add` rule sees the rewritten one. For host-based predicates this rarely matters; for protocol-sensitive predicates it can.

**Branch as seen by `clone` vs `add`**:
In `add`, the branch in the project rule context is the user-supplied branch being checked out in the new worktree. In `clone`, it is whatever branch git checked out by default (the remote's HEAD) after the clone operation completes; if HEAD ends up detached, the value is `""` so predicates evaluate to a defined but non-matching state rather than raising.

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
The grouped failure block printed to stderr at the end of the action loop in `clone`/`add`. Lists one entry per failing action, identified by the rule's config index, the rule's criticality flag, and the failing action's error. Critical rules' loops break after the first failure (so each critical rule appears at most once); non-critical rules appear once per failing action. The non-emptiness of this summary is what gates the `say()` success line: the line is suppressed whenever this summary has any entry, whether critical or non-critical.
_Avoid_: failure report, error log, action error output.

**Checked-out branch**:
A git branch (refs/heads/&lt;name&gt;) that is currently checked out in some worktree of a given source repository. Discovered via `git worktree list --porcelain` (the `branch ` line). Detached-HEAD worktrees are excluded from this set. Informally called a "worktree branch" in some docs, but that conflates the branch with its worktree — keep the canonical term strict.
_Avoid_: worktree branch (informal only), bound branch.
