# 0015 — `gww clean` `--merged` filter is polymorphic

`gww clean`'s default `--merged` filter has one name with two implementation strategies: provider-aware MR-merged status when a provider resolves for the source's origin host, and git-level "fully merged into default branch" detection (`git branch --merged <default>`) when it doesn't. The user-visible flag stays `--merged` in both cases; the silent fallback is the contract.

## Why one flag, not two

The alternatives were two flags (`--mr-merged` for provider, `--git-merged` for the local merge check) or one flag with an explicit `--strict` switch (force provider, error if unavailable). Both make the user pick a strategy before invoking, even when the choice doesn't change the answer for their repository. In practice most repositories either always have a discoverable provider or never do — the choice is a per-user/per-repo property, not a per-call decision. Hiding the strategy behind a single flag keeps the surface clean; users who genuinely want one strategy or the other can achieve it by configuring or un-configuring their `providers:` block.

## Why silent fallback instead of an error

The other option was to error out with "no provider resolvable" and require the user to add `providers.<kind>.url: …` to the config or pass `--all`. That is hostile for the common case of a self-hosted Gitea or a personal GitLab instance the user hasn't configured yet — the fallback produces the right answer (the branch is in fact merged) at zero configuration cost. The cost of the silent fallback is that `--merged` means "merged by whichever check applies", which surprises users who set up a provider and then see different semantics in a non-provider-configured environment. We judge that surprise acceptable in exchange for the no-config default.

## Why silent skip for "no MR at all"

Branches without any MR (e.g. `wip/foo` abandoned before opening a PR) are silently excluded from the `--merged` filter when a provider is resolvable — they have no status to query. Alternatives: print per-branch "skipping: no MR", or include them under a `--no-mr` opt-in. The silent skip is consistent with the filter's job ("keep only branches whose MR is merged"); printing a per-branch skip line would flood the output for repos with many abandoned branches, and a `--no-mr` opt-in adds a flag nobody has asked for.

## Why no `--closed` widening flag

Earlier drafts of `gww clean` exposed `--closed` as a second filter that widened `--merged` to also accept closed-not-merged MRs. That flag was dropped during grilling (see ADR-0018). Closed-not-merged is too ambiguous to automate (abandoned, superseded, won't-fix all collapse into the same bucket), so the only way to clean up such branches is `gww remove <branch>` (per-worktree) or `gww clean --all` (sweep everything, manual review). The polymorphic `--merged` plus `--all` is the entire filter space.

## Considered Options

- Two flags (`--mr-merged` and `--git-merged`) — rejected; user has to pick a strategy up front.
- One flag plus `--strict` to force provider — rejected; pushes configuration onto every call.
- Error when no provider resolves — rejected; hostile for first-time / partially-configured users.
- Per-branch "skipping: no MR" line — rejected; noisy for repos with many abandoned branches.
- `--no-mr` opt-in to include branches without an MR — rejected; flag nobody has asked for.
- `--closed` widening flag — rejected during grilling (ADR-0018); the closed-not-merged semantics belong in `gww remove <branch>` or `--all`, not in a one-shot auto-cleanup flag.
