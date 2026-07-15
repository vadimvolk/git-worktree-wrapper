# 0021 — `gww clean` provider selection uses `when` predicates; provider `filter` field

`gww clean` selects a provider by evaluating a `when` predicate against the source's URI+tag context — identical to how `sources:` and `actions:` rules select — and taking the first provider in config order whose `when` matches. The provider's `filter` field (renamed from `merged`) holds the per-branch command template. This replaces the previous `providers.<kind>.host_patterns` regex list. **Hard replace, no back-compat shim.** The `--merged` git fallback (ADR-0015) and the user-config-only stance (ADR-0019) are unchanged; only the matching mechanism and field name change.

## Why `when` instead of `host_patterns`

gww already had a battle-tested rule-selection mechanism — the `when` predicate evaluated by `gww.template` against a URI+tag context — used by both `sources:` routing and `actions:` gating. The provider block was the odd one out, carrying a bespoke `host_patterns` regex list with its own compile step and its own resolution code. Two mechanisms for "pick the first rule that matches this URI" is one too many:

1. **One vocabulary.** Users who already write `when: '"github" in host()'` for a source rule now write the same predicate for a provider. No second dialect (regex-against-host) to learn.
2. **More expressive.** `when` sees the full URI context (`host()`, `port()`, `protocol()`, `path(n)`, `uri()`) plus tags, not just the host string. Selecting on `port()`, path prefix, or a tag is now possible where `host_patterns` could only match the host.
3. **Less code.** `find_matching_source_rule` and `find_matching_provider` collapse onto one shared primitive (`first_matching_rule` in `src/gww/config/rule_matching.py`); the host-pattern compile/match code is deleted.

## What changed structurally

- `providers` stays a named map, but the name is now **free-form** — the `github`/`gitlab`/`gitea` `kind` constraint is dropped. A provider is a named filter-check rule, not intrinsically a forge kind.
- `ProviderConfig.kind` → `ProviderConfig.name` (parallels `SourceRule.name`); `host_patterns` is gone, `when: str` is added; `merged` → `filter`.
- Provider `when` sees the **same context as source-rule `when`**: URI functions + tags, **no `branch()`**. `branch()` remains available in the per-branch `filter` template, evaluated later.
- A lingering `host_patterns` or `merged` key in a user's config is **silently ignored** (unknown keys aren't rejected today; this ADR doesn't add rejection). Neither is migrated.
- Tags passed via `gww clean --tag key=value` are available in both the provider's `when` predicate (for selection) and the `filter` template (for per-branch logic).
- The `tag()` function accepts an optional default parameter: `tag("name", "default")` returns `"default"` if the tag is missing.

## What's unchanged

- **No-match / no origin URI → `git branch --merged <default>`** fallback (ADR-0015/0019). The stderr warning that fires when providers *are* declared but none match still fires.
- **First match wins**, walking the map in config order.
- The `filter` command contract is still exit-code-only (ADR-0018).
- No env override, no built-in host defaults (ADR-0019).

## Considered Options

- **Keep `host_patterns`** — rejected: a second rule-selection dialect for no benefit; less expressive than `when`; duplicate resolution code.
- **`when` predicate (this ADR)** — chosen: one vocabulary, more expressive, shared primitive.
- **Add `branch()` to provider `when`** — rejected: the branch isn't known at selection time (a provider is chosen once per source, `filter` runs per branch); `branch()` stays in the `filter` template where it belongs.

## Supersedes

- The `host_patterns` matching mechanism of ADR-0019. ADR-0019's *stance* (single-layer, user-config-only, no env override, no built-in defaults, git fallback) is preserved verbatim; only "test the origin host against `host_patterns`" becomes "evaluate the `when` predicate".
- The `merged` field name in provider config, replaced with `filter` to reflect the field's general purpose (exit-0 = cleanable, not strictly "merged").
- The `Origin-based provider detection`, `Provider`, `Provider selection`, and `Provider merged command` glossary entries in `CONTEXT.md` (updated in lockstep).
- The `host_patterns` example blocks in ADR-0018, README.md, README.ru.md, and docs/architecture.md (updated in lockstep).

## Correction — phantom reference modules

ADR-0017/0019, CONTEXT.md, README.md/ru.md, and architecture.md referenced `src/gww/providers/{github,gitlab,gitea}.py` as per-kind "reference modules." **Those files never existed** — the package was only `base.py` + `__init__.py`, both now deleted along with the whole `src/gww/providers/` package. There are no per-kind reference modules; the only worked examples live in the commented `providers:` block of the `gww init config` template.
