# Data Model: Git Worktree Wrapper

**Date**: 2025-01-27  
**Plan**: `plan.md`

This document defines the core entities, their relationships, validation rules, and state transitions for the git worktree wrapper system.

## Core Entities

### 1. Configuration (Config)

Represents the YAML configuration file (`config.yml` in `$XDG_CONFIG_HOME/gww/`) that defines path templates, source routing rules, and project actions.

**Attributes**:
- `default_sources` (str, required): Template string for default source checkout location
- `default_worktrees` (str, required): Template string for default worktree location
- `sources` (dict[str, SourceRule], optional): Named source routing rules
- `projects` (list[ProjectRule], optional): Project detection and action rules

**Validation Rules**:
- `default_sources` and `default_worktrees` must be non-empty strings
- Template strings must be valid (syntax checked during evaluation)
- `sources` keys must be unique strings
- Each `SourceRule` must have a `predicate` field
- `projects` list must contain valid `ProjectRule` objects

**State**: Immutable after loading (read-only during runtime)

**Relationships**:
- Contains multiple `SourceRule` objects
- Contains multiple `ProjectRule` objects

---

### 2. SourceRule

Represents a predicate-based routing rule for determining source and worktree locations based on repository URI.

**Attributes**:
- `predicate` (str, required): Expression evaluated against URI context (host, path segments)
- `sources` (str, optional): Template string for source checkout location (falls back to `default_sources`)
- `worktrees` (str, optional): Template string for worktree location (falls back to `default_worktrees`)

**Validation Rules**:
- `predicate` must be a valid simpleeval expression
- `predicate` must evaluate to boolean
- `sources` and `worktrees` (if present) must be valid template strings
- At least one source rule must match for any valid URI (or default is used)

**Context Variables** (available during predicate evaluation):
- `host` (str): Hostname from URI (e.g., "github.com", "rulez.netbird.selfhosted")
- `port` (str): Port from URI, empty string if missing (e.g., "3000", "")
- `protocol` (str): Protocol from URI (e.g., "http", "https", "ssh", "git", "file")
- `path` (list[str]): URI path segments (e.g., ["vadimvolk", "ansible"] from "/vadimvolk/ansible.git")
- `uri` (str): Full URI string

**Relationships**:
- Belongs to `Config` (many-to-one)

---

### 3. ProjectRule

Represents a project type detection rule with associated actions to execute during checkout or worktree creation.

**Attributes**:
- `predicate` (str, required): Expression evaluated against repository filesystem (e.g., `file_exists(local.properties)`)
- `source_actions` (list[Action], optional): Actions executed after source checkout
- `worktree_actions` (list[Action], optional): Actions executed when worktree is added

**Validation Rules**:
- `predicate` must be a valid simpleeval expression
- `predicate` must evaluate to boolean
- `source_actions` and `worktree_actions` must be valid action lists
- At least one action type must be specified

**Context Variables** (available during predicate evaluation):
- `source_path` (Path): Absolute path to source repository
- File system functions: `file_exists(path)`, `dir_exists(path)`, etc.

**Relationships**:
- Belongs to `Config` (many-to-one)
- Contains multiple `Action` objects

---

### 4. Action

Represents a single action to execute (file copy or command execution).

**Types**:
1. **AbsCopyAction**: Copy file from absolute path to relative destination
2. **RelCopyAction**: Copy file from source to worktree (relative path)
3. **CommandAction**: Execute external command

**Common Attributes**:
- `type` (str): One of "abs_copy", "rel_copy", "command"

**AbsCopyAction Attributes**:
- `source` (str, required): Absolute source file path
- `destination` (str, required): Relative destination path (from repo root)

**RelCopyAction Attributes**:
- `source` (str, required): Relative source path (from source repo root)
- `destination` (str, optional): Relative destination path (defaults to same as source)

**CommandAction Attributes**:
- `command` (str, required): Command name or path to executable
- `args` (list[str], optional): Additional command arguments

**Validation Rules**:
- `type` must be one of the valid action types
- Required attributes must be non-empty strings
- `AbsCopyAction.source` must be absolute path
- `RelCopyAction` only valid in `worktree_actions` context
- `CommandAction.command` must be executable or in PATH

**Relationships**:
- Belongs to `ProjectRule` (many-to-one)

---

### 5. Repository

Represents a git repository (source or worktree).

**Attributes**:
- `path` (Path, required): Absolute path to repository root
- `uri` (str, optional): Original checkout URI (for source repositories)
- `branch` (str, optional): Current checked-out branch
- `is_worktree` (bool, required): Whether this is a worktree (not main repository)
- `worktree_name` (str, optional): Name of worktree (if named)
- `is_clean` (bool, computed): Whether repository has uncommitted changes

**Validation Rules**:
- `path` must exist and be a valid git repository
- `path` must be absolute
- `is_worktree` must be consistent with `.git` file vs directory
- `worktree_name` only valid if `is_worktree` is True

**State Transitions**:
- **Clean → Dirty**: When files are modified, staged, or untracked files added
- **Dirty → Clean**: When changes are committed or discarded

**Relationships**:
- May have multiple `Worktree` objects (one-to-many, for source repos)

---

### 6. Worktree

Represents a git worktree linked to a source repository.

