# 0002 — ruamel.yaml in round-trip mode for config parsing

The gww config file is hand-edited YAML that users annotate with comments documenting their routing rules and project actions. We use `ruamel.yaml` in round-trip mode (`typ='rt'`) because it is the only mainstream Python YAML library that preserves comments, formatting (quotes, indentation), and key ordering across load → modify → dump cycles. `gww init config` writes a documented default; later mutations must not silently strip those comments.

## Considered Options

- **PyYAML** — Rejected: drops comments and formatting on dump; unsuitable for a human-edited, comment-documented config file.
- **JSON** — Rejected: no comments, less readable, no formatting conventions to preserve.
- **TOML** — Considered, but the architecture specifies YAML and TOML does not support the same inline-documentation style.

## Implementation Notes

- Instantiate with `YAML(typ='rt')` and set `preserve_quotes = True` plus the desired indent.
- Use the pure-Python mode (default for `typ='rt'`); the libyaml C extension is incompatible with round-trip.
- Edge case: a YAML document containing only comments must round-trip without losing the comments.
- Acceptable trade-off: comment positions can shift slightly on key reassignment — this is a known round-trip limitation, not a bug to fix.

## Comparison: ruamel.yaml vs PyYAML

| Feature | ruamel.yaml (rt) | PyYAML |
|---|---|---|
| Preserve comments | yes | no |
| Preserve formatting | yes | no |
| Preserve key ordering | yes | limited |
| Round-trip support | full | none |
| Performance | slower (pure Python) | faster (C extension) |
| API complexity | more complex | simpler |