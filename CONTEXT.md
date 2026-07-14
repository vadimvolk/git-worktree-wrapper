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
A boolean parameter on `run_git` (the single public git runner; see ADR-0020), `clone_repository`, `pull_repository`, `add_worktree`, `remove_worktree`, `prune_worktrees`, `repair_worktrees`, and `CommandAction.run`. When `True`, the subprocess inherits both stdout and stderr from the parent process (so the user sees git's progress and the external command's output in real time); when `False` (the default for internal checks), both streams are captured into `CompletedProcess`. Used only by user-facing call sites in `clone`/`pull`/`add`/`remove`/`migrate`, which pass `pass_through_stdout=not ctx.quiet`.
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
A single entry from the `actions:` list in the config, evaluated against a `when:` predicate. A rule that matches produces zero or more `after_clone`, `after_add`, or `before_remove` actions.
_Avoid_: hook, callback.

**Project rule evaluation context**:
The :class:`TemplateContext` instance a project rule's `when` predicate and command templates evaluate against. Carries every piece of state that the calling command (`clone`, `add`, or `before_remove`) actually knows — URI, branch, tags, source path, destination path — so authors can mix `host()`, `branch()`, `tag()`, `file_exists()`, `current_worktree()` and friends in the same predicate. Each command populates it from its own operation; see URI-as-seen-by-`clone`-vs-`add`, Branch-as-seen-by-`clone`-vs-`add`, and Paths-as-seen-by-`clone`-vs-`add`-vs-`remove` for the asymmetries. Path-bearing helpers available here are `source_path(extra?)` (`context.source_path`, optionally joined with `extra`) and `current_worktree(extra?)` (`context.dest_path`, optionally joined with `extra`) — both project-only, neither registered in source-rule predicates or `default_sources`/`default_worktrees` path templates, because those evaluate before the git operation has produced a source or a target. The mapping from helper to context field is fixed across operations; any coincidence or divergence between the two helpers is a property of what the CLI populated, never an aliasing inside the helper itself.
_Avoid_: URI context, action context (too narrow — the context also feeds command templates and tags, not just URI predicates).

**Copy action**:
A project action that copies a file or directory tree. Takes two template-evaluated arguments, `from` and `to`, with the implementation selecting the operation by the source's resolved type: `shutil.copy2` (silent overwrite) when the source is a file, `shutil.copytree(src, dst, dirs_exist_ok=True)` (merge into an existing destination) when the source is a directory. The destination is interpreted relative to `current_worktree()` when written as a relative path; an absolute destination bypasses that resolution. Missing source raises `ActionError`; the destination's parent is created with `mkdir(parents=True, exist_ok=True)` before either operation runs.
_Avoid_: `abs_copy`, `rel_copy` (removed).

**URI as seen by `clone` vs `add`**:
In `clone`, the URI in the project rule context is whatever the user typed on the command line. In `add`, it is whatever `git remote get-url origin` of the source repository returns *now*. If the user later rewrote the remote (`git remote set-url …` from HTTPS to SSH, host rename, etc.), the `clone` rule still sees the original URL while the `add` rule sees the rewritten one. For host-based predicates this rarely matters; for protocol-sensitive predicates it can.

