# 0001 — simpleeval with StrictSimpleEval subclass for expression evaluation

User-supplied expressions appear in two places: `when` conditions (used to route source/worktree rules) and template functions like `path(n)` / `branch()`. We use `simpleeval` because it is the well-maintained safe-expression evaluator for Python, and subclass it as `StrictSimpleEval` to enforce strict argument-type checking at call time and produce user-friendly errors instead of raw tracebacks.

## Considered Options

- **Standard library `eval()`** — Rejected: unsafe for user-provided config; arbitrary code execution is a security risk.
- **Custom parser** — Rejected: too complex, error-prone, reinvents the wheel for a well-solved problem.
- **Other expression evaluators (asteval, etc.)** — Considered; `simpleeval` is more popular and actively maintained.

## Implementation Notes

- Subclass `SimpleEval` and override `_eval_call()` to validate argument count and types before execution.
- Provide a `typed_fn` decorator that each custom function (`path`, `branch`, `norm_branch`, …) is wrapped with; the subclass consults this metadata.
- Raise a custom `FunctionTypeError` carrying function name, expected types, actual types, and argument position so config errors are actionable.
- Edge cases to handle: wrong number of arguments, wrong types, undefined functions. Keep messages user-friendly — no raw Python tracebacks.