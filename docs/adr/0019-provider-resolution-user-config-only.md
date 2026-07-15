# 0019 — `gww clean` provider resolution is user-config-only

> **Superseded in part by [ADR-0021](0021-provider-selection-when-predicate.md) (2026-07-15):** the `host_patterns` regex mechanism described below is replaced by a `when` predicate. This ADR's *stance* — single-layer, user-config-only, no env override, no built-in defaults, git fallback — is unchanged; only "test the origin host against `host_patterns`" becomes "evaluate the `when` predicate against the source URI". Read `providers.<kind>.host_patterns` below as `providers.<name>.when`.

`gww clean`'s provider resolution is single-layer: match the source against each user-declared provider in config order; first match wins. **No `GWW_PROVIDER` environment override. No built-in defaults for hosted instances.** Users on `github.com` / `gitlab.com` / `codeberg.org` / etc. must declare the provider in their config, or rely on the `--merged` git fallback when no declared provider matches.

## Why drop env override and built-in defaults

Earlier drafts of `gww clean` had three resolution layers (env override → user config → built-in defaults for hosted instances). The 2026-07-13 grilling session collapsed this to a single layer for three reasons:

1. **Env override is debugging cruft.** `GWW_PROVIDER` existed for the case "the host pattern fails but the right CLI is installed". With no built-in defaults to fight, the user has already declared their provider explicitly; a temporary override is just a config edit. The env var adds a second code path for zero benefit.
2. **Built-in defaults couple gww to specific hosts.** Keeping `github.com` / `*.github.com` / `gitlab.com` / `codeberg.org` / `gitea.com` / `gitea.io` / `try.gitea.io` as built-ins means gww carries a maintenance burden when GitHub Enterprise URLs change, when GitLab Self-Hosted rebrands, when a new forge launches, or when a hosted instance moves domains. User-declared patterns push that burden to the user, where it belongs — they know their setup.
3. **The git fallback covers the "I just want it to work" case.** Users who don't want to write config — or who use a forge gww doesn't ship defaults for — get correct behaviour via `git branch --merged <default>`. This is the same fallback used when no provider resolves for any reason, so the user experience is consistent.

The cost: users on `github.com` now need to write a config block (or copy one from `gww init config`'s template) before `gww clean --merged` works against the GitHub API. For users who don't care about provider API queries, the fallback works without any config.

## What this implies for the provider examples

There are **no per-kind reference modules** in the codebase (earlier drafts of this ADR wrongly referenced `src/gww/providers/{github,gitlab,gitea}.py`; those files never existed and the whole `src/gww/providers/` package was removed by ADR-0021). The only worked GitHub / GitLab / Gitea examples ship in the commented `providers:` block of the `gww init config` template; users copy the relevant entry into their config. Provider selection now lives in `src/gww/config/` (`rule_matching.first_matching_rule` + `resolver.find_matching_provider`).

## What this implies for `--merged`

Unchanged from ADR-0015: when no provider resolves for the source's origin host, `--merged` falls back to `git branch --merged <default>`. Pure git, no subprocess-per-branch provider cost, and now also the path users get automatically if they don't write provider config.

## Considered Options

- **Three layers (env → user → built-in)** — rejected: couples gww to specific hosts, adds debugging-only complexity, fails the "do one thing simply" test.
- **Two layers (env → user)** — rejected: env override is debugging cruft once built-ins are gone; if a user wants a temporary override, config-edit accomplishes the same.
- **Single layer, user-config-only (this ADR)** — chosen: simplest, no host-coupling, git fallback covers the "I just want it to work" case.

## Supersedes

- The "Provider resolution" subsection of `docs/handoff-gww-clean.md` (the pre-grilling handoff, kept as archaeology).
- The "Provider resolution" subsection of `docs/handoff-gww-clean-v2.md` (updated in lockstep).
- The `Origin-based provider detection` entry in `CONTEXT.md` (updated in lockstep).
- The `Provider` glossary entry's last sentence in `CONTEXT.md` (the "built-in default command template" wording is now wrong — there are no auto-applied values; examples live only in the `gww init config` template).
- The "hosted users don't write anything (defaults kick in)" sentence in `docs/adr/0017-cli-based-provider-no-direct-api.md` ("Why the command is templated, not hard-coded" section) — corrected in lockstep.
- The "we keep built-in defaults for hosted providers so typical users write zero config" line in `docs/adr/0017-cli-based-provider-no-direct-api.md`'s Considered Options — corrected in lockstep.