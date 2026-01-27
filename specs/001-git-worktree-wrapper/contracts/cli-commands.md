# CLI Commands Contract

**Date**: 2025-01-27  
**Plan**: `plan.md`

This document defines the command-line interface contracts for all `gww` commands.

## Command Structure

All commands follow the pattern:
```
gww <command> [arguments] [options]
```

## Common Options

- `--help`, `-h`: Show command help
- `--verbose`, `-v`: Increase verbosity (may be repeated)
- `--quiet`, `-q`: Suppress non-error output
- `--tag`, `-t`: Tag in format `key=value` or just `key` (can be specified multiple times). Tags are available in template evaluation and `when` condition evaluation.

## Command Specifications

### 1. `gww clone <uri> [--tag key=value]...`

**Purpose**: Clone a new repository to the appropriate source location based on configuration.

**Arguments**:
- `uri` (str, required): Git repository URI (HTTP, HTTPS, SSH, or file://)

**Options**:
- `--tag`, `-t`: Tag in format `key=value` or just `key` (can be specified multiple times). Tags are available in template evaluation and `when` condition evaluation.

**Behavior**:
1. Parse URI to extract protocol, host, port, and path segments
2. Parse tags from `--tag` options into dictionary (format: `key=value` or `key` for tags without values)
3. Evaluate source rules (`when` conditions) to find matching rule or use default (tags available via `tag()` and `tag_exist()` functions)
4. Resolve `sources` template to get absolute checkout path (tags available via `tag()` function)
5. Create directory structure if needed
6. Execute `git clone <uri> <path>`
7. Detect project type by evaluating project `when` conditions (tags available via `tag()` and `tag_exist()` functions)
8. Execute matching project `after_clone` actions in order
9. Report success with clone path

**Exit Codes**:
- `0`: Success
- `1`: Error (invalid URI, clone failed, action failed)
- `2`: Configuration error (invalid config, template error)

**Output**:
- Success: Print clone path to stdout
- Error: Print error message to stderr

**Examples**:
```bash
gww clone https://github.com/user/repo.git
# Output: ~/Developer/sources/github/user/repo

gww clone git@gitlab.com:group/project.git
# Output: ~/Developer/sources/gitlab/group/project

gww clone https://github.com/user/repo.git --tag env=prod --tag project=backend
# Tags available: tag("env") returns "prod", tag("project") returns "backend"
# Can be used in templates: ~/Developer/sources/tag("env")/path(-1)
# Can be used in 'when' conditions: tag_exist("env") and tag("env") == "prod"
```

---

### 2. `gww add <branch> [worktree_name] [--create-branch|-c] [--tag key=value]...`

**Purpose**: Add a worktree for the specified branch. Can create branch from current commit if it doesn't exist.

**Arguments**:
- `branch` (str, required): Branch name to checkout in worktree
- `worktree_name` (str, optional): Optional name for the worktree (used only in path template, does not detach worktree)

**Options**:
- `--create-branch`, `-c`: Create branch from current commit (source or worktree) if branch doesn't exist
- `--tag`, `-t`: Tag in format `key=value` or just `key` (can be specified multiple times). Tags are available in template evaluation and `when` condition evaluation.

**Behavior**:
1. Detect current repository (source or worktree)
2. If in worktree, resolve to source repository
3. Parse tags from `--tag` options into dictionary (format: `key=value` or `key` for tags without values)
4. Check if branch exists in source repository (local or remote)
5. If branch doesn't exist and `--create-branch` specified:
   - Get current commit from source or worktree (where command was executed)
   - Create branch from that commit: `git branch <branch> <commit>`
6. If branch doesn't exist and `--create-branch` not specified:
   - Print error: "Branch '<branch>' not found. Use --create-branch to create from current commit."
   - Exit with code 1
7. Evaluate worktree template to get absolute worktree path (tags available via `tag()` function)
8. Create directory structure if needed
9. Execute `git worktree add <path> <branch>` (worktree remains attached to repository)
10. Detect project type by evaluating project `when` conditions (tags available via `tag()` and `tag_exist()` functions)
11. Execute matching project `after_add` actions in order
12. Report success with worktree path

**Exit Codes**:
- `0`: Success
- `1`: Error (not in git repo, branch not found without --create-branch, worktree add failed, action failed)
- `2`: Configuration error

**Output**:
- Success: Print worktree path to stdout
- Error: Print error message to stderr

**Examples**:
```bash
cd ~/Developer/sources/github/user/repo
gww add feature-branch
# Output: ~/Developer/worktrees/github/user/repo/feature-branch

gww add new-feature -c
# Creates branch 'new-feature' from current commit, then adds worktree
# Output: ~/Developer/worktrees/github/user/repo/new-feature

cd ~/Developer/worktrees/github/user/repo/other-branch
gww add another-feature -c
# Creates branch 'another-feature' from commit in 'other-branch' worktree
# Output: ~/Developer/worktrees/github/user/repo/another-feature

gww add feature-branch --tag env=dev --tag team=frontend
# Tags available: tag("env") returns "dev", tag("team") returns "frontend"
# Can be used in templates: ~/Developer/worktrees/tag("team")/path(-1)/branch()
```

---

### 3. `gww remove <branch_or_path> [--force]`

**Purpose**: Remove a worktree by branch name or path.

**Arguments**:
- `branch_or_path` (str, required): Branch name or absolute path to worktree

**Options**:
- `--force`, `-f`: Force removal even if worktree is dirty (has uncommitted changes)

**Behavior**:
1. If `branch_or_path` is absolute path:
   - Verify path is a valid worktree
   - Resolve source repository from worktree
2. If `branch_or_path` is branch name:
   - Detect current repository (source or worktree)
   - If in worktree, resolve to source repository
   - Find worktree for branch name
3. Check if worktree is clean (no uncommitted changes)
4. If dirty and `--force` not specified:
   - Print error: "Worktree has uncommitted changes. Use --force to remove anyway."
   - Exit with code 1
5. If dirty and `--force` specified:
   - Proceed with removal
6. Execute `git worktree remove <path>` or `git worktree remove --force <path>`
7. Report success

**Exit Codes**:
- `0`: Success
- `1`: Error (worktree not found, dirty without --force, removal failed)
- `2`: Configuration error

**Output**:
- Success: Print "Removed worktree: <path>" to stdout
- Error: Print error message to stderr

**Examples**:
```bash
cd ~/Developer/sources/github/user/repo
gww remove feature-branch
# Output: Removed worktree: ~/Developer/worktrees/github/user/repo/feature-branch

gww remove ~/Developer/worktrees/github/user/repo/feature-branch --force
# Output: Removed worktree: ~/Developer/worktrees/github/user/repo/feature-branch
```

---

### 4. `gww pull`

**Purpose**: Update the source repository by pulling from remote (if clean and on main/master).

**Arguments**: None

**Options**: None

**Behavior**:
1. Detect current repository (source or worktree)
2. If in worktree, resolve to source repository
3. Verify source repository is on `main` or `master` branch
4. Check if source repository is clean (no uncommitted changes)
5. If not on main/master:
   - Print error: "Source repository must be on 'main' or 'master' branch"
   - Exit with code 1
6. If not clean:
   - Print error: "Source repository has uncommitted changes. Commit or stash changes first."
   - Exit with code 1
7. Execute `git pull` in source repository
8. Report success

**Exit Codes**:
- `0`: Success
- `1`: Error (not in git repo, not on main/master, not clean, pull failed)
- `2`: Configuration error

**Output**:
- Success: Print "Updated source repository: <path>" to stdout
- Error: Print error message to stderr

**Examples**:
```bash
cd ~/Developer/sources/github/user/repo
gww pull
# Output: Updated source repository: ~/Developer/sources/github/user/repo

cd ~/Developer/worktrees/github/user/repo/feature-branch
gww pull
# Output: Updated source repository: ~/Developer/sources/github/user/repo
```

---

### 5. `gww migrate <old_repos> [--dry-run] [--move]`

**Purpose**: Scan old repositories directory and migrate them to new locations based on current configuration.

**Arguments**:
- `old_repos` (str, required): Path to directory containing old repositories

**Options**:
- `--dry-run`, `-n`: Show what would be migrated without making changes
- `--move`: Move repositories instead of copying (default is copy)

**Behavior**:
1. Verify `old_repos` path exists and is a directory
2. Recursively scan directory tree for git repositories (directories containing `.git`). Git submodules are excluded (only top-level repos and worktrees are considered for migration).
3. For each repository found:
   - Extract URI from remote origin (if available)
   - Calculate expected location using current config
   - Compare current location with expected location
   - If same: Output "Already at target: \<path\>" (when not quiet) and include in summary count
   - If different:
     - Output path (e.g. `old_path -> new_path`) immediately when processing that repository, before copy/move
     - If `--dry-run`: Output each path immediately; at the end print "Would migrate N repositories" (and "Would skip N repositories" if any skipped)
     - Else: Copy or move repository to expected location
     - If the repository being migrated is a worktree:
       - After moving/copying, call `git worktree repair` on the source repository to update the worktree path
       - Handle repair errors gracefully (log warning, don't fail migration)
     - If the repository is a source repository: No repair action needed
4. Report summary: repositories migrated, repaired, skipped, already at target

**Exit Codes**:
- `0`: Success
- `1`: Error (invalid path, migration failed)
- `2`: Configuration error

**Output**:
- Success: Print summary to stdout
- Error: Print error message to stderr

**Examples**:
```bash
gww migrate ~/old-repos --dry-run
# Output (each path first, then summary at end):
#   ~/old-repos/repo1 -> ~/Developer/sources/github/user/repo1
#   ...
# Would migrate 5 repositories

gww migrate ~/old-repos --move
# Output (each path as processed, then summary):
#   ~/old-repos/repo1 -> ~/Developer/sources/github/user/repo1
#   ...
# Moved 5 repositories
# Repaired 2 worktrees
```

---

### 6. `gww init config`

**Purpose**: Create a default configuration file with examples and documentation.

**Arguments**: None

**Options**: None

**Behavior**:
1. Determine config file path: `$XDG_CONFIG_HOME/gww/config.yml` (or platform equivalent, following XDG and OS defaults)
2. Check if config file already exists
3. If exists:
   - Print warning: "Config file already exists at <path>. Not overwriting."
   - Exit with code 1
4. Create config directory if needed
5. Write default config file with:
   - `default_sources` and `default_worktrees` templates
   - Large comment block with examples:
     - Source rule examples (github, gitlab, custom)
     - Project rule examples
     - Template function documentation
     - All available functions with signatures
6. Report success with config file path

**Exit Codes**:
- `0`: Success
- `1`: Error (config exists, write failed)
- `2`: Configuration error (cannot determine config directory)

**Output**:
- Success: Print "Created config file: <path>" to stdout
- Error: Print error message to stderr

**Examples**:
```bash
gww init config
# Output: Created config file: ~/.config/gww/config.yml
```

---

### 7. `gww init shell <shell>`

**Purpose**: Generate and install shell autocompletion script.

**Arguments**:
- `shell` (str, required): Shell name - one of: `bash`, `zsh`, `fish`

**Options**: None

**Behavior**:
1. Validate shell name (must be bash, zsh, or fish)
2. Generate completion script using argparse's built-in methods:
   - `bash`: `parser.get_bash_complete()`
   - `zsh`: `parser.get_zsh_complete()`
   - `fish`: `parser.get_fish_complete()`
3. Determine installation location:
   - `bash`: `~/.bash_completion.d/gww` or system directory
   - `zsh`: `~/.zsh/completions/_gww` or `$fpath/_gww`
   - `fish`: `~/.config/fish/completions/gww.fish`
4. Write completion script to installation location
5. Print installation instructions if manual sourcing needed
6. Report success

**Exit Codes**:
- `0`: Success
- `1`: Error (invalid shell, write failed)
- `2`: Configuration error

**Output**:
- Success: Print "Installed <shell> completion script: <path>" and instructions
- Error: Print error message to stderr

**Examples**:
```bash
gww init shell bash
# Output:
# Installed bash completion script: ~/.bash_completion.d/gww
# To activate, run: source ~/.bash_completion.d/gww
# Or add to ~/.bashrc: source ~/.bash_completion.d/gww

gww init shell fish
# Output:
# Installed fish completion script: ~/.config/fish/completions/gww.fish
# Restart fish shell or run: source ~/.config/fish/completions/gww.fish
```

---

## Error Handling

All commands follow consistent error handling:

1. **Validation Errors**: Invalid arguments, missing required fields
   - Exit code: 1
   - Message: Clear description of validation failure

2. **Configuration Errors**: Invalid config file, template errors
   - Exit code: 2
   - Message: Configuration error with file location and details

3. **Git Errors**: Git command failures, repository issues
   - Exit code: 1
   - Message: Git error message (from git command output)

4. **File System Errors**: Permission denied, path not found
   - Exit code: 1
   - Message: File system error with path

5. **Action Errors**: Project action execution failures
   - Exit code: 1
   - Message: Action error with action type and details

## Output Format

- **Success**: Print result to stdout (paths, summaries)
- **Errors**: Print to stderr
- **Warnings**: Print to stderr with "Warning:" prefix
- **Verbose**: Additional details when `--verbose` specified

## Completion Support

All commands support shell completion for:
- Subcommands
- Branch names (local and remote)
- Worktree paths
- Options (`--force`, `--dry-run`, etc.)
- File paths (where applicable)

Completion is generated via `gww init shell <shell>` and uses argparse's built-in completion generation.
