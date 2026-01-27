# Agents

This document defines AI agents and their roles for the Git Worktree Wrapper (GWW) project.

## Project Overview

GWW is a CLI tool (`gww`) that wraps git worktree functionality with:
- Configurable path templates using functions like `path(n)`, `branch()`, `norm_branch()`, `tag()`
- Condition-based routing based on URI conditions (host, path, protocol, tags)
- Project-specific actions (file copies, commands) after clone or worktree creation
- Shell completion support (bash, zsh, fish)

**Tech Stack**: Python 3.11+, simpleeval, ruamel.yaml, pytest, mypy

**Key Directories**:
- `src/gww/` - Main source code
- `tests/` - Test suite (unit and integration)
- `specs/001-git-worktree-wrapper/` - Feature specifications
- `.cursor/commands/` - Cursor command definitions

## Agents

### 🛠️ Development Agent

**Role**: Implement features, fix bugs, and maintain the codebase.

**Context**:
- Follow the architecture defined in `architecture.md`
- Use type hints for all function arguments and return values
- Use `uv` for dependency management
- Customize `simpleeval` for strict function argument checking
- Pre-process templates for function calls (handle escaped parentheses)

**Key Modules**:
- `src/gww/cli/commands/` - CLI command implementations
- `src/gww/git/` - Git operations (repository, worktree, branch)
- `src/gww/config/` - Configuration loading, validation, resolution
- `src/gww/template/` - Template evaluation and functions
- `src/gww/actions/` - Action execution and matching
- `src/gww/utils/` - Utility functions (shell, URI, XDG)

**Guidelines**:
- Always add type hints
- Follow existing code patterns
- Handle errors gracefully with clear messages
- Use exit codes: 0 (success), 1 (error), 2 (config error)
- Test changes with both unit and integration tests

**Common Tasks**:
- Adding new CLI commands
- Extending template functions
- Implementing new action types
- Improving error handling
- Refactoring for maintainability

---

### 🧪 Testing Agent

**Role**: Write and maintain comprehensive tests.

**Context**:
- Tests are in `tests/unit/` and `tests/integration/`
- Use pytest with markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.slow`
- Run tests with: `uv run pytest`
- Coverage target: Maintain high coverage for core functionality

**Test Structure**:
- Unit tests: Test individual functions/modules in isolation
- Integration tests: Test full CLI command workflows
- Use fixtures for common setup (temp directories, git repos, config files)

**Guidelines**:
- Write tests before or alongside implementation
- Test both success and error cases
- Test edge cases (empty strings, missing files, invalid configs)
- Use descriptive test names: `test_<function>_<scenario>_<expected_result>`
- Mock external dependencies (git commands, file system) when appropriate

**Key Test Files**:
- `test_cli_commands.py` - CLI command integration tests
- `test_worktree_management.py` - Worktree operations
- `test_config_loader.py` - Configuration loading
- `test_template_functions.py` - Template evaluation

---

### 📚 Documentation Agent

**Role**: Maintain documentation, README files, and specifications.

**Context**:
- Main docs: `README.md` (English) and `README.ru.md` (Russian)
- Specifications: `specs/001-git-worktree-wrapper/`
- Architecture: `architecture.md`

**Guidelines**:
- Keep README.md up-to-date with CLI changes
- Document all template functions with examples
- Include usage examples for common workflows
- Maintain both English and Russian versions
- Update quickstart guides when adding features

**Documentation Sections**:
- Installation instructions (uv, pipx, pip)
- Quick start guide
- Configuration examples
- Template function reference
- Command reference
- Development setup

**Common Tasks**:
- Updating README after feature additions
- Adding examples for new template functions
- Documenting breaking changes
- Syncing English and Russian docs

---

### ⚙️ Configuration Agent

**Role**: Work with configuration files, templates, and path resolution.

**Context**:
- Config file: `~/.config/gww/config.yml` (Linux) or `~/Library/Application Support/gww/config.yml` (macOS)
- Config structure: `default_sources`, `default_worktrees`, `sources`, `actions`
- Template evaluation uses `simpleeval` with custom functions

**Template Functions**:
- URI: `host()`, `port()`, `protocol()`, `uri()`, `path(n)`
- Branch: `branch()`, `norm_branch(replacement)`
- Utility: `time_id(fmt)`
- Actions: `source_path()`, `dest_path()`, `file_exists(path)`, `dir_exists(path)`, `path_exists(path)`
- Tags: `tag(name)`, `tag_exist(name)`

**Guidelines**:
- Validate config syntax and semantics
- Provide clear error messages for invalid configs
- Support XDG config directory standards
- Handle template evaluation errors gracefully
- Document template function behavior

**Common Tasks**:
- Adding new template functions
- Improving config validation
- Enhancing path resolution logic
- Supporting new condition operators

---

### 🖥️ CLI Agent

**Role**: Work with CLI commands, user interface, and shell integration.

**Context**:
- Main entry: `src/gww/cli/main.py`
- Commands: `clone`, `add`, `remove`, `pull`, `migrate`, `init`
- Shell aliases: `gwc` (clone), `gwa` (add), `gwr` (remove)
- Shell completion: bash, zsh, fish

**CLI Commands**:
- `gww clone <uri> [--tag key=value]...` - Clone repository
- `gww add <branch> [-c] [--tag key=value]...` - Add worktree
- `gww remove <branch|path> [-f]` - Remove worktree
- `gww pull` - Update source repository
- `gww migrate <path>... [--dry-run] [--copy | --inplace]` - Migrate repositories
- `gww init config` - Create default config
- `gww init shell <shell>` - Install shell completion

**Guidelines**:
- Use argparse for argument parsing
- Provide helpful error messages
- Support `--verbose` and `--quiet` flags
- Handle user prompts for navigation confirmation
- Generate shell completion scripts correctly

**Common Tasks**:
- Adding new CLI options
- Improving error messages
- Enhancing shell completion
- Adding user prompts/confirmations

---

### 🔍 Code Review Agent

**Role**: Review code changes for quality, consistency, and correctness.

**Guidelines**:
- Check type hints are present and correct
- Verify error handling is appropriate
- Ensure tests cover new functionality
- Check code follows project patterns
- Verify documentation is updated
- Check for security issues (path traversal, command injection)
- Ensure mypy type checking passes: `uv run mypy src/gww`

**Review Checklist**:
- [ ] Type hints on all functions
- [ ] Error handling with appropriate exit codes
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] No hardcoded paths or secrets
- [ ] Follows existing code style
- [ ] Mypy passes without errors

---

## General Guidelines for All Agents

### Code Quality
- Use type hints everywhere
- Run `uv run mypy src/gww` before committing
- Follow Python 3.11+ best practices
- Keep functions focused and testable

### Git Workflow
- Use the speckit workflow commands (`.cursor/commands/speckit.*`)
- Create feature branches: `NN-feature-name`
- Write specs before implementation
- Update tasks.md as work progresses

### Testing
- Write tests for new features
- Run `uv run pytest` before committing
- Maintain test coverage
- Test on both Linux and macOS when possible

### Documentation
- Update README.md for user-facing changes
- Document new template functions
- Add examples for new features
- Keep architecture.md current

### Dependencies
- Use `uv` for dependency management
- Add new dependencies to `pyproject.toml`
- Run `uv sync` after dependency changes

---

## Quick Reference

**Run tests**: `uv run pytest`
**Type check**: `uv run mypy src/gww`
**Install deps**: `uv sync`
**Run CLI**: `uv run gww --help`
**Create spec**: Use `/speckit.specify` command
**Create plan**: Use `/speckit.plan` command
