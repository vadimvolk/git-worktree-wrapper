# Implementation Plan: Git Worktree Wrapper (sgw)

**Branch**: `001-git-worktree-wrapper` | **Date**: 2025-01-27 | **Spec**: `architecture.md`
**Input**: Architecture specification from `/architecture.md`

**Note**: This plan is created using the `/speckit.plan` command workflow based on the architecture document.

## Summary

Build a CLI tool `sgw` that wraps git worktree functionality with configurable path templates, predicate-based routing, and project-specific actions. The tool uses YAML configuration with template evaluation for dynamic path generation, supports multiple git hosting providers, and provides commands for checkout, worktree management, migration, and shell autocompletion.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: 
- `simpleeval` - for predicate and template evaluation (NEEDS CLARIFICATION: version, customization approach)
- `pyyaml` or `ruamel.yaml` - for YAML config parsing (NEEDS CLARIFICATION: which library, why)
- Standard library: `subprocess`, `pathlib`, `argparse`, `shutil`

**Storage**: File system (YAML config in XDG_CONFIG_HOME, git repositories)  
**Testing**: pytest (TDD mandatory per constitution)  
**Target Platform**: Unix-like systems (Linux, macOS) with git installed  
**Project Type**: Single CLI application  
**Performance Goals**: 
- Command execution < 2 seconds for typical operations
- Config parsing < 100ms
- Template evaluation < 50ms

**Constraints**: 
- Must not interfere with native git commands
- Must maintain compatibility with standard git worktree behavior
- Minimal external dependencies (justify each)
- All functions must have type hints

**Scale/Scope**: 
- ~7 CLI commands
- Configurable path templates with function evaluation
- Support for multiple git hosting providers via predicates
- Project-specific action hooks
- Shell autocompletion for 3 shells (bash, zsh, fish)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Test-Driven Development (TDD) ✅
- **Status**: PASS
- **Compliance**: All features will follow strict TDD workflow. Tests written first, then implementation.

### II. Minimalism & Dependency Management ⚠️
- **Status**: NEEDS JUSTIFICATION
- **Dependencies to justify**:
  - `simpleeval`: Required for safe expression evaluation. Standard library `eval()` is unsafe. Alternative: custom parser (too complex).
  - YAML library: Required for config parsing. Standard library has no YAML support. Alternative: JSON (less user-friendly, loses comments).

### III. Single Command Interface ✅
- **Status**: PASS
- **Compliance**: Single entry point `sgw` with consistent subcommand pattern: `sgw <command> [args] [options]`

### IV. Python 3.11+ & uv Requirements ✅
- **Status**: PASS
- **Compliance**: Will use Python 3.11+ and uv exclusively for dependency management.

### V. Git Worktree Focus ✅
- **Status**: PASS
- **Compliance**: Wrapper around git worktree, maintains compatibility, doesn't interfere with native git.

## Project Structure

### Documentation (this feature)

```text
specs/001-git-worktree-wrapper/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
├── sgw/
│   ├── __init__.py
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── main.py           # Entry point, argument parsing
│   │   └── commands/          # Command implementations
│   │       ├── __init__.py
│   │       ├── checkout.py
│   │       ├── add.py
│   │       ├── remove.py
│   │       ├── pull.py
│   │       ├── migrate.py
│   │       └── init.py        # init config, init shell
│   ├── config/
│   │   ├── __init__.py
│   │   ├── loader.py          # Load and parse config.yml
│   │   ├── validator.py       # Validate config structure
│   │   └── resolver.py        # Resolve paths using templates
│   ├── template/
│   │   ├── __init__.py
│   │   ├── evaluator.py       # Template evaluation engine
│   │   └── functions.py        # Built-in template functions (path, norm_branch, etc.)
│   ├── git/
│   │   ├── __init__.py
│   │   ├── worktree.py        # Git worktree operations wrapper
│   │   ├── repository.py       # Git repository operations
│   │   └── branch.py           # Branch operations
│   ├── actions/
│   │   ├── __init__.py
│   │   ├── executor.py         # Execute project actions (abs_copy, rel_copy, command)
│   │   └── matcher.py          # Match projects by predicates
│   └── utils/
│       ├── __init__.py
│       ├── xdg.py              # XDG_CONFIG_HOME handling
│       └── shell.py             # Shell autocompletion generation

tests/
├── unit/
│   ├── test_template_evaluator.py
│   ├── test_config_loader.py
│   ├── test_git_worktree.py
│   ├── test_actions_executor.py
│   └── test_cli_commands.py
├── integration/
│   ├── test_checkout_flow.py
│   ├── test_worktree_management.py
│   └── test_migration.py
└── fixtures/
    ├── configs/                # Sample config files
    └── repos/                   # Test git repositories

pyproject.toml                   # uv project configuration
README.md
```

**Structure Decision**: Single project structure (Option 1) chosen. This is a CLI tool with no frontend/backend separation needed. The structure separates concerns: CLI commands, configuration management, template evaluation, git operations, and action execution. Tests are organized by type (unit/integration) following pytest conventions.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| External dependency: simpleeval | Safe expression evaluation for predicates and templates | Standard library `eval()` is unsafe for user-provided config. Custom parser would be too complex and error-prone. |
| External dependency: YAML library | User-friendly config format with comments | JSON lacks comments and is less readable. Config files need documentation inline. |
| Template evaluation engine | Complex path template system with function calls | Simple string substitution insufficient for path(-2), norm_branch(), etc. Need function evaluation. |

## Phase 0 Research Areas

1. **simpleeval library**: 
   - Research customization for strict type checking
   - How to add custom functions safely
   - Error message formatting for user-friendly errors

2. **YAML library choice**:
   - Compare `pyyaml` vs `ruamel.yaml`
   - Which preserves comments (needed for config examples)
   - Performance and maintenance status

3. **XDG_CONFIG_HOME**:
   - Cross-platform handling (Linux vs macOS)
   - Fallback behavior when not set
   - Standard library support

4. **Git worktree API**:
   - Subprocess vs libgit2 (Python bindings)
   - Error handling patterns
   - Detecting worktree state (clean/dirty)

5. **Shell autocompletion**:
   - Bash/zsh/fish completion formats
   - Dynamic completion (branch names, worktree paths)
   - Integration with argparse

6. **Template preprocessing**:
   - Parsing function calls vs literal parentheses
   - Handling edge cases like `not_function((my folder))`
   - Performance of regex vs manual parsing
