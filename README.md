# SGW - Git Worktree Wrapper

A CLI tool that wraps git worktree functionality with configurable path templates, predicate-based routing, and project-specific actions.

## Features

- **Configurable path templates**: Dynamic path generation using templates with functions like `path()`, `branch()`, `norm_branch()`
- **Predicate-based routing**: Route repositories to different locations based on URI predicates (host, path, protocol)
- **Project actions**: Execute custom actions (file copies, commands) after clone or worktree creation
- **Shell completion**: Bash, Zsh, and Fish completion support

## Requirements

- Python 3.11+
- Git
- Unix-like system (Linux, macOS)

## Installation

### Using uv (recommended)

```bash
# Clone the repository
git clone https://github.com/vadimvolk/git-worktree-wrapper.git
cd git-worktree-wrapper

# Install with uv
uv sync

# Run sgw
uv run sgw --help
```

### Using pip

```bash
pip install .
sgw --help
```

## Quick Start

### 1. Initialize Configuration

```bash
sgw init config
```

This creates a default configuration file at `~/.config/sgw/config.yml` (Linux) or `~/Library/Application Support/sgw/config.yml` (macOS).

### 2. Clone a Repository

```bash
sgw clone https://github.com/user/repo.git
# Output: ~/Developer/sources/github/user/repo
```

### 3. Add a Worktree

```bash
cd ~/Developer/sources/github/user/repo
sgw add feature-branch
# Output: ~/Developer/worktrees/github/user/repo/feature-branch
```

### 4. Remove a Worktree

```bash
sgw remove feature-branch
# Output: Removed worktree: ~/Developer/worktrees/github/user/repo/feature-branch
```

### 5. Update Source Repository

```bash
sgw pull
# Output: Updated source repository: ~/Developer/sources/github/user/repo
```

## Configuration

Example `config.yml`:

```yaml
default_sources: ~/Developer/sources/default/path(-2)/path(-1)
default_worktrees: ~/Developer/worktrees/default/path(-2)/path(-1)/norm_branch()

sources:
  github:
    predicate: '"github" in host'
    sources: ~/Developer/sources/github/path(-2)/path(-1)
    worktrees: ~/Developer/worktrees/github/path(-2)/path(-1)/norm_branch()

  gitlab:
    predicate: '"gitlab" in host'
    sources: ~/Developer/sources/gitlab/path(-3)/path(-2)/path(-1)
    worktrees: ~/Developer/worktrees/gitlab/path(-3)/path(-2)/path(-1)/norm_branch()

projects:
  - predicate: file_exists("local.properties")
    source_actions:
      - abs_copy: ["~/sources/default-local.properties", "local.properties"]
    worktree_actions:
      - rel_copy: ["local.properties"]
```

### Template Functions

| Function | Description | Example |
|----------|-------------|---------|
| `path(n)` | Get URI path segment by index (0-based, negative for reverse) | `path(-1)` → last segment |
| `branch()` | Current branch name | `feature/new-ui` |
| `norm_branch(sep)` | Branch name with `/` replaced | `norm_branch()` → `feature-new-ui` |
| `worktree()` | Worktree name (if named) | `my-worktree` |
| `prefix_worktree(prefix)` | Prefix + worktree name, or empty | `prefix_worktree("-")` → `-my-worktree` |
| `norm_prefix_branch()` | Worktree name + branch, or normalized branch | `my-worktree-feature-new-ui` |

## Commands

| Command | Description |
|---------|-------------|
| `sgw clone <uri>` | Clone repository to configured location |
| `sgw add <branch> [name] [-c]` | Add worktree for branch (optionally create branch) |
| `sgw remove <branch\|path> [-f]` | Remove worktree |
| `sgw pull` | Update source repository |
| `sgw migrate <path> [--dry-run] [--move]` | Migrate repositories to new locations |
| `sgw init config` | Create default configuration file |
| `sgw init shell <shell>` | Install shell completion (bash/zsh/fish) |

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov

# Run only unit tests
uv run pytest tests/unit/

# Run only integration tests
uv run pytest tests/integration/
```

### Type Checking

```bash
uv run mypy src/sgw
```

## License

MIT
