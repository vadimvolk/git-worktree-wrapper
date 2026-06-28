# 0007 — Single-package layout for the CLI project

The gww codebase is laid out as a single Python package (`src/gww/`) with subpackages per concern (`cli/`, `config/`, `template/`, `git/`, `actions/`, `utils/`), one console-script entry point (`gww`), and a flat `tests/` tree mirroring the source tree. We rejected multi-package or monorepo layouts because gww is one binary with tightly coupled internal layers; splitting it across packages would force artificial import boundaries without any deployment benefit (there is one `gww` wheel to ship, not several).

## Considered Options

- **Multi-package layout** (`gww-core`, `gww-cli`, `gww-template` …) — Rejected: the layers share types and call each other constantly; a multi-package layout would mean either re-exporting types or making consumers depend on multiple internal packages. Either is worse than a single package.
- **Flat module layout** (no `src/`, everything at the repo root) — Rejected: harder to enforce import isolation, and `src/` layout is the `uv` default and matches what contributors expect from a Python CLI in 2025.
- **Monorepo with multiple binaries** (e.g. `gww`, `gwwd` daemon) — Rejected: out of scope; no daemon is planned.

## Implementation Notes

- `src/gww/` is the installable package; `pyproject.toml` declares it via `tool.hatch.build.targets.wheel.packages = ["src/gww"]` (or the equivalent `setuptools` / `uv` block).
- Tests live in `tests/unit/` and `tests/integration/`, mirroring the source tree under `src/gww/`.
- Subpackages by concern (CLI commands, config, template, git, actions, utils) — kept small enough that cross-imports inside the package do not require explicit public APIs.
- Fixtures (sample configs, sample git repos) live under `tests/fixtures/` and are loaded via `pathlib.Path(__file__).parent / "fixtures"`.