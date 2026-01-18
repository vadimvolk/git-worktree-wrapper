<!-- Language switcher -->
**English** | [Русский](README.ru.md)

> ⚠️ **Warning**: GWW is not heavily tested, use at your own risk!

# 🚀 GWW - Git Worktree Wrapper

A CLI tool that wraps git worktree functionality with configurable path templates, condition-based routing, and project-specific actions.

## ✨ Features

- **📝 Configurable path templates**: Dynamic path generation using templates with functions like `path(n)`, `branch()`, `norm_branch()`, `tag()`
- **🔄 Condition-based routing**: Route repositories to different locations based on URI conditions (host, path, protocol, tags)
- **🏷️ Tag support**: Pass custom tags via `--tag` option for conditional routing and path organization
- **⚙️ Project actions**: Execute custom actions (file copies, commands) after clone or worktree creation
- **🐚 Shell completion**: Bash, Zsh, and Fish completion support

## 📋 Requirements

- 🐍 Python 3.11+
- 🔧 Git
- 🖥️ Unix-like system (Linux, macOS)

## 📦 Installation

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

## 🚀 Quick Start

### 1. ⚙️ Initialize Configuration

```bash
gww init config
```

This creates a default configuration file at `~/.config/gww/config.yml` (Linux) or `~/Library/Application Support/gww/config.yml` (macOS).

### 2. 📥 Clone a Repository

```bash
gww clone https://github.com/user/repo.git
# Output: ~/Developer/sources/github/user/repo
```

### 3. ➕ Add a Worktree

```bash
cd ~/Developer/sources/github/user/repo
gww add feature-branch
# Output: ~/Developer/worktrees/github/user/repo/feature-branch
```

### 4. ➖ Remove a Worktree

```bash
gww remove feature-branch
# Output: Removed worktree: ~/Developer/worktrees/github/user/repo/feature-branch
```

### 5. 🔄 Update Source Repository

```bash
gww pull
# Output: Updated source repository: ~/Developer/sources/github/user/repo
```

**Note**: `gww pull` will pull the source repository even if it's called from a worktree, as long as the source repository is clean and has `main` or `master` branch checked out. This is useful for merge/rebase scenarios where you want to update the source repository while working in a worktree.

## ⚙️ Configuration

Example `config.yml`:

```yaml
default_sources: ~/Developer/sources/default/path(-2)/path(-1)
default_worktrees: ~/Developer/worktrees/default/path(-2)/path(-1)/norm_branch()

sources:
  github:
    when: '"github" in host()'
    sources: ~/Developer/sources/github/path(-2)/path(-1)
    worktrees: ~/Developer/worktrees/github/path(-2)/path(-1)/norm_branch()

  gitlab:
    when: '"gitlab" in host()'
    sources: ~/Developer/sources/gitlab/path(-3)/path(-2)/path(-1)
    worktrees: ~/Developer/worktrees/gitlab/path(-3)/path(-2)/path(-1)/norm_branch()

actions:
  - when: file_exists("local.properties")
    after_clone:
      - abs_copy: ["~/sources/default-local.properties", "local.properties"]
    after_add:
      - rel_copy: ["local.properties"]
```

### 📝 Template Functions

#### 🌐 URI Functions (available in templates and `when` conditions)

| Function | Description | Example |
|----------|-------------|---------|
| `host()` | Get URI hostname | `host()` → `"github.com"` |
| `port()` | Get URI port (empty string if not specified) | `port()` → `""` or `"22"` |
| `protocol()` | Get URI protocol/scheme | `protocol()` → `"https"` or `"ssh"` |
| `uri()` | Get full URI string | `uri()` → `"https://github.com/user/repo.git"` |
| `path(n)` | Get URI path segment by index (0-based, negative for reverse) | `path(-1)` → `"repo"`, `path(0)` → `"user"` |

#### 🌿 Branch Functions (available in templates)

| Function | Description | Example |
|----------|-------------|---------|
| `branch()` | Get current branch name | `branch()` → `"feature/new/ui"` |
| `norm_branch(replacement)` | Branch name with `/` replaced (default: `"-"`) | `norm_branch()` → `"feature-new-ui"`, `norm_branch("_")` → `"feature_new_ui"` |