**Attributes**:
- `path` (Path, required): Absolute path to worktree root
- `branch` (str, required): Branch checked out in worktree
- `name` (str, optional): Optional worktree name
- `source_repo` (Path, required): Path to source repository
- `is_clean` (bool, computed): Whether worktree has uncommitted changes

**Validation Rules**:
- `path` must exist and be a valid worktree
- `branch` must exist in source repository (or be created from current commit if `--create-branch` used)
- `name` is only used for path definition in templates, does not detach worktree from repository
- `source_repo` must be a valid source repository (not another worktree)

**State Transitions**:
- **Created**: When `git worktree add` succeeds
- **Removed**: When `git worktree remove` succeeds or directory deleted
- **Clean → Dirty**: When files modified
- **Dirty → Clean**: When changes committed

**Relationships**:
- Belongs to `Repository` (many-to-one, source repository)

---

### 7. TemplateContext

Context object passed to template evaluator for resolving template variables.

**Attributes**:
- `uri` (str, optional): Repository URI (for checkout operations)
- `host` (str, optional): URI hostname
- `port` (str, optional): URI port, empty string if missing
- `protocol` (str, optional): URI protocol (http, https, ssh, git, file, etc.)
- `path_segments` (list[str], optional): URI path segments
- `branch` (str, optional): Git branch name
- `worktree_name` (str, optional): Worktree name (if named)
- `source_path` (Path, optional): Source repository path (for worktree operations)

**Validation Rules**:
- If `uri` provided, `host` and `path_segments` should be derivable
- `branch` required for worktree template evaluation
- `source_path` required for worktree template evaluation

**Relationships**:
- Used by template evaluator (no persistent relationship)

---

### 8. TemplateFunction

Built-in functions available in template expressions.

**Functions**:
- `path(index: int) -> str`: Get URI path segment by index (0-based, negative for reverse)
- `path(-1)`: Last path segment
- `path(-2)`: Second-to-last path segment
- `branch() -> str`: Current branch name (as-is)
- `norm_branch(replacement: str = "-") -> str`: Branch name with "/" replaced with `replacement` (default: "-")
  - `norm_branch()`: Branch name with "/" replaced with "-"
  - `norm_branch("_")`: Branch name with "/" replaced with "_"
- `worktree() -> str`: Worktree name, or "" if unnamed
- `prefix_worktree(prefix: str = "-") -> str`: Returns "" if no worktree name, else "prefix{name}" (default prefix: "-")
- `prefix_branch(prefix: str = "-") -> str`: Returns branch if no worktree name, else "{worktree_name}{prefix}{branch}" (default prefix: "-")
- `norm_prefix_branch() -> str`: Returns branch if no worktree name, else "prefix-branch"

**Validation Rules**:
- Function names must be valid identifiers
- Argument types must match function signatures (enforced by StrictSimpleEval)
- Argument count must match function signatures

**Relationships**:
- Used by template evaluator (no persistent relationship)

---

## Relationships Summary

```
Config
├── contains many SourceRule
├── contains many ProjectRule
└── ProjectRule contains many Action

Repository (source)
└── has many Worktree

TemplateContext
└── used by TemplateEvaluator (no persistent storage)
```

## State Transitions

### Repository Lifecycle

1. **Source Repository**:
   - Created: `gww clone <uri>` → repository cloned to source location
   - Updated: `gww pull` → source repository updated if clean and on main/master
   - Removed: Manual deletion (not managed by gww)

2. **Worktree Lifecycle**:
   - Created: `gww add <branch> [name]` → worktree added at computed location
   - Removed: `gww remove <branch|path> [--force]` → worktree removed if clean (or forced)
   - Updated: Via `gww pull` (updates source, which affects worktrees)

### Configuration Lifecycle

1. **Loaded**: On first command execution, config loaded from `$XDG_CONFIG_HOME/gww/config.yml` (or platform equivalent)
2. **Validated**: Syntax and structure validated on load
3. **Cached**: Config cached in memory for the duration of the `gww` command execution (no file change detection)
4. **Modified**: Via `gww init config` (creates new default config)

## Validation Rules Summary

### Configuration Validation
- YAML syntax must be valid
- Required fields must be present
- Template strings must be parseable
- Predicates must be valid simpleeval expressions
- Action types must be recognized

### Repository Validation
- Path must exist and be absolute
- Must be valid git repository
- Worktree must be linked to valid source repository
- Branch must exist in source repository

### Template Validation
- Function calls must use valid function names
- Function arguments must match signatures
- Template variables must be available in context
- Escaped parentheses `((` must be handled correctly

## Error Handling

**Configuration Errors**:
- Invalid YAML: Raise `ConfigParseError` with file location
- Missing required field: Raise `ConfigValidationError` with field name
- Invalid template: Raise `TemplateError` with template string and position

**Repository Errors**:
- Invalid path: Raise `RepositoryError` with path
- Not a git repo: Raise `NotGitRepositoryError`
- Worktree not clean: Raise `WorktreeDirtyError` (unless `--force`)

**Template Errors**:
- Unknown function: Raise `FunctionNotDefinedError` with function name
- Wrong argument types: Raise `FunctionTypeError` with expected/actual types
- Missing context variable: Raise `ContextError` with variable name
