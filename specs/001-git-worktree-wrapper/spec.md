# Specification: Git Worktree Wrapper (gww)

**Date**: 2025-01-27  
**Input**: Architecture specification from `/architecture.md` and CLI contracts from `/contracts/cli-commands.md`

## Overview

Build a CLI tool `gww` that wraps git worktree functionality with configurable path templates, condition-based routing, and project-specific actions. The tool uses YAML configuration with template evaluation for dynamic path generation, supports multiple git hosting providers, and provides commands for cloning, worktree management, migration, and shell autocompletion.

## Functional Requirements

### FR1: Repository Cloning
**Priority**: P1 (MVP)

Users can clone repositories to configurable source locations based on URI conditions, with project-specific actions executed after clone.

**Acceptance Criteria**:
- Command: `gww clone <uri> [--tag key=value]...`
- Parse URI to extract protocol, host, port, and path segments
- Parse optional tags from `--tag` options (format: `key=value` or `key`)
- Evaluate source rules (`when` conditions) to find matching rule or use default (tags available in condition context)
- Resolve `sources` template to get absolute checkout path (tags available in template context)
- Execute `git clone <uri> <path>`
- Detect project type by evaluating project `when` conditions (tags available in condition context)
- Execute matching project `after_clone` actions in order
- Report success with clone path to stdout
- Handle errors: invalid URI, clone failures, action failures (exit code 1)
- Handle configuration errors (exit code 2)

**Examples**:
```bash
gww clone https://github.com/user/repo.git
# Output: ~/Developer/sources/github/user/repo

gww clone git@gitlab.com:group/project.git
# Output: ~/Developer/sources/gitlab/group/project

gww clone https://github.com/user/repo.git --tag env=prod --tag project=backend
# Tags available in templates and 'when' conditions: tag("env") returns "prod", tag("project") returns "backend"
```

---

### FR2: Worktree Addition
**Priority**: P1 (MVP)

Users can add worktrees for branches with configurable paths and project-specific actions executed after worktree creation.

**Acceptance Criteria**:
- Command: `gww add <branch> [worktree_name] [--create-branch|-c] [--tag key=value]...`
- Detect current repository (source or worktree)
- If in worktree, resolve to source repository
- Parse optional tags from `--tag` options (format: `key=value` or `key`)
- Check if branch exists in source repository (local or remote)
- If branch doesn't exist and `--create-branch` specified: create branch from current commit
- Evaluate worktree template to get absolute worktree path (tags available in template context)
- Execute `git worktree add <path> <branch>`
- Detect project type and execute matching project `after_add` actions in order (tags available in condition context)
- Report success with worktree path to stdout
- Handle errors: not in git repo, branch not found without --create-branch, worktree add failed, action failed (exit code 1)
- Handle configuration errors (exit code 2)

**Examples**:
```bash
cd ~/Developer/sources/github/user/repo
gww add feature-branch
# Output: ~/Developer/worktrees/github/user/repo/feature-branch

gww add feature-branch my-feature
# Output: ~/Developer/worktrees/github/user/repo/my-feature-feature-branch

gww add new-feature -c
# Creates branch 'new-feature' from current commit, then adds worktree

gww add feature-branch --tag env=dev --tag team=frontend
# Tags available in templates: tag("env") returns "dev", tag("team") returns "frontend"
```

---

### FR3: Worktree Removal
**Priority**: P2

Users can remove worktrees by branch name or path, with safety checks for dirty worktrees and force option.

**Acceptance Criteria**:
- Command: `gww remove <branch_or_path> [--force]`
- Accept branch name or absolute path to worktree
- If branch name: detect current repository and find worktree for branch
- If absolute path: verify path is a valid worktree
- Check if worktree is clean (no uncommitted changes)
- If dirty and `--force` not specified: error with exit code 1
- If dirty and `--force` specified: proceed with removal
- Execute `git worktree remove <path>` or `git worktree remove --force <path>`
- Report success: "Removed worktree: <path>" to stdout
- Handle errors: worktree not found, dirty without --force, removal failed (exit code 1)
- Handle configuration errors (exit code 2)

