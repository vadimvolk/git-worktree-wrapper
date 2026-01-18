<!-- Language switcher -->
**English** | [Русский](README.ru.md)

# GWW - Git Worktree Wrapper

A CLI tool that wraps git worktree functionality with configurable path templates, predicate-based routing, and project-specific actions.

## Features

- **Configurable path templates**: Dynamic path generation using templates with functions like `path(n)`, `branch()`, `norm_branch()`, `tag()`
- **Predicate-based routing**: Route repositories to different locations based on URI predicates (host, path, protocol, tags)
- **Tag support**: Pass custom tags via `--tag` option for conditional routing and path organization
- **Project actions**: Execute custom actions (file copies, commands) after clone or worktree creation
- **Shell completion**: Bash, Zsh, and Fish completion support

## Requirements

- Python 3.11+
- Git
- Unix-like system (Linux, macOS)

## Installation

### Install the CLI (recommended)

#### Using uv

```bash
uv tool install "git+https://github.com/vadimvolk/git-worktree-wrapper.git"
gww --help
```

#### Using pipx

```bash
pipx install "git+https://github.com/vadimvolk/git-worktree-wrapper.git"
gww --help
```

### From source (development)

```bash
# Clone the repository
git clone git@github.com:vadimvolk/git-worktree-wrapper.git
cd git-worktree-wrapper

# Install with uv
uv sync

# Run gww
uv run gww --help
```

### From source using pip

```bash
# From a local checkout
cd git-worktree-wrapper
python -m pip install .
gww --help
```

## Quick Start

### 1. Initialize Configuration

```bash
gww init config
```

This creates a default configuration file at `~/.config/gww/config.yml` (Linux) or `~/Library/Application Support/gww/config.yml` (macOS).

### 2. Clone a Repository

```bash
gww clone https://github.com/user/repo.git
# Output: ~/Developer/sources/github/user/repo
```

### 3. Add a Worktree

```bash
cd ~/Developer/sources/github/user/repo
gww add feature-branch
# Output: ~/Developer/worktrees/github/user/repo/feature-branch
```

### 4. Remove a Worktree

```bash
gww remove feature-branch
# Output: Removed worktree: ~/Developer/worktrees/github/user/repo/feature-branch
```

### 5. Update Source Repository

```bash
gww pull
# Output: Updated source repository: ~/Developer/sources/github/user/repo
```

## Configuration

Example `config.yml`:

```yaml
default_sources: ~/Developer/sources/default/path(-2)/path(-1)
default_worktrees: ~/Developer/worktrees/default/path(-2)/path(-1)/norm_branch()

sources:
  github:
    predicate: '"github" in host()'
    sources: ~/Developer/sources/github/path(-2)/path(-1)
    worktrees: ~/Developer/worktrees/github/path(-2)/path(-1)/norm_branch()

  gitlab:
    predicate: '"gitlab" in host()'
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

#### URI Functions (available in templates, URI predicates, and project predicates)

| Function | Description | Example |
|----------|-------------|---------|
| `host()` | Get URI hostname | `host()` → `"github.com"` |
| `port()` | Get URI port (empty string if not specified) | `port()` → `""` or `"22"` |
| `protocol()` | Get URI protocol/scheme | `protocol()` → `"https"` or `"ssh"` |
| `uri()` | Get full URI string | `uri()` → `"https://github.com/user/repo.git"` |
| `path(n)` | Get URI path segment by index (0-based, negative for reverse) | `path(-1)` → `"repo"`, `path(0)` → `"user"` |

#### Branch Functions (available in templates)

| Function | Description | Example |
|----------|-------------|---------|
| `branch()` | Get current branch name | `branch()` → `"feature/new/ui"` |
| `norm_branch(replacement)` | Branch name with `/` replaced (default: `"-"`) | `norm_branch()` → `"feature-new-ui"`, `norm_branch("_")` → `"feature_new_ui"` |

#### Tag Functions (available in templates, URI predicates, and project predicates)

| Function | Description | Example |
|----------|-------------|---------|
| `tag(name)` | Get tag value by name (returns empty string if not set) | `tag("env")` → `"prod"` |
| `tag_exist(name)` | Check if tag exists (returns boolean) | `tag_exist("env")` → `True` |

#### Project Functions (available only in project predicates)

| Function | Description | Example |
|----------|-------------|---------|
| `source_path()` | Get absolute path to source repository or worktree root | `source_path()` → `"/path/to/repo"` |
| `dest_path()` | Get absolute path to destination (clone target or worktree) | `dest_path()` → `"/path/to/worktree"` |
| `file_exists(path)` | Check if file exists relative to source repository | `file_exists("local.properties")` → `True` |
| `dir_exists(path)` | Check if directory exists relative to source repository | `dir_exists("config")` → `True` |
| `path_exists(path)` | Check if path exists (file or directory) relative to source repository | `path_exists("local.properties")` → `True` |

**Tag Usage Example**:
```yaml
sources:
  production:
    predicate: 'tag_exist("env") and tag("env") == "prod"'
    sources: ~/Developer/sources/prod/path(-2)/path(-1)
    worktrees: ~/Developer/worktrees/prod/path(-2)/path(-1)/norm_branch()
```

```bash
# Clone with tags
gww clone https://github.com/user/repo.git --tag env=prod --tag project=backend

# Add worktree with tags
gww add feature-branch --tag env=dev --tag team=frontend
```

## Commands

| Command | Description |
|---------|-------------|
| `gww clone <uri> [--tag key=value]...` | Clone repository to configured location (tags available in templates/predicates) |
| `gww add <branch> [-c] [--tag key=value]...` | Add worktree for branch (optionally create branch, tags available in templates/predicates) |
| `gww remove <branch\|path> [-f]` | Remove worktree |
| `gww pull` | Update source repository |
| `gww migrate <path> [--dry-run] [--move]` | Migrate repositories to new locations |
| `gww init config` | Create default configuration file |
| `gww init shell <shell>` | Install shell completion (bash/zsh/fish) |

**Common Options**:
- `--tag`, `-t`: Tag in format `key=value` or just `key` (can be specified multiple times)

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
uv run mypy src/gww
```

## License

MIT
