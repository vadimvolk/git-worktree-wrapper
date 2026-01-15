# Research: Git Worktree Wrapper Implementation

**Date**: 2025-01-27  
**Plan**: `plan.md`

This document consolidates research findings for all "NEEDS CLARIFICATION" items identified in the implementation plan.

## 1. simpleeval Library Customization

### Decision
Use `simpleeval` library with custom subclass `StrictSimpleEval` that enforces strict type checking and provides user-friendly error messages.

### Rationale
- `simpleeval` is designed for safe expression evaluation (unlike `eval()` which is unsafe)
- Supports adding custom functions via `functions` parameter
- Can be subclassed to override `_eval_call()` for type checking
- Provides exception types (`NameNotDefined`, `FunctionNotDefined`) for error handling
- Lightweight and well-maintained

### Implementation Approach
1. Create a `typed_fn` decorator that validates argument types and count
2. Subclass `SimpleEval` as `StrictSimpleEval` to intercept function calls
3. Override `_eval_call()` to validate types before execution
4. Raise custom `FunctionTypeError` exceptions with clear messages including:
   - Function name
   - Expected argument types
   - Actual argument types received
   - Argument position if applicable

### Alternatives Considered
- **Standard library `eval()`**: Rejected - unsafe for user-provided config, security risk
- **Custom parser**: Rejected - too complex, error-prone, reinventing the wheel
- **Other expression evaluators**: Considered but `simpleeval` is most popular and actively maintained

### Notes
- Must handle edge cases: wrong number of arguments, wrong types, undefined functions
- Error messages should be user-friendly (not raw Python tracebacks)
- Consider checking argument count in `_eval_call()` before type checking

---

## 2. YAML Library Choice

### Decision
Use `ruamel.yaml` with round-trip mode (`typ='rt'`) for preserving comments and formatting.

### Rationale
- **Preserves comments**: Critical for config files with inline documentation
- **Preserves formatting**: Maintains user's formatting preferences (quotes, indentation, style)
- **Preserves key ordering**: Maintains original key order in mappings
- **Round-trip capability**: Can load, modify, and dump without losing metadata
- **Active maintenance**: Well-maintained library with good documentation

### Comparison with PyYAML

| Feature | ruamel.yaml | PyYAML |
|---------|-------------|--------|
| Preserve comments | ✅ Yes | ❌ No |
| Preserve formatting | ✅ Yes | ❌ No |
| Preserve key ordering | ✅ Yes | ⚠️ Limited |
| Performance | Slower (pure Python) | Faster (C extension) |
| API complexity | More complex | Simpler |
| Round-trip support | ✅ Full | ❌ None |

### Implementation Approach
```python
from ruamel.yaml import YAML

yaml = YAML(typ='rt')  # round-trip mode
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)

data = yaml.load(open('gww.yml'))
# ... modify data ...
yaml.dump(data, open('gww.yml', 'w'))
```

### Alternatives Considered
- **PyYAML**: Rejected - loses comments and formatting, not suitable for human-edited configs
- **JSON**: Rejected - no comments, less readable, loses user-friendly format
- **TOML**: Considered but YAML is more widely known and the architecture specifies YAML

### Notes
- Use pure Python mode (not C extension) for full comment support
- Some edge cases: minimal YAMLs (only comments) may need special handling
- Comment positions can shift slightly on reassignments (acceptable trade-off)

---

## 3. XDG_CONFIG_HOME Handling

### Decision
Use standard library only with a custom function that handles cross-platform paths, respecting XDG_CONFIG_HOME on Linux and platform conventions on macOS/Windows.

### Rationale
- **No external dependency**: Aligns with minimalism principle
- **Standard library sufficient**: `os`, `pathlib`, `sys` provide all needed functionality
- **Cross-platform support**: Can handle Linux, macOS, Windows with simple logic
- **XDG compliance**: Properly respects `$XDG_CONFIG_HOME` when set

