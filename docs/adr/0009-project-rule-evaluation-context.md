# 0009 — Unify project-rule evaluation context around `TemplateContext`

Project rules (`actions:` in the config) had a `when:` predicate that could only see filesystem-shaped helpers (`source_path`, `file_exists`, `dir_exists`, `path_exists`, `dest_path`) and tag functions. URI functions (`host()`, `port()`, `protocol()`, `uri()`, `path()`) and branch functions (`branch()`, `norm_branch()`) were registered in the same `FunctionRegistry` and therefore reachable in theory, but the project-rule evaluation pipeline built a fresh `TemplateContext(source_path=..., tags=...)` with `uri=None` and `branch=None`, so calling any of them raised `"No URI context available"` or `"No branch context available"` at runtime.

The user-facing symptom was a config like

```yaml
- when: '"somehost" in host'
  after_clone:
    - command: "echo hello world"
  after_add:
    - command: "echo here i am"
```

failing with `Predicate evaluation failed: No URI context available for host() function`. We fix this by routing every evaluation site — URI predicates, source/worktree path templates, project-rule predicates, project-rule command templates — through the same `TemplateContext` object that callers populate from the operation in progress.

## Why a single context object

The pre-existing `TemplateContext` dataclass already carried `uri`, `branch`, `source_path`, `tags`. It was used by `config/resolver.py` for source-rule matching and path template evaluation. Adding `dest_path` to it (the only field project rules needed that templates did not) kept the project-rule pipeline a single-context pipeline: `apply_actions(rules, context, kind)` instead of `apply_actions(rules, source_path, tags, dest_path, kind)`.

The pre-refactor signature had five positional arguments, two of which (`tags`, `dest_path`) were effectively partial projections of context-shaped data. The refactor replaces them with the single `TemplateContext` argument that already aggregates them.

`create_project_functions` similarly moved from `(source_path, dest_path)` to `(context)`, reading both fields off the supplied context. It now raises `ValueError` if `context.source_path` is `None`, since project predicates cannot meaningfully run without one.

## What is available per operation

Project-rule predicates see everything the calling command actually knows:

| Field | `clone` | `add` |
|---|---|---|
| `uri` | from `ctx.uri` (CLI argument) | from `git remote get-url origin` of the source repo |
| `branch` | `git rev-parse --abbrev-ref HEAD` of the source repo after clone; `""` if detached | `ctx.branch` (the branch being added) |
| `source_path` | the cloned source repo | the source repo |
| `dest_path` | `source_path` (same path) | the worktree path |
| `tags` | `ctx.tags` | `ctx.tags` |

Two asymmetries fall out of this and are documented in `CONTEXT.md` (`URI as seen by clone vs add`, `Branch as seen by clone vs add`):

1. The URI in `add` predicates is whatever `git remote get-url origin` returns *now*, which can diverge from the original clone URL after `git remote set-url …`. For host-based predicates this rarely matters; for protocol-sensitive predicates it can.
2. The branch in `clone` predicates is whatever git checked out by default (the remote's HEAD). It is empty string when HEAD ends up detached so predicates evaluate to a defined but non-matching state rather than raising.

## Why soft-fail on detached HEAD in `clone`

`clone_repository` always produces a working repository, but HEAD is sometimes detached (shallow clones of a specific tag, certain CI workflows). `get_current_branch` raises `GitCommandError` on detached HEAD, which would turn any project rule that happened to reference `branch()` into a hard error — even when the rule would have evaluated to `False` naturally.

`try_get_current_branch` wraps the call and returns `""` on failure. `branch()` in the registry then returns `""`, and `"main" in branch()` evaluates to `False` without raising. This mirrors how `tag()` returns `""` for a missing tag — defined-but-non-matching, not an error.

## Considered Options

- **Add explicit `uri` and `branch` kwargs to `apply_actions`.** Rejected: leaves two context-shaped arguments hanging off the signature once `source_path`, `tags`, `dest_path` are already threaded. The caller still has to remember which combination of fields populate which function family, which is exactly what `TemplateContext` was designed to encode.
- **Introduce a new `ProjectRuleContext` type that wraps `TemplateContext` and adds `dest_path`.** Rejected: pure ceremony. `dest_path` is a real field of template evaluation (project predicates use it via `dest_path()`); it belongs on `TemplateContext` itself.
- **Read the URI/branch inside `apply_actions` via git calls.** Rejected: makes the actions layer depend on git state it shouldn't know about, and the caller already has the values in hand (parsed in `clone.py` and `add.py` respectively).
- **Pass `dest_path` separately, keep `TemplateContext` "pure" for templates.** Rejected: pretends the templates-only use is the canonical one. In practice `TemplateContext` is already the cross-cutting evaluation context — the templates, URI predicates, and project predicates all use the same `FunctionRegistry`. Pretending otherwise would leave the type honest for one caller and dishonest for the others.

## Notes for future readers

- The decision to put `dest_path` on `TemplateContext` is the one that stretches the name most. The type is no longer purely "for template evaluation" — it is "for anything evaluated through `FunctionRegistry`". Renaming the type is intentionally deferred: it would touch every caller and the dataclass field set is stable, so the value of the rename is cosmetic.
- `try_get_current_branch` is intentionally not used by `add` — `add` already has the branch from `ctx.branch`, so re-reading it would be both slower and semantically wrong (it would read the worktree's branch, which equals `ctx.branch` only after `add_worktree` returns; before that, the branch may not yet exist locally).
- The validator docstring for `ProjectRule.when` previously read *"Expression evaluated against repository filesystem."* It now points at `TemplateContext`. The old wording was stale: project predicates were always evaluated against the unified registry, the bug was that the registry's URI/branch helpers were unreachable because the context left them `None`.