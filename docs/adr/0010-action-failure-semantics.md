# 0010 — Action failure semantics: per-rule criticality, exit codes, and output

Action failures in `gww clone` / `gww add` are classified by per-rule criticality: the `critical:` flag on each project rule, defaulting to `true`. A failing critical rule makes the command exit 1; a failing non-critical rule is summarised but exits 0; a matcher failure (un-evaluable `when:` predicate or `command:` template) is a config error and exits 2. Failures are reported in a single grouped summary at the end of the action loop, and the `say()` success line is suppressed whenever that summary is non-empty — so `cd $(gwc …)` only ever lands on a fully-configured worktree.

## Why per-rule granularity

Three granularities were considered: per-action (`critical:` on each `abs_copy` / `rel_copy` / `command`), per-rule, and per-command-invocation. Per-action is the most flexible but pushes bookkeeping onto every user — and actions inside a single rule almost always share intent ("set up the Python venv" runs `python -m venv` and `pip install -r requirements.txt` together, both either succeed or both fail). Per-command-invocation collapses to per-action with extra ceremony. Per-rule matches how users think: one rule = one setup step = one criticality decision. The matcher already iterates rules in order, so threading a criticality flag through the loop is cheap.

## Why default critical: true

Three defaults were considered: `true`, `false`, and required. `false` preserves today's behaviour — and today's behaviour is exactly what we wanted to escape: silent failures on a successful clone, exit 0, success line printed, user thinks everything worked. That is the failure mode this ADR exists to retire. Required is purist but punishes every existing user with a mandatory config edit on upgrade. `true` is the gentle nudge: the field is optional, the new behaviour is the safe one, and the escape hatch (`critical: false`) is one line per rule for users who genuinely want non-critical semantics.

## Why this exit-code mapping

| Outcome | Exit |
|---|---|
| Clean run (no failures) | 0 |
| Non-critical rule failure | 0 |
| Critical rule failure | 1 |
| Matcher failure | 2 |

The existing two-tier signal (1 = runtime, 2 = config; see `CommandExit` in `gww/cli/context.py`) is preserved. Non-critical failures are warnings: the user explicitly opted into non-critical behaviour by setting `critical: false`, so the command honours that choice. Tiered codes (e.g. 3 = non-critical failure) were considered but rejected — no existing tooling differentiates beyond 0/1/2, and adding 3 expands the contract for marginal benefit.

## Why suppress the success line on any failure

The success line is gww's contract with shell scripts and the `gwc` / `gwa` / `gwr` shell aliases. The documented pattern is `cd $(gwc <uri>)` — bind the new path to the current shell and `cd` into it. If the success line is printed on partial failure, scripts `cd` into a half-configured worktree and fail later in confusing ways. Suppressing on any failure (critical or non-critical) makes the success line a clean signal: "this path is fully configured, safe to `cd` into". The trade-off is that a non-critical failure no longer surfaces in the success-line position — but it does surface in the grouped summary block right above, so nothing is lost.

## Considered Options

- **No `critical` flag — keep today's silent-failure behaviour.** Rejected: the entire motivation for this ADR. Silent failures on a successful clone are exactly the failure mode we need to escape.
- **Per-action criticality.** Rejected: most flexible, but pushes bookkeeping onto every user and conflates rule-level intent with per-file-copy configuration.
- **Required `critical` field.** Rejected: punishes every existing user with a mandatory config edit on upgrade for a soft benefit. Optional-with-default-true is the gentler nudge.
- **Tiered exit codes (3 = non-critical failure).** Rejected: expands the contract beyond the existing 0/1/2 split that `CommandExit` and downstream consumers already encode.
- **`--lax` global CLI flag to override `critical: true` → false at runtime.** Rejected: redundant — users who want lax behaviour can edit `critical: false` per rule. The per-rule knob is strictly more expressive than a global toggle, and the CLI surface stays clean.
- **Suppress success line only on critical failure.** Rejected: creates a confusing split — same exit 0, same path printed, but a hidden warning somewhere in stderr. That is the silent-failure mode we just escaped.
- **Per-rule fault isolation in the matcher (rule N's `when` failure skips rule N but lets rules N-1 and N+1 run).** Rejected: matcher failures are config bugs the user needs to see immediately; partial matching masks them. Strict semantics (any matcher failure → exit 2) keeps the bug surface visible.