### Implementation Approach
```python
import os
from pathlib import Path
import sys

def user_config_dir(appname: str = "gww") -> Path:
    """Return cross-platform config directory following XDG/OS conventions."""
    home = Path.home()
    
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA", home / "AppData" / "Roaming")
        return Path(base) / appname
    elif sys.platform == "darwin":
        base = home / "Library" / "Application Support"
        return base / appname
    else:
        # Linux/Unix: $XDG_CONFIG_HOME or ~/.config
        xdg = os.environ.get("XDG_CONFIG_HOME")
        if xdg and Path(xdg).is_absolute():
            base = Path(xdg)
        else:
            base = home / ".config"
        return base / appname

def get_config_path() -> Path:
    """Return full path to config file: {user_config_dir()}/config.yml"""
    return user_config_dir() / "config.yml"
```

### Behavior
- **Linux**: Uses `$XDG_CONFIG_HOME` if set and absolute, otherwise `~/.config/gww/config.yml`
- **macOS**: Uses `~/Library/Application Support/gww/config.yml`
- **Windows**: Uses `%APPDATA%\gww\config.yml` (or `~/AppData/Roaming/gww/config.yml`)

### Alternatives Considered
- **platformdirs library**: Considered but adds dependency. Rejected per minimalism principle - standard library is sufficient.
- **appdirs library**: Older, less maintained. Rejected.
- **xdg-base-dirs library**: Unix-only. Rejected - need cross-platform support.

### Notes
- Must validate that `XDG_CONFIG_HOME` is absolute if set
- Fallback to `~/.config` if `XDG_CONFIG_HOME` is unset or invalid
- Config file location: `{user_config_dir()}/config.yml` where `user_config_dir()` returns `{XDG_CONFIG_HOME}/gww` or platform equivalent
- Config is cached in memory only during `gww` command execution (no file change detection needed)

---

## 4. Git Worktree API

### Decision
Use `subprocess` to call `git` commands directly rather than libgit2/pygit2.

### Rationale
- **No external dependency**: Aligns with minimalism principle
- **Matches user expectations**: Uses same `git` binary users have, behavior matches exactly
- **Worktree support**: Works correctly with `--git-dir` and `--work-tree` flags
- **Simpler error handling**: Git's error messages are user-friendly
- **Sufficient performance**: For CLI tool, subprocess overhead is acceptable

### Implementation Approach
```python
import subprocess
from pathlib import Path

def is_worktree_clean(worktree_path: Path) -> bool:
    """Check if worktree has uncommitted changes."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=worktree_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return not bool(result.stdout.strip())

def get_worktree_branch(worktree_path: Path) -> str:
    """Get current branch name in worktree."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=worktree_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return result.stdout.strip()
```

### Comparison with pygit2

| Criteria | subprocess + git | pygit2/libgit2 |
|----------|------------------|----------------|
| Dependencies | None (git binary) | pygit2 + libgit2 |
| Performance | Slower (process spawn) | Faster (in-process) |
| Behavior match | Exact (uses git) | Very good (some edge cases) |
| Error messages | User-friendly | Programmatic flags |
| Worktree support | Via flags | Via repo path |

### Alternatives Considered
- **pygit2/libgit2**: Considered for performance but rejected - adds dependency, more complex, potential behavior differences
- **GitPython**: Considered but adds dependency, similar trade-offs to pygit2

### Notes
- Use `--porcelain` format for stable, parseable output
- Handle `--git-dir` and `--work-tree` correctly for worktree operations
- Consider `git diff --quiet` for faster dirty checks if needed
- Error handling: capture stderr for user-friendly error messages

---

## 5. Shell Autocompletion

### Decision
Use argparse's built-in completion generation methods (`get_bash_complete()`, `get_zsh_complete()`, `get_fish_complete()`) for static completion, with custom Python logic for dynamic values (branches, worktrees).

### Rationale
- **No external dependency**: Built into argparse (Python 3.8+)
- **Multi-shell support**: Native support for bash, zsh, fish
- **Static + dynamic**: Can generate static scripts and add dynamic completers
- **Simple integration**: `gww init shell` command can generate and install scripts
- **Maintainable**: Standard approach, well-documented

### Implementation Approach

1. **Generate completion scripts**:
```python
def generate_completion(shell: str) -> str:
    parser = build_parser()  # Main argparse parser
    if shell == "bash":
        return parser.get_bash_complete()
    elif shell == "zsh":
        return parser.get_zsh_complete()
    elif shell == "fish":
        return parser.get_fish_complete()
    else:
        raise ValueError(f"Unsupported shell: {shell}")
```