**Branch as seen by `clone` vs `add`**:
In `add`, the branch in the project rule context is the user-supplied branch being checked out in the new worktree. In `clone`, it is whatever branch git checked out by default (the remote's HEAD) after the clone operation completes; if HEAD ends up detached, the value is `""` so predicates evaluate to a defined but non-matching state rather than raising.

**Critical rule**:
A project rule with `critical: true` (the default) in the `actions:` config. When any action in a critical rule fails, the command exits 1, the `say()` success line is suppressed, and the failure is reported in the action execution summary. Other rules still run after a critical rule fails. For `before_remove`, a critical-rule failure additionally skips the `git worktree remove` step entirely — the worktree is preserved because its pre-deletion cleanup did not finish.
_Avoid_: required rule, mandatory rule, fatal rule.

**Non-critical rule**:
A project rule with `critical: false`. When an action in a non-critical rule fails, the failure is reported in the action execution summary but the command exits 0. The `say()` success line is still suppressed when the summary is non-empty — criticality affects the exit code, not the success-line policy. For `before_remove`, a non-critical-rule failure does not block the `git worktree remove` step; the worktree is still removed even though the cleanup step reported a warning.
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

**`before_remove`**:
A third section in a project rule, sibling of `after_clone` and `after_add`. Holds actions that run *before* `git worktree remove` is invoked by `gww remove`, against the worktree that is about to be deleted. Uses the same per-rule `critical` flag as the `after_*` sections — a failing critical rule aborts the remove; a failing non-critical rule is reported but the remove still proceeds. `--force` does NOT bypass or alter `before_remove` execution; it continues to mean "pass `--force` to `git worktree remove`". The section accepts the same action types as `after_*` (`copy`, `command`) — copying into a doomed directory is unusual but the validator does not enforce type-vs-kind compatibility (runtime `ActionError` if it can't do its job).
_Avoid_: pre_remove, on_remove, remove hook, cleanup hook.

**Branch as seen by `gww remove`**:
For `before_remove` predicates, `branch()` is the branch checked out in the worktree being removed. When the user passes a branch name on the CLI, that branch is used. When the user passes an absolute path, `git -C <worktree_path> rev-parse --abbrev-ref HEAD` is read; if HEAD is detached, the value is `""` so predicates evaluate to a defined but non-matching state — mirroring the soft-fail-on-detached-HEAD policy of `clone`.

**`gww remove` `--tag`**:
Repeatable `key=value` flag on `gww remove`, mirroring `clone` / `add`. Feeds `tag()` and `tag_exist()` in `before_remove` predicates; absent tags default to empty. Tags do NOT affect path resolution (none happens for `remove`) and do NOT affect the `git worktree remove` step; their only purpose is to make `before_remove` predicates discriminating.

**Paths as seen by `clone` vs `add` vs `remove`**:
For project predicates, `source_path()` is `context.source_path` and `current_worktree()` is `context.dest_path` — uniformly. The CLI populates the two context fields per operation:

| Operation | `context.source_path` | `context.dest_path` |
|---|---|---|
| `clone` | the freshly-cloned source repo | the same path (clone target = source) |
| `add` | the source repo | the worktree being added |
| `before_remove` | the source repo | the worktree being removed |

So `source_path()` and `current_worktree()` happen to coincide in `clone` and diverge in `add` / `before_remove`. The coincidence during `clone` is a CLI-side property of how the calling command populates the context, NOT an aliasing inside either helper — neither function ever substitutes the other for its caller. See ADR-0012 §"Uniform semantics across operations" for the principle that supersedes the now-obsolete `dest_path()`-side aliasing decisions.

**Prompt repaint**:
The `commandline -f repaint` line at the end of every generated fish alias (`gwc`, `gwa`, `gwr`). It queues fish's `repaint` input function, forcing the prompt to redraw after the alias returns. Bash and zsh generated aliases do not include this call: their prompts re-evaluate automatically on the next command and have no equivalent queue-based repaint primitive. The fish call appears inside every terminal branch of each alias — before every `return` and at the tail of every return-less branch — so it fires regardless of which branch the alias took (success, force-accept, force-decline, error-return). Placing it earlier than the work that changed prompt-relevant state (the `cd` for `gwc`/`gwa`; the `git worktree add/remove` for all three, since the prompt may render derived state such as the worktree count) would repaint against a still-stale prompt. See ADR-0013.
_Avoid_: redraw, refresh (less precise about the queueing mechanism); `$PWD reset` (the issue is not the variable — fish has updated it — but the on-screen prompt render).

## Cleanup

**`gww clean`**:
A subcommand of the ``gww`` CLI that removes worktrees and their local branches from the current source repository. Operates on the source repo detected from CWD; if CWD is a worktree, the source is detected via the existing walk-back (see ``gww remove``) and ``gww clean`` runs against that source. Lists cleanable worktrees by walking every worktree in the source. The current source's main checkout is *never* cleanable.
_Avoid_: ``gww cleanup``, ``gww prune`` (the latter collides with ``git worktree prune``), ``gww delete``.

**Cleanable worktree**:
A worktree that ``gww clean`` will consider for removal. Defined as a worktree in the current source whose branch (a) is not the source's default branch (main/master), and (b) satisfies the active filter (see ``--merged``, ``--all``). ``git worktree remove`` may still refuse a cleanable worktree whose branch is checked out in another worktree — that refusal is one of the per-worktree git failures handled by the failure-mode policy (silent at the per-branch level, exit 1 if any). We deliberately do not pre-filter for this; in practice git itself prevents two worktrees from having the same branch checked out (``git checkout`` refuses), so the defensive check is virtually never false and ``git worktree remove``'s refusal path is already covered. A worktree may be cleanable conceptually but still blocked by ``--dry-run`` or by an interactive confirmation that hasn't been answered yes.
_Avoid_: stale worktree (overloaded with git's own "stale worktree" semantics from ``git worktree prune``).

**`--merged` filter**:
The default filter for ``gww clean``. Marks as cleanable (see *Cleanable worktree*, i.e. eligible for removal) only worktrees whose branch has an upstream merge request in the ``merged`` state — equivalently, ``--merged`` **removes** merged-MR worktrees and **keeps** the rest. When no provider is configured and the origin host doesn't auto-resolve to one, falls back silently to git's "fully merged into default branch" check (``git branch --merged <default>``); the user-visible flag stays ``--merged`` in both cases (see ADR-0015). A worktree whose branch has no MR at all (e.g. ``wip/foo``) is not cleanable and stays in the source: silent keep is the contract, regardless of fallback path.
_Avoid_: ``--merged-into-default`` (overloads the git fallback into the flag name), ``--mr-merged`` (Provider-side-only; we don't want to bake provider-awareness into the flag name).

**`--all` filter**:
Disables MR-status checks for ``gww clean``: every cleanable worktree in the source is listed and subject to confirmation. Used both as a "trust git to be the source of truth" mode (when no provider is configured) and as a "I want to sweep everything" mode when combined with ``-y``. Also the only way to clean up a branch whose MR was *closed-not-merged* (abandoned, superseded, won't-fix): those branches fail the provider's ``merged`` command and so are skipped by ``--merged``; ``gww remove <branch>`` is the per-worktree alternative when the user wants them gone.

**`--dry-run`**:
A boolean flag on ``gww clean`` that suppresses both the deletion of the worktree (``git worktree remove``) and the deletion of the local branch (``git branch -d``), while still walking the source and printing what *would* be removed. Has no effect on gww's own status messages (``say()``, ``verbose_msg()``) — only on whether side effects run. Does not require a provider: dry-runs work even when the filter is the git-fallback path.

**`--yes` / `-y`**:
A boolean flag on ``gww clean`` that suppresses the batch confirmation prompt (the ``Filter: --merged (provider: github). Delete matching worktrees? [y/N]`` line). Independent of ``--dry-run`` (use both for a non-interactive preview). Has no effect on gww's status output — only on whether the prompt is shown. See *Cleanup confirmation* for the prompt that this flag bypasses.

**`--force`**:
A boolean flag on ``gww clean`` that escalates two git-level refusals: passes ``--force`` to ``git worktree remove`` (allowing dirty worktrees) and uses ``git branch -D`` instead of ``-d`` (forcing branch deletion even if git's local merge check would refuse). Does NOT escalate the MR filter — to bypass ``--merged`` use ``--all``. Does NOT cause remote-branch deletion or push-deletion; those never happen in ``gww clean``.

**Cleanup confirmation**:
The interactive prompt ``Filter: --merged (provider: github). Delete matching worktrees? [y/N]`` issued once per ``gww clean`` run after the plan is printed and before any deletion. The ``--merged`` token becomes ``--all`` when that filter is active; the ``(provider: <kind>)`` suffix appears only when ``--merged`` is the active filter AND a provider resolved, otherwise the prompt is just ``Filter: --merged. Delete matching worktrees? [y/N]``. Triggered on stdin EOF or non-``y`` answer: the command exits 0 having printed the plan but with no side effects. Skipped by ``--yes``/``-y``.

**Cleanable worktree side-effects**:
The package of operations ``gww clean`` performs per *surviving confirmation* cleanable worktree, in order: (1) ``before_remove`` project-rule actions run with the same criticality semantics as ``gww remove`` (a failing critical rule aborts the per-worktree pass for that worktree only, the rest of the batch continues); (2) ``git worktree remove <path>`` (refuses if dirty unless ``--force``); (3) ``git branch -d <branch>`` after the worktree is gone (refuses if branch not locally merged unless ``--force``, in which case ``-D``). Remote-tracking refs and remote branches are never touched by ``gww clean``.

**Provider command outcome (exit-code-only contract, locked 2026-07-13)**:
The action contract: provider exit 0 marks the worktree as cleanable (will be removed); provider exit non-0 leaves the worktree in place. No abort, no retry, no parse — the exit code is the entire signal; gww does not interpret the provider's stdout or stderr to disambiguate sub-cases of non-zero. Two exceptions get per-branch gww-generated labels (these are gww's own output, not parsing of the provider's streams): subprocess timeout (60s exceeded) → ``X: skip (timeout)``; FileNotFoundError (provider CLI not installed, e.g. ``gh not found``) → ``X: skip (<command> not found)`` with the actual command name. Any other exception is silent (treated as non-zero → keep). Provider stdout and provider stderr both pass through to the user's terminal via inherited file descriptors; gww's ``checking X`` header and the matching result line (``X: clean`` / ``X: keep`` / ``X: skip (timeout)`` / ``X: skip (<command> not found)``) bracket the streams so the user can see which branch produced them, but the streams themselves are never transformed or parsed. Command exit code: 0 if no per-worktree git operation failed, 1 if any ``git worktree remove`` or ``git branch -d`` failed, 2 if config error — provider failures do not affect the command's exit code. See ADR-0018 for the rationale (rejected richer abort-on-auth / retry-on-429/5xx policies in favour of this simpler approach).

**No auto-fetch**:
``gww clean`` never invokes ``git fetch`` (or ``git remote update``) on the user's behalf. Provider API calls hit the network on their own; the ``--merged`` git-fallback path uses the user's local refs as-is, which means a stale local ``main`` will produce a stale fallback result. The user is responsible for refreshing refs (``gww pull``) when they want the fallback to be accurate; making this automatic was considered and rejected (ADR-0016).

**Provider**:
A service that exposes a programmatic interface for repository and merge-request state. ``gww clean`` currently supports three: **GitHub** (PRs as merge requests, via the ``gh`` CLI), **GitLab** (MRs, via the ``glab`` CLI), and **Gitea** (PRs, via the ``tea`` CLI). A provider is identified by its kind (``github``/``gitlab``/``gitea``) and a *configured command template* that the provider module renders per branch to fetch MR/PR status. ``gww clean`` never makes direct API calls: it shells out to the provider's official CLI only. Each provider kind has a documented default ``host_patterns`` and ``merged`` template in ``src/gww/providers/<kind>.py`` that users copy into their config (the ``gww init config`` template includes them commented out); these defaults are **reference starting points**, not auto-applied values — resolution requires a user-declared match (see *Origin-based provider detection*).
_Avoid_: forge (gitlab-specific term that leaked into the wider world), remote, host (a host is a hostname, not a provider — a single host maps to exactly one provider *kind*).

**Origin-based provider detection** (simplified 2026-07-13, per ADR-0019):
The algorithm ``gww clean`` runs to resolve a provider for the current source: test the origin host against each user-declared ``providers.<kind>.host_patterns`` (a list of regex strings) in config order; first match wins. **No ``GWW_PROVIDER`` environment override. No built-in defaults** for hosted instances — users on ``github.com`` / ``gitlab.com`` / ``codeberg.org`` / etc. must declare the provider in their config, or rely on the ``--merged`` git fallback. Failing all declared patterns means "no provider resolvable" and the ``--merged`` filter falls back to ``git branch --merged <default>``. The per-kind modules in ``src/gww/providers/`` (``github.py`` / ``gitlab.py`` / ``gitea.py``) are reference starting points that document a sensible default ``host_patterns`` and ``merged`` template; they are not auto-applied.
_Avoid_: provider autodiscovery, magic detection.

**Provider merged command**:
The single string ``providers.<kind>.merged`` evaluated by gww's existing template engine (``gww.template``) with the same functions available as path templates and ``command`` actions: ``branch()``, ``host()``, ``path(n)``, ``protocol()``, ``uri()``, ``port()``, the project's tag functions, and project-context functions like ``current_worktree()``. The template is resolved against a per-worktree ``TemplateContext`` so commands like ``gh pr list --head branch()`` see the right branch for each worktree. The rendered command is invoked via the shell; ``gww clean`` reads only its **exit code** — no stdout parsing, no JSON, no canonical enum. **Exit 0 means "an MR/PR for this branch is in the merged state, the worktree is cleanable and will be removed".** Non-zero means "do not remove" (the worktree stays) — whether that's "no MR exists", "MR exists but isn't merged", "auth failed", "rate-limited", or "the network is down". The CLI's own state filter (e.g. ``--state merged`` for ``gh``) is what produces the merged-vs-not discrimination; users who need a different shape (e.g. ``tea`` which has no native ``--state merged``) compose their own pipeline with ``jq`` and emit exit code from that. See ADR-0018.

**CLI-based provider**:
A provider that ``gww clean`` uses exclusively by shelling out to the provider's official CLI (``gh``, ``glab``, ``tea``) and reading its exit code. ``gww clean`` itself never calls HTTP APIs, never reads tokens from env or config, never parses JSON, and never stores credentials — authentication is the CLI's responsibility (``gh auth login``, ``glab auth login``, ``tea login``). This is a deliberate trade-off (ADR-0017): trade away a small amount of control over request shape for a hard guarantee that gww never holds secrets, never has to learn a JSON shape, and reuses whatever auth the user has already set up. The trade also collapses the schema (one template per provider, not a template + a parser) and makes user overrides as simple as swapping in a different shell command — anything that exits 0 on "merged" works.

## Distribution

**Release**:
A new version of `gww` published to GitHub Releases and PyPI. Triggered by pushing a `vX.Y.Z` tag; produces a sdist + per-Python-version wheels as GitHub Release artifacts and a `gww` package on PyPI. The published version is read from `[project].version` in `pyproject.toml`, which the workflow asserts matches the stripped tag — the tag is the trigger, the file is the source of truth.
_Avoid_: deploy, publish (use for the PyPI side specifically), ship (too informal).

**Release trigger**:
The git tag push that initiates a release, of the form `vX.Y.Z` (SemVer, `v` prefix). Annotated tags are not required; lightweight tags work because the workflow reads the version from `pyproject.toml`, not from the tag object.
_Avoid_: version bump (that's the file edit, not the trigger), release commit.

**Trusted Publishing**:
PyPI's OIDC-based authentication for upload workflows. PyPI issues a short-lived token to the `release.yml` workflow run based on the repository, workflow file path, and `pypi` GitHub Environment; no long-lived API token exists. See ADR-0014.
_Avoid_: OIDC auth (mechanism, not the product), tokenless upload (PyPI still issues a token — it just lives for one workflow run).

**`pypi` GitHub Environment**:
A GitHub Environment named `pypi` configured on the repo with a required-reviewer protection rule. The release workflow targets this environment so the OIDC token exchange only succeeds when the run is gated by an approver — even a successful tag push is blocked at the approval step without reviewer consent. See ADR-0014.
_Avoid_: production environment (PyPI *is* production for this project, but "production" is ambiguous when the repo has no other deploys).
