# 0019 — `gww clean` provider resolution is user-config-only

`gww clean`'s provider resolution is single-layer: test the source's origin host against each user-declared `providers.<kind>.host_patterns` in config order; first match wins. **No `GWW_PROVIDER` environment override. No built-in defaults for hosted instances.** Users on `github.com` / `gitlab.com` / `codeberg.org` / etc. must declare the provider in their config, or rely on the `--merged` git fallback when no declared pattern matches.

## Why drop env override and built-in defaults

Earlier drafts of `gww clean` had three resolution layers (env override → user config → built-in defaults for hosted instances). The 2026-07-13 grilling session collapsed this to a single layer for three reasons:

1. **Env override is debugging cruft.** `GWW_PROVIDER` existed for the case "the host pattern fails but the right CLI is installed". With no built-in defaults to fight, the user has already declared their provider explicitly; a temporary override is just a config edit. The env var adds a second code path for zero benefit.
2. **Built-in defaults couple gww to specific hosts.** Keeping `github.com` / `*.github.com` / `gitlab.com` / `codeberg.org` / `gitea.com` / `gitea.io` / `try.gitea.io` as built-ins means gww carries a maintenance burden when GitHub Enterprise URLs change, when GitLab Self-Hosted rebrands, when a new forge launches, or when a hosted instance moves domains. User-declared patterns push that burden to the user, where it belongs — they know their setup.
3. **The git fallback covers the "I just want it to work" case.** Users who don't want to write config — or who use a forge gww doesn't ship defaults for — get correct behaviour via `git branch --merged <default>`. This is the same fallback used when no provider resolves for any reason, so the user experience is consistent.

The cost: users on `github.com` now need to write a config block (or copy one from `gww init config`'s template) before `gww clean --merged` works against the GitHub API. For users who don't care about provider API queries, the fallback works without any config.

## What this implies for the provider modules

`src/gww/providers/{github,gitlab,gitea}.py` are kept as **reference / starting points**, not auto-applied defaults. Each module documents a sensible default `host_patterns` and `merged` template for its kind; users copy the relevant fields into their config (the `gww init config` template includes them commented out). `base.py` provides the `Provider` dataclass and the host-pattern matching primitive.

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
- The `Provider` glossary entry's last sentence in `CONTEXT.md` (the "built-in default command template" wording is now wrong — defaults live in `src/gww/providers/<kind>.py` as reference, not as auto-applied values).
- The "hosted users don't write anything (defaults kick in)" sentence in `docs/adr/0017-cli-based-provider-no-direct-api.md` ("Why the command is templated, not hard-coded" section) — corrected in lockstep.
- The "we keep built-in defaults for hosted providers so typical users write zero config" line in `docs/adr/0017-cli-based-provider-no-direct-api.md`'s Considered Options — corrected in lockstep.