# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-07-15

### Changed

- **BREAKING**: Provider selection now uses `when` predicates instead of `host_patterns`. Providers are matched using the same URI+tag context as `sources:` and `actions:` rules. The first provider whose `when` predicate evaluates to true is selected. (ADR-0021)
- **BREAKING**: Provider `merged` field renamed to `filter` to reflect its general exit-code-based filtering purpose.
- **BREAKING**: Provider `kind` field renamed to `name`. Provider names are now free-form identifiers rather than constrained to `github`/`gitlab`/`gitea`.
- Removed `src/gww/providers/` package (`base.py` and `__init__.py`) — the `when` predicate makes provider kinds unnecessary.

### Added

- Tags passed via `gww clean --tag key=value` are now available in both provider `when` predicates (for selection) and `filter` templates (for per-branch logic).
- The `tag()` template function now accepts an optional default parameter: `tag("name", "default")` returns the default value if the tag is missing.

### Notes

- Provider `when` predicates have access to the same URI context as source rules: `host()`, `port()`, `protocol()`, `path(n)`, `uri()`, and tags. The `branch()` function remains available only in the `filter` template.
- The git fallback behavior is unchanged: when no providers match or no origin exists, `gww clean --merged` falls back to `git branch --merged`.
- Existing configs with `host_patterns` or `merged` keys will silently ignore those fields — manual migration to `when` and `filter` is required.

### Breaking Changes

- **`gww clean` provider config**: Renamed `merged` field to `filter` to reflect its general purpose (exit 0 = cleanable branch, not strictly "merged state"). Update your config:
  ```yaml
  # Before:
  providers:
    github:
      merged: 'gh pr list --head branch() --state merged'
  
  # After:
  providers:
    github:
      filter: 'gh pr list --head branch() --state merged'
  ```

### Added

- **`gww clean --tag`**: Added `--tag key=value` support to `gww clean` command (repeatable, same as other commands). Tags are available in both provider `when` predicates (for selection) and `filter` templates (for per-branch logic).
- **`tag()` default parameter**: The `tag()` template function now accepts an optional default value: `tag("state", "merged")` returns `"merged"` if the `state` tag is not set. Fully backward compatible—existing `tag("name")` calls still return empty string if the tag is missing.
- **Tag-driven filtering example**: Use `gww clean --tag state=closed` to remove branches with closed (but not merged) PRs, where the provider's `filter` uses `--state tag("state", "merged")` for flexible state checking.

## [0.2.1] - 2026-07-14

### Added

- `gww clean --merged` now emits a stderr warning when the filter falls
  back to `git merge --no-ff` because the origin URI is unparseable or
  its host matches no declared provider. Deliberate-fallback cases (no
  origin remote, no providers declared) stay silent.

### Notes

- Several internal refactors since 0.2.0: `gww clean` was split into a
  package (removal primitive, plan, provider, report); the source URI
  is now parsed once and threaded through as `ParsedURI`; the per-kind
  provider reference modules and `Provider` dataclass were dropped;
  all git invocations were consolidated behind a single public
  `run_git`. No user-facing API changes.
- The architecture docs and ADR-0019 still describe the dropped
  per-kind provider reference modules; this is intentional for this
  release and will be cleaned up in a follow-up.

## [0.2.0] - 2026-07-14

### Added

- `gww clean` subcommand that removes worktrees whose branches have a
  merged upstream MR/PR, gated by a configurable provider abstraction
  (`github`, `gitlab`, `gitea`). Providers are CLI-based with an
  exit-code-only contract (no direct API calls) and resolved
  exclusively from user-declared config.
- `providers:` config block in `config.yml`, with reference defaults
  shipped under `src/gww/providers/` (see ADR-0017, ADR-0018,
  ADR-0019).

### Fixed

- `gww clean` now invokes provider commands via `/bin/bash` so that
  `set -o pipefail` works uniformly on macOS and Linux (dash on Linux
  was rejecting it with exit code 2, masking real provider exit
  codes).

### Notes

- See ADR-0015 through ADR-0019 for the design decisions behind
  `gww clean`.

## [0.1.0] - 2026-07-03

First published release.

### Added

- `gww` CLI with subcommands: `clone`, `add`, `remove`, `pull`, `migrate`, `init`.
- Configurable path templates via `path(n)`, `branch()`, `norm_branch()`,
  `tag()` functions.
- Condition-based routing on URI conditions (host, path, protocol, tags).
- Project-specific actions (`after_clone`, `after_add`, `before_remove`)
  with `copy` and `command` kinds.
- Critical / non-critical rule semantics for action failure handling.
- Cross-platform config directory resolution (XDG / macOS / Windows),
  honouring `$XDG_CONFIG_HOME` on every platform.
- Shell completion and aliases (`gwc`, `gwa`, `gwr`) for bash, zsh, fish.
- Fish prompt repaint after alias-driven navigation (ADR-0013).

### Notes

- The Python package on PyPI is `git-worktree-wrapper`; the CLI command
  installed by `[project.scripts]` is `gww`. Install with
  `pip install git-worktree-wrapper` or `uv tool install git-worktree-wrapper`.
- See `docs/releasing.md` for the release process.
- See `CONTEXT.md` for domain terminology and `docs/adr/` for
  architectural decisions.

[Unreleased]: https://github.com/vadimvolk/git-worktree-wrapper/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/vadimvolk/git-worktree-wrapper/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/vadimvolk/git-worktree-wrapper/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/vadimvolk/git-worktree-wrapper/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/vadimvolk/git-worktree-wrapper/releases/tag/v0.1.0