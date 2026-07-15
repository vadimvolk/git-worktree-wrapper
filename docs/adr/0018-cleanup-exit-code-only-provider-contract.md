# 0018 — `gww clean` provider contract is exit-code-only, single template per kind

`gww clean`'s `--merged` filter runs the provider's `merged` command template once per cleanable worktree and reads **only** the exit code: 0 marks the worktree as cleanable (it will be removed), anything else leaves it in the source. gww never parses the command's stdout, never holds a `PullRequestStatus` enum, never learns any provider's JSON shape. The schema is a single template per provider; provider modules and user overrides produce any shell command that exits 0 on "merged".

## Why exit-code-only and not JSON

Earlier drafts of `gww clean` (see ADR-0017 and the post-grilling handoff `docs/handoff-gww-clean.md`) had gww parse JSON out of `gh --json` / `glab --output json` / `tea --output json` and reduce it to a `PullRequestStatus` enum (`OPEN` / `CLOSED` / `MERGED`). Three problems with that:

1. **Each CLI ships a different JSON shape.** `gh` uses `state` + `mergedAt`; `glab` uses `state` (already separate `merged`); `tea` uses `state` + a `merged` boolean. A `parse_hint` DSL that maps arbitrary fields to the enum is its own surface, with its own tests, its own JSONPath evaluator, and its own forward-compat story.
2. **GitHub's `mergedAt` quirk is unique to the JSON path.** `gh pr list --state closed` returns merged *and* closed-not-merged PRs; only `mergedAt` disambiguates. With exit-code-only, this disappears: `gh pr list --state merged` answers "is there a merged PR?" directly with its exit code, no field reading required.
3. **JSON parsing in gww violates the "no secrets in gww's hands" property by extension.** A JSON parser is harmless on its own, but every line of output-handling code is a place where stderr formatting, error messages, and verbose-mode logging can accidentally surface provider internals. The smaller the surface, the smaller the audit.

The CLI's own state filter (`--state merged` for `gh`, `--state merged` for `glab`, `| jq -e 'select(.merged)'` for `tea`) is the parser. gww delegates.

## Why a single template per provider, not two (`merged` + `closed_not_merged`)

A previous revision considered two templates so that `--closed` could widen `--merged` to also accept closed-not-merged MRs. That was dropped because:

