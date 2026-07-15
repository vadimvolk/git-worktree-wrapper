# 0017 — `gww clean` providers are CLI-based, never direct API

`gww clean`'s provider integration shells out to the official CLI for each supported host (`gh` for GitHub, `glab` for GitLab, `tea` for Gitea). `gww clean` itself never makes HTTP calls to provider APIs, never reads tokens from the environment, never stores credentials in the config, never asks the user to paste a PAT. The `providers:` config block declares the *command template* that gww renders per branch.

## Why CLI-based instead of direct API

The alternative was a thin `httpx`-or-stdlib-based provider client per kind, with token sourcing layered on top (env, `gh auth token` shelling, `~/.netrc`, etc., as explored in Q4). We chose CLI-based for three independent reasons:

1. **No secrets in gww's hands.** Auth is the CLI's problem, not ours. `gww config` cannot leak a token because `gww config` doesn't see one. `gww clean` has nothing to redact in `--verbose` output, no token to scrub from crash dumps, no PAT to invalidate when a config file is shared.
2. **Free auth for users who already logged in.** The user already typed `gh auth login` / `glab auth login` / `tea login` once for the rest of their tooling. CLI-based reuses that, so `gww clean` works for the common case at zero extra setup. The API-based path would have required every user to set a token env var even if they already had `gh` authenticated.
3. **Reuse of CLI output formats.** `gh --json`, `glab --output json`, `tea --output json` all emit JSON we can parse. We don't need to write the JSON-shape-unmarshalling logic ourselves; the CLI authors already did it.

The cost is a subprocess per branch and a per-provider output parser. The subprocess overhead is amortized across the API work the CLI itself does; the parser is small (one kind's worth of output mapping).

## Why the command is templated, not hard-coded

A hard-coded command per provider kind — `gh pr list --head {branch} --state merged` — would work for hosted instances but break for self-hosted ones with non-standard CLI wrappers, proxied `gh`/`glab`/`tea` binaries, or alternative output flags. Making `providers.<kind>.merged` a template (evaluated by gww's existing template engine with `branch()`, `host()`, `path()`, …) means: self-hosted / oddly-configured users can swap in their own command without us shipping a fork, and the template engine we already maintain (with its escaping, function registry, error reporting, ADR-0006) does double duty. Note that the rendered command's *exit code* is the entire contract — see ADR-0018 for why we don't parse JSON.

> **Note (2026-07-13)**: Earlier drafts of this section claimed "hosted users don't write anything (defaults kick in)". That claim is superseded by ADR-0019: there are no auto-applied built-in defaults. Hosted users must declare their provider in config, or rely on the `--merged` git fallback. Worked reference examples live in the commented `providers:` block of the `gww init config` template, not in any per-kind source module — none exist (per ADR-0019 / ADR-0021).

## Why we don't ship a "provider detects the CLI is installed" check

Some providers ship multiple CLIs (`gh` is one; `hub` predates it; GitHub also supports `graphql` via `gh extension`). We picked **one** canonical CLI per kind (`gh`, `glab`, `tea`) and let users override the command template if they need a different binary. We deliberately do not probe for multiple binaries, because:
- Probing adds time on every cleanup run.
- The "which CLI is canonical" question only ever has one answer in modern setups — picking that answer and not deviating is the simplest contract.
- Users on legacy CLIs have a one-line escape hatch via `providers.<kind>.merged`.

## Why output-shape handling is not a gww concern at all

A previous draft of this ADR said "the provider module knows what JSON its command produces and how to map fields to `PullRequestStatus` (`OPEN` / `CLOSED` / `MERGED`)". That design was rejected during grilling (see ADR-0018): the schema is now a single `merged` template per provider and gww reads **only the exit code**. GitHub's `mergedAt` quirk is no longer gww's problem — `gh pr list --state merged` answers the question directly with its exit code, and `tea` users compose their own `jq` pipeline. Users overriding `merged` are responsible only for "exit 0 iff an MR for this branch is in the merged state" — the simplest possible contract.

## Considered Options

- Direct API with `httpx` + env/netrc token sourcing — rejected; trades secrets-handling complexity for one fewer subprocess per branch.
- Direct API with `gh auth token` / `glab auth status` / `tea` shell-outs for token only — rejected; pulls token into gww's address space, removing the security property this ADR exists to give us.
- gRPC/protobuf over the CLI — rejected; not all CLIs expose one.
- Make the user write the entire command in config — rejected as the *only* mechanism; we keep worked reference examples in the commented `providers:` block of the `gww init config` template for users to copy, but they are not auto-applied (per ADR-0019).
