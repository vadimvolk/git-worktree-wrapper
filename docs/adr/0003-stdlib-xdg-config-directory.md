# 0003 — Stdlib-only cross-platform config directory

The config file lives at `$XDG_CONFIG_HOME/gww/config.yml` whenever
`$XDG_CONFIG_HOME` is set to an absolute path; otherwise the OS default is
used — `~/.config/gww/config.yml` on Linux, `~/Library/Application
Support/gww/config.yml` on macOS, and `%APPDATA%\gww\config.yml` on
Windows. Per the Constitution's minimalism principle, we resolve this with
a small custom function over `os` / `pathlib` / `sys` rather than pulling
in `platformdirs` or `xdg-base-dirs`.

## Considered Options

- **`platformdirs` library** — Rejected: the standard library covers the
  three platforms we support with a few lines of `sys.platform` branching;
  the dependency adds maintenance and supply-chain surface for trivial
  logic.
- **`appdirs` library** — Rejected: older, less actively maintained.
- **`xdg-base-dirs`** — Rejected: Unix-only; we need cross-platform
  support.

## Implementation Notes

- Honor `$XDG_CONFIG_HOME` on **every** platform when it is set to an
  absolute path. This matches the XDG Base Directory spec, which is
  platform-agnostic, and lets macOS/Windows users opt into the XDG layout.
- On Linux/Unix, fall back to `~/.config` when `XDG_CONFIG_HOME` is
  unset, empty, or relative.
- On macOS, fall back to `~/Library/Application Support`.
- On Windows, fall back to `%APPDATA%` (then `~/AppData/Roaming`).
- Validate that `XDG_CONFIG_HOME` is absolute before trusting it.
- The config is cached in memory only during a single `gww` invocation —
  no file-change detection needed.

## Behavior

| Platform | Resolved path |
|---|---|
| Any | `$XDG_CONFIG_HOME/gww/config.yml` (when set and absolute) |
| Linux | `~/.config/gww/config.yml` |
| macOS | `~/Library/Application Support/gww/config.yml` |
| Windows | `%APPDATA%\gww\config.yml` |