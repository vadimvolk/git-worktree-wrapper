# 0006 — Regex preprocessor for templates before simpleeval evaluation

Templates look like `~/Developer/{host()}/{path(1)}/{branch()}` and need both function evaluation (`branch()` → `feature-x`) and a way to embed a literal parenthesis (`(my folder)`) without it being parsed as a function call. We preprocess with regex (escapes first, then function-call extraction), hand the result to `simpleeval` for evaluation, and substitute results back into the template. The architecture explicitly disallows nested function calls, which is what makes the regex approach viable.

## Considered Options

- **AST parsing** — Rejected: overkill for the non-nested template grammar; adds complexity for no observable benefit.
- **Full recursive parser** — Rejected: the architecture specifies non-nested function calls; recursive parsing would also need to handle the escape rule.
- **Pure string substitution** — Rejected: cannot evaluate functions; templates would be limited to fixed strings.

## Implementation Notes

- Escape rule: `((` → `(` and `))` → `)` (double parens denote a literal single paren). This is intuitive in YAML config.
- Function-call regex: `[a-zA-Z_][a-zA-Z0-9_]*\s*\([^()]*\)` — matches a non-nested call.
- Edge cases: function names with underscores, empty argument lists, surrounding whitespace, negative numeric arguments (`path(-2)`), and `((my folder))` must survive preprocessing intact.
- Performance: regex on a typical template (a few hundred characters) is well under a millisecond.
- Error handling: missing function or invalid argument should raise a clear error that includes the template source.