# CLI Commands Contract

**Date**: 2025-01-27  
**Plan**: `plan.md`

This document defines the command-line interface contracts for all `sgw` commands.

## Command Structure

All commands follow the pattern:
```
sgw <command> [arguments] [options]
```

## Common Options

- `--help`, `-h`: Show command help
- `--verbose`, `-v`: Increase verbosity (may be repeated)
- `--quiet`, `-q`: Suppress non-error output

## Command Specifications

### 1. `sgw clone <uri>`

**Purpose**: Clone a new repository to the appropriate source location based on configuration.

**Arguments**:
- `uri` (str, required): Git repository URI (HTTP, HTTPS, SSH, or file://)

**Options**: None

**Behavior**:
1. Parse URI to extract protocol, host, port, and path segments
2. Evaluate source rules (predicates) to find matching rule or use default
3. Resolve `sources` template to get absolute checkout path
4. Create directory structure if needed
5. Execute `git clone <uri> <path>`
6. Detect project type by evaluating project predicates
7. Execute matching project `source_actions` in order
8. Report success with clone path

**Exit Codes**:
- `0`: Success
- `1`: Error (invalid URI, clone failed, action failed)
- `2`: Configuration error (invalid config, template error)

**Output**:
- Success: Print clone path to stdout
- Error: Print error message to stderr

**Examples**:
```bash
sgw clone https://github.com/user/repo.git
# Output: ~/Developer/sources/github/user/repo

sgw clone git@gitlab.com:group/project.git
# Output: ~/Developer/sources/gitlab/group/project
```

---

### 2. `sgw add <branch> [worktree_name] [--create-branch|-c]`

**Purpose**: Add a worktree for the specified branch, optionally with a name. Can create branch from current commit if it doesn't exist.

**Arguments**:
- `branch` (str, required): Branch name to checkout in worktree
- `worktree_name` (str, optional): Optional name for the worktree (used only in path template, does not detach worktree)

**Options**:
- `--create-branch`, `-c`: Create branch from current commit (source or worktree) if branch doesn't exist

**Behavior**:
1. Detect current repository (source or worktree)
2. If in worktree, resolve to source repository
3. Check if branch exists in source repository (local or remote)
4. If branch doesn't exist and `--create-branch` specified:
   - Get current commit from source or worktree (where command was executed)
   - Create branch from that commit: `git branch <branch> <commit>`
5. If branch doesn't exist and `--create-branch` not specified:
   - Print error: "Branch '<branch>' not found. Use --create-branch to create from current commit."
   - Exit with code 1
6. Evaluate worktree template to get absolute worktree path (worktree_name used in template if provided)
7. Create directory structure if needed
8. Execute `git worktree add <path> <branch>` (worktree remains attached to repository)
9. Detect project type by evaluating project predicates
10. Execute matching project `worktree_actions` in order
11. Report success with worktree path

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
sgw add feature-branch
# Output: ~/Developer/worktrees/github/user/repo/feature-branch

sgw add feature-branch my-feature
# Output: ~/Developer/worktrees/github/user/repo/my-feature-feature-branch

sgw add new-feature -c
# Creates branch 'new-feature' from current commit, then adds worktree
# Output: ~/Developer/worktrees/github/user/repo/new-feature

cd ~/Developer/worktrees/github/user/repo/other-branch
sgw add another-feature -c
# Creates branch 'another-feature' from commit in 'other-branch' worktree
# Output: ~/Developer/worktrees/github/user/repo/another-feature
```

---

### 3. `sgw remove <branch_or_path> [--force]`

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
sgw remove feature-branch
# Output: Removed worktree: ~/Developer/worktrees/github/user/repo/feature-branch

sgw remove ~/Developer/worktrees/github/user/repo/feature-branch --force
# Output: Removed worktree: ~/Developer/worktrees/github/user/repo/feature-branch
```

---

### 4. `sgw pull`

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
sgw pull
# Output: Updated source repository: ~/Developer/sources/github/user/repo

cd ~/Developer/worktrees/github/user/repo/feature-branch
sgw pull
# Output: Updated source repository: ~/Developer/sources/github/user/repo
```

---

### 5. `sgw migrate <old_repos> [--dry-run] [--move]`

**Purpose**: Scan old repositories directory and migrate them to new locations based on current configuration.

**Arguments**:
- `old_repos` (str, required): Path to directory containing old repositories

**Options**:
- `--dry-run`, `-n`: Show what would be migrated without making changes
- `--move`: Move repositories instead of copying (default is copy)

**Behavior**:
1. Verify `old_repos` path exists and is a directory
2. Recursively scan directory tree for git repositories (directories containing `.git`)
3. For each repository found:
   - Extract URI from remote origin (if available)
   - Calculate expected location using current config
   - Compare current location with expected location
   - If different:
     - If `--dry-run`: Print migration plan
     - Else: Copy or move repository to expected location
     - Update worktrees if any exist
4. Report summary: repositories scanned, migrated, skipped

**Exit Codes**:
- `0`: Success
- `1`: Error (invalid path, migration failed)
- `2`: Configuration error

**Output**:
- Success: Print summary to stdout
- Error: Print error message to stderr

**Examples**:
```bash
sgw migrate ~/old-repos --dry-run
# Output:
# Would migrate 5 repositories:
#   ~/old-repos/repo1 -> ~/Developer/sources/github/user/repo1
#   ...

sgw migrate ~/old-repos --move
# Output:
# Migrated 5 repositories
# Moved 3 worktrees
```

---

### 6. `sgw init config`

**Purpose**: Create a default configuration file with examples and documentation.

**Arguments**: None

**Options**: None

**Behavior**:
1. Determine config file path: `$XDG_CONFIG_HOME/sgw/config.yml` (or platform equivalent, following XDG and OS defaults)
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
sgw init config
# Output: Created config file: ~/.config/sgw/config.yml
```

---

### 7. `sgw init shell <shell>`

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
   - `bash`: `~/.bash_completion.d/sgw` or system directory
   - `zsh`: `~/.zsh/completions/_sgw` or `$fpath/_sgw`
   - `fish`: `~/.config/fish/completions/sgw.fish`
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
sgw init shell bash
# Output:
# Installed bash completion script: ~/.bash_completion.d/sgw
# To activate, run: source ~/.bash_completion.d/sgw
# Or add to ~/.bashrc: source ~/.bash_completion.d/sgw

sgw init shell fish
# Output:
# Installed fish completion script: ~/.config/fish/completions/sgw.fish
# Restart fish shell or run: source ~/.config/fish/completions/sgw.fish
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

Completion is generated via `sgw init shell <shell>` and uses argparse's built-in completion generation.
