# 0016 — `gww clean` never auto-fetches

`gww clean` does not invoke `git fetch` (or any equivalent `git remote update`) before evaluating the `--merged` filter or before any other operation. Provider API calls go to the network on their own; the git-fallback path uses the user's local refs as-is, with no attempt to refresh them.

## Why no auto-fetch on the git-fallback path

The git-merged fallback (`git branch --merged <default>`) only produces correct results when the local `<default>` ref is at least as new as the remote's. The simplest correctness fix is for `gww clean` to `git fetch` first: one network round-trip buys an accurate filter. We rejected this because:

- **Network is opt-in for the rest of gww.** `gww add`, `gww remove`, `gww migrate`, `gww clone` all hit the network only when their primary operation requires it. Adding implicit fetches to `gww clean` is the first time gww would perform a network side effect that the user didn't ask for.
- **Air-gapped runs.** A user on a plane or behind a firewall wants `gww clean` to "just work" against local refs. An auto-fetch surfaces an avoidable network failure.
- **Predictable ordering with `gww pull`.** gww already has a `pull` command whose job is "refresh the source repo". Coupling fetch to clean makes the two commands secretly dependent. Better to make the user sequence them explicitly (`gww pull && gww clean --dry-run` to preview, `gww pull && gww clean --yes` to act).

The cost is that a stale local `refs/heads/main` will produce a stale `--git-merged` answer. We judge the cost acceptable because (a) most users run `gww pull` before destructive commands anyway, (b) the worst outcome is "we don't delete a branch we could have", which is the safer direction, and (c) `gww clean --dry-run` makes the staleness visible before any side effects run.

## Why provider-driven paths don't fetch either

The provider API path doesn't need local refs at all — it asks the provider directly. We deliberately do *not* run `git fetch` "just in case" a future code path adds a git-side step that would benefit from fresh refs. Adding fetches speculatively is the same anti-pattern as adding them to the fallback path.

## Considered Options

- Auto-fetch on the fallback path — rejected (see above).
- Auto-fetch unless `--offline` is passed — rejected; introduces a flag nobody has asked for, and is still surprising for users on planes.
- Auto-fetch only when the local `<default>` is behind `origin/<default>` — rejected; "is behind" requires a fetch to determine, defeating the optimization.