- **Closed-not-merged is ambiguous.** "Closed" includes abandoned, superseded, won't-fix, and rejected-but-decided-to-revisit-later. Auto-cleanup of these is a judgment call the user should make explicitly (`gww remove <branch>` or `gww clean --all`).
- **Two templates double the subprocess count for `--closed`** vs the per-source list-call approach (now N/A anyway since we're per-branch). Even if subprocess cost is acceptable, the *complexity cost* in `CONTEXT.md`, in `validator.py`, and in user-facing docs is real for a flag whose semantics the user can replace with `--all` + `gww remove`.
- **The surface shrinks faster than the user-visible expressivity drops.** `--merged` covers the common case (MR was merged → cleanup is obvious). `--all` covers everything else. Closed-not-merged cleanup becomes a one-line `gww remove` away.

## What this implies for the schema

```yaml
providers:
  github:
    when: '"github" in host()'  # selection mechanism, ADR-0021 (was host_patterns)
    filter: 'gh pr list --head branch() --state tag("state", "merged") --json number --jq "length > 0"'
  gitlab:
    when: '"gitlab" in host()'
    filter: 'glab mr list --source-branch branch() --state tag("state", "merged")'
  gitea:
    when: '"codeberg.org" in host()'
    filter: 'tea pulls list --head branch() --state closed --output json | jq -e "[.[] | select(.merged or tag(\"state\") == \"closed\")] | length > 0"'
```

One template per provider, evaluated by the existing `gww.template` engine with `branch()`, `host()`, `path(n)`, etc. The rendered command is invoked via the shell; only its return code is consulted.

## What this implies for the failure-mode policy (locked 2026-07-13)

The action contract is the entire failure-mode policy:

| Composed-command behaviour | Exit 0 iff | gww reaction |
|---|---|---|
| Provider returned cleanly (e.g. `gh pr list --state merged --head X` printed and matched) | a merged MR/PR exists for this branch | worktree is cleanable (removed) |
| Anything else (empty result, auth failure, rate limit, network error, malformed composed pipeline) | not-a-merged-MR-for-this-branch | worktree stays |

No abort, no retry, no parse. The exit code is the entire signal; gww does not interpret the provider's stdout or stderr to disambiguate sub-cases of non-zero. The CLI's exit-code-on-empty behaviour still matters for correctness — `gh` exits 1 on empty, `glab`'s contract needs empirical verification (the implementation should test against a fixture repo before shipping), and `tea` has no native `--state merged` so users compose `jq -e` themselves with `set -o pipefail` so an upstream `tea` failure isn't hidden by `jq` exiting 0 on an empty stream. All of those are about *whether exit 0 truly means "merged MR/PR exists"* — not about how gww reacts to non-zero, which is uniformly "keep" at the contract level.

Two exceptions get gww-generated per-branch labels (these are gww's own output, not parsing of the provider's streams):

| Condition | Per-branch label |
|---|---|
| Subprocess timeout (60s exceeded) | `X: skip (timeout)` |
| `FileNotFoundError` (provider CLI not installed, e.g. `gh not found`) | `X: skip (<command> not found)` with the actual command name |
| Any other exception | (silent, treated as non-zero → keep) |

Both provider stdout and provider stderr pass through to the user's terminal via inherited file descriptors. The `checking X` header and result line bracket the streams so the user knows which branch produced them; the streams themselves are never transformed or parsed.

**Command exit code:** 0 if no per-worktree git operation failed, 1 if any `git worktree remove` or `git branch -d` failed (consistent with `remove.py`'s `raise CommandExit(1)` pattern), 2 if config error. Provider failures do not affect the command's exit code.

## Rejected richer policies

Earlier drafts of this ADR (and the pre-grilling handoff) considered:

- **Abort-on-auth** (stderr substring match for `auth` / `unauthorized` / `forbidden` per CLI): rejected. Fragile across CLIs and localizations; introduces stderr-parsing into a contract that explicitly forbids it; the silent-broken-setup risk is mitigated by the per-branch timeout / not-found tags + summary counts + the user's own ability to `gh auth status` themselves.
- **Retry-on-429** (with `Retry-After` honored) and **retry-on-5xx** (one retry with 1s backoff): rejected. Adds retry timing, retry budgets, and `pipefail`-preserved retry attribution, all for transient blips the user can re-run around.
- **Per-CLI exit-code discrimination** (e.g. `gh`'s exit 4 = auth): rejected. Same per-CLI fragility as stderr substring matching; not all CLIs have distinct codes for "auth" vs "no result".

The trade is explicit: **simplicity and the "do not parse" property in exchange for accepting that a token-expired `gh` looks identical to a healthy repo with no merged MRs** at the per-branch level. The summary's `kept M` count is the same in both cases. The user accepts this risk because the alternative — parsing stderr or maintaining per-CLI exit-code tables — violates ADR-0017's "no secrets-handling surface" rationale (every line of stderr-handling code is a place where verbose-mode logging or error messages could accidentally surface provider internals).

## What this implies for the `--merged` git-fallback path

Unchanged from ADR-0015: when no provider resolves for the source's origin host, `--merged` falls back to `git branch --merged <default>`. This path is pure git, has no subprocess-per-branch provider cost, and is the documented contract for users without `gh`/`glab`/`tea` set up.

## Considered Options

- **JSON parsing with `parse_hint` DSL** — rejected; introduces a per-provider JSONPath surface, doesn't shrink the schema meaningfully, leaves GitHub's `mergedAt` quirk to be expressed in config.
- **Per-source list-call with one subprocess** — rejected when exit-code-only was adopted; the per-branch model is simpler once you've decided not to parse anything, and N subprocesses at ~50ms each is well under any user's pain threshold.
- **Two templates per provider (`merged` + `closed_not_merged`)** — rejected; closed-not-merged cleanup is a judgment call, the second template doubles the surface for a flag whose semantics `gww remove` already covers.
- **Hard-coded command per kind, no user override** — rejected; the existing template engine handles `branch()` / `host()` / etc. already, and user overrides are a one-line escape hatch for self-host / proxy-CLI setups (per ADR-0017's "Why the command is templated, not hard-coded").
- **Per-CLI auto-detection ("which `gh`-equivalent is installed?")** — rejected by ADR-0017; one canonical CLI per kind, with template override as escape hatch.

## Supersedes

- The "Provider command template" glossary term (CONTEXT.md pre-0018), which described a `providers.<kind>.command` template whose stdout was parsed for `PullRequestStatus`.
- The `PullRequestStatus` glossary term (CONTEXT.md pre-0018, also duplicated), which described a canonical `OPEN/CLOSED/MERGED` enum that gww reduced CLI output to.
- The `--closed` filter glossary term (CONTEXT.md pre-0018) and the corresponding paragraph in ADR-0015.