**Examples**:
```bash
cd ~/Developer/sources/github/user/repo
gww remove feature-branch
# Output: Removed worktree: ~/Developer/worktrees/github/user/repo/feature-branch

gww remove ~/Developer/worktrees/github/user/repo/feature-branch --force
```

---

### FR4: Source Repository Updates
**Priority**: P2

Users can update source repositories by pulling from remote, with safety checks for branch (main/master) and clean state.

**Acceptance Criteria**:
- Command: `gww pull`
- Detect current repository (source or worktree)
- If in worktree, resolve to source repository
- Verify source repository is on `main` or `master` branch
- Check if source repository is clean (no uncommitted changes)
- If not on main/master: error with exit code 1
- If not clean: error with exit code 1
- Execute `git pull` in source repository
- Report success: "Updated source repository: <path>" to stdout
- Handle errors: not in git repo, not on main/master, not clean, pull failed (exit code 1)
- Handle configuration errors (exit code 2)

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

### FR5: Repository Migration
**Priority**: P3

Users can migrate existing repositories from old locations to new locations based on current configuration.

**Acceptance Criteria**:
- Command: `gww migrate <old_repos> [--dry-run] [--move]`
- Verify `old_repos` path exists and is a directory
- Recursively scan directory tree for git repositories (exclude git submodules; only top-level repos and worktrees are considered)
- For each repository found:
  - Extract URI from remote origin (if available)
  - Calculate expected location using current config
  - Compare current location with expected location
  - If same: Output "Already at target: \<path\>" and include in summary count
  - If different:
    - Output path (e.g. old_path -> new_path) immediately when processing that repository, before copy/move
    - If `--dry-run`: Output each path immediately; at the end print "Would migrate N repositories" (and "Would skip N repositories" if any)
    - Else: Copy or move repository to expected location
    - If repository is a worktree: After moving/copying, call `git worktree repair` on the source repository to update worktree paths
    - If repository is a source repository: No repair needed (worktrees are not migrated with source)
- Report summary: repositories migrated, repaired, skipped, already at target
- Handle errors: invalid path, migration failed (exit code 1)
- Handle configuration errors (exit code 2)

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

### FR6: Configuration Initialization
**Priority**: P3

Users can create a default configuration file with examples and documentation.

**Acceptance Criteria**:
- Command: `gww init config`
- Determine config file path: `$XDG_CONFIG_HOME/gww/config.yml` (or platform equivalent)
- Check if config file already exists
- If exists: print warning and exit with code 1
- Create config directory if needed
- Write default config file with:
  - `default_sources` and `default_worktrees` templates
  - Large comment block with examples:
    - Source rule examples (github, gitlab, custom)
    - Project rule examples
    - Template function documentation
    - All available functions with signatures
- Report success: "Created config file: <path>" to stdout
- Handle errors: config exists, write failed (exit code 1)
- Handle configuration errors: cannot determine config directory (exit code 2)

**Examples**:
```bash
gww init config
# Output: Created config file: ~/.config/gww/config.yml
```

---

### FR7: Shell Completion Initialization
**Priority**: P3

Users can generate and install shell autocompletion scripts for bash, zsh, and fish.

**Acceptance Criteria**:
- Command: `gww init shell <shell>`
- Validate shell name (must be bash, zsh, or fish)
- Generate completion script using argparse's built-in methods
- Determine installation location per shell:
  - `bash`: `~/.bash_completion.d/gww`
  - `zsh`: `~/.zsh/completions/_gww` or `$fpath/_gww`
  - `fish`: `~/.config/fish/completions/gww.fish`
- Write completion script to installation location
- Print installation instructions if manual sourcing needed
- Support dynamic completion for:
  - Subcommands
  - Branch names (local and remote)
  - Worktree paths
  - Options (`--force`, `--dry-run`, etc.)
  - File paths (where applicable)
- Report success with installation path and instructions
- Handle errors: invalid shell, write failed (exit code 1)
- Handle configuration errors (exit code 2)