#### ⚙️ Actions (available in `actions` section)

| Action | Description | Example |
|--------|-------------|---------|
| `abs_copy` | Copy file from absolute path to relative destination in target directory | `abs_copy: ["~/sources/default-local.properties", "local.properties"]` |
| `rel_copy` | Copy file from source repository to worktree (relative paths) | `rel_copy: ["local.properties"]` or `rel_copy: ["config.template", "config"]` |
| `command` | Execute external command (runs in destination directory, template functions available) | `command: "npm install"` or `command: "claude init"` |

#### 📁 Actions Functions (available in `command` actions and `when` conditions)

| Function | Description | Example |
|----------|-------------|---------|
| `source_path()` | Get absolute path to source repository or worktree root | `source_path()` → `"/path/to/repo"` |
| `dest_path()` | Get absolute path to destination (clone target or worktree) | `dest_path()` → `"/path/to/worktree"` |
| `file_exists(path)` | Check if file exists relative to source repository | `file_exists("local.properties")` → `True` |
| `dir_exists(path)` | Check if directory exists relative to source repository | `dir_exists("config")` → `True` |
| `path_exists(path)` | Check if path exists (file or directory) relative to source repository | `path_exists("local.properties")` → `True` |

#### 🏷️ Tag Functions (available in templates and `when` conditions)

| Function | Description | Example |
|----------|-------------|---------|
| `tag(name)` | Get tag value by name (returns empty string if not set) | `tag("env")` → `"prod"` |
| `tag_exist(name)` | Check if tag exists (returns boolean) | `tag_exist("env")` → `True` |

**🏷️ Tag Usage Example**:
```yaml
sources:
  # Temporary checkout: Clone repositories to ~/Downloads/temp for quick access
  # Usage: gww clone <uri> --tag temp
  temp:
    when: 'tag_exist("temp")'
    sources: ~/Downloads/temp/path(-1)
    worktrees: ~/Downloads/temp/path(-1)/norm_branch()

  # Code review worktrees: Add worktrees to ~/Developer/worktree/code-review for review tasks
  # Usage: gww add <branch> --tag review
  review:
    when: 'tag_exist("review")'
    sources: ~/Developer/sources/path(-2)/path(-1)
    worktrees: ~/Developer/worktree/code-review/path(-1)/norm_branch()
```

```bash
# Clone to temporary location
gww clone https://github.com/user/repo.git --tag temp
# Output: ~/Downloads/temp/repo

# Add worktree for code review
cd ~/Developer/sources/github/user/repo
gww add feature-branch --tag review
# Output: ~/Developer/worktree/code-review/repo/feature-branch
```

## 📖 Commands

| Command | Description |
|---------|-------------|
| `gww clone <uri> [--tag key=value]...` | 📥 Clone repository to configured location (tags available in templates/conditions) |
| `gww add <branch> [-c] [--tag key=value]...` | ➕ Add worktree for branch (optionally create branch, tags available in templates/conditions) |
| `gww remove <branch\|path> [-f]` | ➖ Remove worktree |
| `gww pull` | 🔄 Update source repository (works from worktrees if source is clean and on main/master) |
| `gww migrate <path> [--dry-run] [--move]` | 🚚 Migrate repositories to new locations |
| `gww init config` | ⚙️ Create default configuration file |
| `gww init shell <shell>` | 🐚 Install shell completion (bash/zsh/fish) |

**Common Options**:
- `--tag`, `-t`: Tag in format `key=value` or just `key` (can be specified multiple times).

## 🔄 Update

### Using uv

```bash
# Re-run the install command to update to the latest version
uv tool install "git+https://github.com/vadimvolk/git-worktree-wrapper.git"

# Or use the update command (if available)
uv tool update gww
```

### Using pipx

```bash
pipx upgrade gww
```

### Using pip

```bash
python -m pip install --upgrade gww
```

## 🗑️ Uninstall

### Using uv

```bash
uv tool uninstall gww
```

### Using pipx

```bash
pipx uninstall gww
```

### Using pip

```bash
python -m pip uninstall gww
```

## 🛠️ Development

### 🧪 Running Tests

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

### 🔍 Type Checking

```bash
uv run mypy src/gww
```

## 📄 License

MIT
