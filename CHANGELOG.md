# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/vadimvolk/git-worktree-wrapper/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/vadimvolk/git-worktree-wrapper/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/vadimvolk/git-worktree-wrapper/releases/tag/v0.1.0