<!-- Language switcher -->
**English** | [Русский](README.ru.md)

> ⚠️ **Warning**: GWW is not heavily tested, use at your own risk!

# 🚀 GWW - Git Worktree Wrapper

[![CI](https://github.com/vadimvolk/git-worktree-wrapper/actions/workflows/ci.yml/badge.svg)](https://github.com/vadimvolk/git-worktree-wrapper/actions/workflows/ci.yml)

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

This creates a default configuration file at `~/.config/gww/config.yml` (Linux), `~/Library/Application Support/gww/config.yml` (macOS), or `%APPDATA%\gww\config.yml` (Windows). On any platform, exporting `XDG_CONFIG_HOME` to an absolute path overrides the default and stores the config there instead. Edit these 2 values: `default_sources` and `default_worktrees`. Check the [tutorial section](#tutorial) for routing details.

### 2. 🐚 Initialize Shell Integration

```bash
gww init shell zsh  # or bash, or fish
```

This installs shell completion and aliases (`gwc`, `gwa`, `gwr`) for easier workflow. Follow the instructions printed by the command to enable them in your shell.

### 3. 📥 Clone a Repository

```bash
gwc https://github.com/user/repo.git
# Prompts: "Navigate to ~/Developer/sources/github/user/repo? [Y/n]"
# Navigates if you confirm (default: yes)
```

### 4. ➕ Add a Worktree

```bash
cd ~/Developer/sources/github/user/repo
gwa feature-branch
# Prompts: "Navigate to ~/Developer/worktrees/github/user/repo/feature-branch? [Y/n]"
# Navigates if you confirm (default: yes)
```

### 5. ➖ Remove a Worktree

```bash
gwr feature-branch
# If worktree has uncommitted changes or untracked files:
#   Prompts: "Force removal? [y/N]"
#   Removes with --force if you confirm
# Otherwise: Removes worktree immediately
# Output: Removed worktree: ~/Developer/worktrees/github/user/repo/feature-branch
```

### 6. 🔄 Update Source Repository

```bash
gww pull
# Output: Updated source repository: ~/Developer/sources/github/user/repo
```

**Note**: `gww pull` updates the source repository even from a worktree, as long as the source is clean and has `main` or `master` checked out. Useful for merge/rebase workflows.
```bash
gww pull # from any repository worktree
git rebase main # rebase your current changes to updated main branch
```

### 7. 🚚 Migrate Repositories
Create a backup first!

```bash
gww migrate ~/old-repos --dry-run
# Output:
# Would migrate 5 repositories:
#   ~/old-repos/repo1 -> ~/Developer/sources/github/user/repo1
#   ...

gww migrate ~/old-repos
# Copy (default): list, copy sources then worktrees, repair, summary

gww migrate ~/old-repos --inplace
# Move worktrees then sources, repair, clean empty folders
```

The `migrate` command scans one or more directories for git repositories and migrates them to locations based on your current configuration. It's useful when:
- You've updated your configuration and want to reorganize existing repositories
- You're moving from manual repository management to GWW
- You need to consolidate repositories from different locations

**Options**:
- `--dry-run`, `-n`: Show what would be migrated without making changes
- `--copy` (default): Copy repositories to new locations; list, validate, copy sources then worktrees, run `git worktree repair`, then report summary. No folder cleanup.
- `--inplace`: Move repositories in place (worktrees first, then sources), run `git worktree repair`, then recursively clean empty source folders.

**Behavior**:
- Accepts one or more paths; scans each and merges repo lists (deduplicated)
- Classifies each repo as source or worktree; uses source path template for sources and worktree path template for worktrees
- **--inplace**: Two passes (worktrees then sources), move and repair, then remove vacated dirs and empty parents up to input roots
- **--copy**: List sources and worktrees, validate destinations, copy sources then worktrees, repair relations, report summary
- Skips repositories without remotes, detached HEAD worktrees, or already at target

## Tutorial

A minimal config file looks like:
```yaml
# Folder where all sources are checked out with gwc. path(-2)/path(-1) generates 2-level subfolders based on repository URI. Like https://github.com/user/repo.git -> ~/Developer/sources/user/repo
default_sources: ~/Developer/other/sources/path(-2)/path(-1)
# Folder where all worktrees are checked out with gwa. norm_branch() works better with remote branches, e.g. origin/remote-branch -> origin-remote-branch
default_worktrees: ~/Developer/other/worktrees/path(-2)/path(-1)/norm_branch()
```
The generated file will have more options commented out, including the functions reference. 

### Checkout based on where repository is hosted
Useful to separate e.g. open source projects (where you learn or get inspired) from your work projects.
```yaml
# Still needed in case the config fails to find a section. You may prefer a non-nested sources structure, but make sure the result folder is unique
default_sources: ~/Developer/sources/host()-path(-2)-path(-1)
default_worktrees: ~/Developer/worktrees/host()-path(-2)-path(-1)-norm_branch()
sources:
  # ... other rules
  work:
    when: "your.org.host" in host()
    sources: ~/Developer/work/sources/path(-2)-path(-1)
    worktrees: ~/Developer/work/sources/path(-2)-path(-1)-norm_branch()
  
```
That's enough to separate work sources from all others, but you can create more sections with various rules. The library uses [simpleeval](https://github.com/danthedeckie/simpleeval) to evaluate templates, so you can use its [operators](https://github.com/danthedeckie/simpleeval?tab=readme-ov-file#operators) and functions below to get necessary routing. 

#### 🌐 URI Functions (available in templates and `when` conditions)

| Function | Description | Example |
|----------|-------------|---------|
| `uri()` | Get full URI string | `uri()` → `"https://loca-repo-manager.com:8081/user/repo.git"` |
| `host()` | Get URI hostname | `host()` → `"loca-repo-manager.com"` |
| `port()` | Get URI port (empty string if not specified) | `port()` → `"8081"` or `""` usually |
| `protocol()` | Get URI protocol/scheme | `protocol()` → `"https"` / `"ssh"` / `git` |
| `path(n)` | Get URI path segment by index (0-based, negative for reverse) | `path(-1)` → `"repo"`, `path(0)` → `"user"` |

#### 🌿 Branch Functions (available in templates)

| Function | Description | Example |
|----------|-------------|---------|
| `branch()` | Get current branch name | `branch()` → `"feature/new/ui"` |
| `norm_branch(replacement)` | Branch name with `/` replaced (default: `"-"`) | `norm_branch()` → `"feature-new-ui"`, `norm_branch("_")` → `"feature_new_ui"` |

Need to checkout temporary projects separately? Add this to your config:
```yml
sources:
  # ... other rules
  temp:
    when: tag_exist("temp")  # See [tags section](#-tags) for details about tags
    sources: ~/Downloads/temp/sources/time_id()-host()-path(-2)-path(-1) 
    worktrees: ~/Downloads/temp/worktrees/time_id()-host()-path(-2)-path(-1)-norm-branch()
```
`time_id(fmt)` generates a datetime-based identifier (cached per template evaluation). Default format is `"20260120-2134.03"` (short, seconds accuracy unique). Use [format codes](https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes) for more detailed/nested results. Works properly if used multiple times.
```yml
worktrees: ~/Downloads/temp/worktrees/time_id("%Y")/time_id("%m")/time_id("%H-%M$.%S")/host()-path(-2)-path(-1)-norm-branch()
```
Generates nested structure: `YYYY/HH-MM.ss/host()-path(-2)-path(-1)-norm-branch()`


#### ⚙️ Actions (available in `actions` section)
Run actions after checking out a repository, after adding a worktree, or **before removing a worktree**. Common example: copying `local.properties` for Gradle projects.
```yml
actions:
  - when: file_exists("settings.gradle") # Check if it's actually a Gradle project
    after_clone:
      - abs_copy: ["~/sources/default-local.properties", "local.properties"] # Copies your default file right after cloning the repo
    after_add: 
      - rel_copy: ["local.properties"] # Inherit existing repository file to worktree
```
You can have multiple `when` subsections in actions. After clone/add, the library goes top-to-bottom and executes all actions with matching `when` conditions.
Other functions available in the actions section: 
| Action | Description | Example |
|--------|-------------|---------|
| `abs_copy` | Copy file from absolute path to relative destination in target directory | `abs_copy: ["~/sources/default-local.properties", "local.properties"]` |
| `rel_copy` | Copy file from source repository to worktree (relative paths) | `rel_copy: ["local.properties"]` or `rel_copy: ["config.template", "config"]` |
| `command` | Execute external command (runs in destination directory, template functions available) | `command: "npm install"` or `command: "claude init"` |

Each action rule also accepts an optional `critical:` flag (default `true`). When `true`, a failing action in that rule aborts the remaining actions in the rule and makes the command exit `1`. Set `critical: false` for non-critical rules — failures are reported in the action execution summary but the command still exits `0`. See [Failure handling](#-failure-handling) below for the full exit-code table.
```yml
actions:
  - when: file_exists("package.json")
    critical: false  # non-critical: a missing node_modules is annoying, not fatal
    after_clone:
      - command: "npm install"
```

##### 🪓 `before_remove` — cleanup actions before `gww remove`
A third action kind, `before_remove`, runs user-defined cleanup steps **before** `git worktree remove` deletes the worktree. Use it to archive the worktree, post a notification, run a hook, etc. The same `critical:` / `command:` / `rel_copy:` / `abs_copy:` machinery applies; a critical `before_remove` failure aborts the remove and exits `1`, a non-critical failure is reported but the remove still proceeds. `--force` is git-only and does *not* bypass `before_remove`.

In `before_remove` rules, `dest_path()` is the worktree being removed, `source_path()` is its parent source repo, and `branch()` resolves to the worktree's currently checked-out branch (or `""` on detached HEAD). The `gww remove` command also accepts `--tag key=value`, which flows into `tag()` / `tag_exist()` predicates so per-call cleanup can be tag-driven.

```yml
actions:
  # Critical: archive the worktree before letting `gww remove` delete it.
  - when: 'tag_exist("archive")'
    before_remove:
      - command: "tar -czf ~/archives/norm_branch()-time_id('%Y%m%d').tar.gz dest_path()"

  # Non-critical: notify a Slack channel. A failed notification should not block the remove.
  - when: tag("notify") == "slack"
    critical: false
    before_remove:
      - command: "curl -sf -X POST https://hooks.slack.com/... -d branch=branch()"

  # Path-based remove: when removing by absolute path, `branch()` still resolves.
  - when: branch() == "main"
    before_remove:
      - command: "echo refusing to remove main branch"
```
> Note: `gww remove` accepts an absolute worktree path as well as a branch name. When invoked with a path, `branch()` reads the worktree's current branch via `git rev-parse --abbrev-ref HEAD` and falls back to `""` for detached HEAD, so predicates referencing `branch()` never raise.

#### ❗ Failure handling
Action failures are reported per-rule, grouped at the end of the action loop on stderr as the **action execution summary**. The summary lists every failing rule by its index in `actions:`, its criticality flag, and the failing action's error. Its non-emptiness also gates the success line: `say()` (the line scripts `cd $(gwc …)`) is suppressed whenever the summary has any entry, so `cd` only ever lands on a fully-configured worktree.

| Outcome | Exit code |
|---|---|
| Clean run (no failures) | `0` |
| Non-critical rule failure only | `0` |
| Critical rule failure | `1` |
| `when:` predicate or `command:` template failed to evaluate | `2` |

#### 📁 Actions Functions (available in `command` actions and `when` conditions)

| Function | Description | Example |
|----------|-------------|---------|
| `source_path()` | Get absolute path to source repository or worktree root | `source_path()` → `"/path/to/repo"` |
| `dest_path()` | Get absolute path to destination (clone target or worktree) | `dest_path()` → `"/path/to/worktree"` |
| `file_exists(path)` | Check if file exists relative to source repository | `file_exists("local.properties")` → `True` |
| `dir_exists(path)` | Check if directory exists relative to source repository | `dir_exists("config")` → `True` |
| `path_exists(path)` | Check if path exists (file or directory) relative to source repository | `path_exists("local.properties")` → `True` |

#### 🏷️ Tags

Still not flexible enough? Here comes tags. Tags specified using command line param `-t <tag-name>[=optional value]` (or `--tag`) for clone / add commands. Tags available in configuration with:

| Function | Description | Example |
|----------|-------------|---------|
| `tag(name)` | Get tag value by name (returns empty string if not set) | `tag("env")` → `"prod"` |
| `tag_exist(name)` | Check if tag exists (returns boolean) | `tag_exist("env")` → `True` |

**🏷️ Tag Usage Example**:
```yaml
sources:
  # Temporary checkout: Clone repositories to ~/Downloads/temp for quick access
  # Usage: gwc <uri> -t temp
  temp:
    when: 'tag_exist("temp")'
    sources: ~/Downloads/temp/time_id()-host()-path(-1)
    worktrees: ~/Downloads/temp/time_id()-host()-path(-1)/norm_branch()

  # Code review worktrees: Add worktrees to ~/Developer/worktree/code-review for review tasks
  # Usage: gwa <branch> --tag review
  review:
    when: 'tag_exist("review")'
    worktrees: ~/Developer/review/worktree/path(-1)/norm_branch()
    # If used during clone, default source path is used
```
```

```bash
# Clone to temporary location
gwc https://github.com/user/repo.git -t temp
# Output: ~/Downloads/temp/repo

# Add worktree for code review
cd ~/Developer/sources/github/user/repo
gwa feature-branch --tag review
# Output: ~/Developer/worktree/code-review/repo/feature-branch
```

## 📖 Commands

| Command | Description |
|---------|-------------|
| `gwc <uri> [--tag key=value]...` | 📥 Clone repository to configured location (tags available in templates/conditions) |
| `gwa <branch> [-c] [--tag key=value]...` | ➕ Add worktree for branch (optionally create branch, tags available in templates/conditions) |
| `gwr <branch\|path> [-f] [--tag key=value]...` | ➖ Remove worktree (tags available in `before_remove` predicates) |
| `gww pull` | 🔄 Update source repository (works from worktrees if source is clean and on main/master) |
| `gww migrate <path>... [--dry-run] [--copy \| --inplace]` | 🚚 Migrate repositories to new locations |
| `gww init config` | ⚙️ Create default configuration file |
| `gww init shell <shell>` | 🐚 Install shell completion (bash/zsh/fish) |

**Note**: `gwc`, `gwa`, and `gwr` are convenient shell aliases for `gww clone`, `gww add`, and `gww remove` respectively. They provide the same functionality with automatic navigation prompts. Install them with `gww init shell <shell>`.

**Common Options**:
- `--tag`, `-t`: Tag in the format `key=value` or just `key` (can be specified multiple times).

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