**Examples**:
```bash
gww init shell bash
# Output:
# Installed bash completion script: ~/.bash_completion.d/gww
# To activate, run: source ~/.bash_completion.d/gww
# Or add to ~/.bashrc: source ~/.bash_completion.d/gww
```

---

## Non-Functional Requirements

### NFR1: Performance
- Command execution < 2 seconds for typical operations
- Config parsing < 100ms
- Template evaluation < 50ms

### NFR2: Type Safety
- All functions must have type hints (Python 3.11+)

### NFR3: Error Handling
- Consistent error handling across all commands
- Clear error messages with context
- Appropriate exit codes (0: success, 1: error, 2: configuration error)

### NFR4: Compatibility
- Must not interfere with native git commands
- Must maintain compatibility with standard git worktree behavior
- Target platform: Unix-like systems (Linux, macOS) with git installed

### NFR5: Configuration
- Configuration file: `gww.yml` in `$XDG_CONFIG_HOME/gww/` (or platform equivalent)
- Support for configurable path templates with function evaluation
- Support for condition-based routing for multiple git hosting providers
- Support for project-specific action hooks

---

## Edge Cases

### EC1: Invalid URI
- Handle malformed URIs gracefully
- Support HTTP, HTTPS, SSH, and file:// protocols
- Extract protocol, host, port, and path segments correctly

### EC2: Missing Configuration
- Handle missing config file gracefully
- Provide clear error message directing user to run `gww init config`

### EC3: Dirty Worktrees
- Prevent removal of dirty worktrees without `--force`
- Provide clear error message with instructions

### EC4: Branch Not Found
- Handle missing branches gracefully
- Provide option to create branch from current commit with `--create-branch`

### EC5: Template Evaluation Errors
- Handle invalid template syntax gracefully
- Provide user-friendly error messages with function name and position

### EC6: Project Action Failures
- Handle action execution failures gracefully
- Continue with remaining actions if one fails (or stop on first failure - TBD)

---

## User Stories

### US1: Clone Repositories (P1) 🎯 MVP
**As a** developer  
**I want to** clone repositories to configurable locations based on URI  
**So that** my repositories are organized automatically by hosting provider

**Acceptance**: See FR1

---

### US2: Add Worktrees (P1) 🎯 MVP
**As a** developer  
**I want to** add worktrees for branches with configurable paths  
**So that** I can work on multiple branches simultaneously in organized locations

**Acceptance**: See FR2

---

### US3: Remove Worktrees (P2)
**As a** developer  
**I want to** remove worktrees by branch name or path  
**So that** I can clean up completed work without manual git commands

**Acceptance**: See FR3

---

### US4: Pull Updates (P2)
**As a** developer  
**I want to** update source repositories safely  
**So that** my source repositories stay up-to-date without breaking worktrees

**Acceptance**: See FR4

---

### US5: Migrate Repositories (P3)
**As a** developer  
**I want to** migrate existing repositories to new locations  
**So that** I can reorganize my repository structure without manual work

**Acceptance**: See FR5

---

### US6: Initialize Configuration (P3)
**As a** developer  
**I want to** create a default configuration file with examples  
**So that** I can quickly set up the tool with documented examples

**Acceptance**: See FR6

---

### US7: Initialize Shell Completion (P3)
**As a** developer  
**I want to** install shell autocompletion  
**So that** I can use tab completion for commands, branches, and options

**Acceptance**: See FR7

---

## Technical Constraints

- **Language**: Python 3.11+
- **Dependency Manager**: uv (exclusive)
- **External Dependencies**: 
  - `simpleeval` (with custom StrictSimpleEval subclass)
  - `ruamel.yaml` (round-trip mode)
- **Testing**: pytest (TDD mandatory)
- **Type Hints**: Required for all functions
- **Minimalism**: Minimal external dependencies, justify each

---

## Configuration Schema

See `data-model.md` for detailed configuration schema, entities, and validation rules.

## Command Contracts

See `contracts/cli-commands.md` for detailed command specifications, arguments, options, behavior, exit codes, and output formats.