2. **Dynamic completion for branches/worktrees**:
   - Use custom completer functions that query git/fs
   - Integrate with argparse's `choices` parameter or custom completers
   - Ensure completers are fast (minimal imports, cache if needed)

3. **Installation**:
   - Bash: `~/.bash_completion.d/gww` or system directory
   - Zsh: `$fpath/_gww` or `~/.zsh/completions/_gww`
   - Fish: `~/.config/fish/completions/gww.fish`

### Comparison with Alternatives

| Approach | Pros | Cons |
|----------|------|------|
| **argparse built-in** | No deps, multi-shell, standard | Manual script generation |
| **argcomplete** | Dynamic, well-maintained | No native Fish support, requires setup |
| **pyparam** | Flexible, Fish support | Adds dependency |
| **Custom shell scripts** | Full control | More maintenance, shell-specific code |

### Alternatives Considered
- **argcomplete**: Considered but rejected - adds dependency, limited Fish support
- **pyparam**: Considered but rejected - adds dependency, less common
- **Custom shell scripts**: Considered but rejected - more maintenance, shell-specific

### Notes
- Dynamic completers must be fast (TAB press responsiveness)
- Cache branch/worktree lists if expensive to compute
- Document installation instructions for each shell
- Test completion behavior with various argument combinations

---

## 6. Template Preprocessing

### Decision
Use regex-based approach for initial function call detection, then validate/evaluate with simpleeval. Handle literal parentheses by requiring double parentheses `((` for escaping.

### Rationale
- **Performance**: Regex is fast for initial parsing
- **Simplicity**: Architecture specifies simple approach (no nested function handling)
- **Clear escaping**: Double parentheses `((` → `(` is intuitive
- **Validation**: simpleeval handles actual evaluation safely

### Implementation Approach

1. **Preprocessing step**:
   - Find function call patterns: `function_name(arg1, arg2)`
   - Replace double parentheses `((` with single `(` (escape sequence)
   - Extract function calls using regex (non-nested is sufficient per architecture)
   - Replace function calls with placeholders
   - Evaluate function calls via simpleeval
   - Substitute results back into template

2. **Regex pattern** (simplified, no nesting):
```python
import re

# Match function calls: name(args)
FUNCTION_CALL_PATTERN = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^()]*)\)')

def preprocess_template(template: str) -> str:
    # Replace escaped parentheses
    template = template.replace('((', '\x00ESCAPE_OPEN\x00')
    template = template.replace('))', '\x00ESCAPE_CLOSE\x00')
    
    # Find and evaluate function calls
    # ... extract, evaluate, substitute ...
    
    # Restore escaped parentheses
    template = template.replace('\x00ESCAPE_OPEN\x00', '(')
    template = template.replace('\x00ESCAPE_CLOSE\x00', ')')
    
    return template
```

3. **Edge case handling**:
   - `not_function((my folder))` → `not_function(my folder)` (double parens become single)
   - `path(-2)` → evaluated as function call
   - `path((escaped))` → `path(escaped)` after preprocessing

### Alternatives Considered
- **AST parsing**: Considered but rejected - overkill for simple templates, more complex
- **Full recursive parsing**: Considered but rejected - architecture specifies no nested functions
- **Simple string replacement**: Considered but rejected - need function evaluation

### Notes
- Architecture explicitly states: "Do not bother with nested functions for that case"
- Must handle edge cases: function names with underscores, empty arguments, whitespace
- Performance: Regex is fast enough for typical template sizes
- Error handling: Clear errors if function not found or invalid arguments

---

## Summary of Decisions

| Research Area | Decision | Justification |
|---------------|----------|---------------|
| Expression evaluation | simpleeval with custom subclass | Safe, extensible, well-maintained |
| YAML parsing | ruamel.yaml (round-trip) | Preserves comments and formatting |
| Config directory | Standard library custom function | No dependency, cross-platform |
| Git operations | subprocess + git commands | No dependency, matches user expectations |
| Shell completion | argparse built-in methods | No dependency, multi-shell support |
| Template parsing | Regex + simpleeval | Simple, fast, handles edge cases |

All decisions align with the constitution's minimalism principle while meeting functional requirements.
