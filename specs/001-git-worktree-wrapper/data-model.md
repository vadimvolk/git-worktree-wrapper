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

**Context Functions** (available during predicate evaluation):
- URI functions: `host()`, `port()`, `protocol()`, `uri()`, `path()`, `path(index)` (see TemplateFunction section)
- Tag functions: `tag(name)`, `tag_exist(name)` (see TemplateFunction section)

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

**Context Functions** (available during predicate evaluation):
- Shared functions: URI functions (`host()`, `port()`, `protocol()`, `uri()`, `path()`, `path(index)`), tag functions (`tag(name)`, `tag_exist(name)`) - see TemplateFunction section
- Project-specific functions (only in project predicates):
  - `source_path() -> str`: Absolute path to current repository or worktree root (detects from cwd)
  - `file_exists(path: str) -> bool`: Check if file exists in source repository (relative to repo root)
  - `dir_exists(path: str) -> bool`: Check if directory exists in source repository (relative to repo root)
  - `path_exists(path: str) -> bool`: Check if path exists (file or directory) in source repository (relative to repo root)

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
- `is_clean` (bool, computed): Whether repository has uncommitted changes

**Validation Rules**:
- `path` must exist and be a valid git repository
- `path` must be absolute
- `is_worktree` must be consistent with `.git` file vs directory

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
- `source_repo` (Path, required): Path to source repository
- `is_clean` (bool, computed): Whether worktree has uncommitted changes

**Validation Rules**:
- `path` must exist and be a valid worktree
- `branch` must exist in source repository (or be created from current commit if `--create-branch` used)
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
- `uri` (ParsedURI, optional): Parsed URI object (for checkout operations)
- `host` (str, optional): URI hostname (derived from `uri` object)
- `port` (str, optional): URI port, empty string if missing (derived from `uri` object)
- `protocol` (str, optional): URI protocol (http, https, ssh, git, file, etc.) (derived from `uri` object)
- `path_segments` (list[str], optional): URI path segments (derived from `uri` object)
- `branch` (str, optional): Git branch name (for worktree operations)
- `source_path` (Path, optional): Source repository path (for worktree operations)
- `tags` (dict[str, str], optional): Dictionary of tag key-value pairs passed via `--tag` CLI option

**Validation Rules**:
- If `uri` provided, `host` and `path_segments` should be derivable
- `branch` required for worktree template evaluation
- `source_path` required for worktree template evaluation
- Tags are optional and can be empty dictionary

**Relationships**:
- Used by template evaluator (no persistent relationship)

---

### 8. TemplateFunction

Built-in functions available in template expressions, URI predicates, and project predicates.

**Function Availability**:
- **Shared functions** (available in templates, URI predicates, and project predicates):
  - URI functions: `host()`, `port()`, `protocol()`, `uri()`, `path()`, `path(index)`
  - Branch functions: `branch()`, `norm_branch(replacement)`
  - Tag functions: `tag(name)`, `tag_exist(name)`
- **Project-specific functions** (only available in project predicates):
  - `source_path()`, `file_exists(path)`, `dir_exists(path)`, `path_exists(path)`

**URI Functions**:
- `host() -> str`: Hostname from URI (e.g., "github.com", "rulez.netbird.selfhosted")
- `port() -> str`: Port from URI, empty string if missing (e.g., "3000", "")
- `protocol() -> str`: Protocol from URI (e.g., "http", "https", "ssh", "git", "file")
- `uri() -> str`: Full URI string
- `path() -> list[str]`: URI path segments as list (e.g., ["vadimvolk", "ansible"] from "/vadimvolk/ansible.git")
  - Use `path()[0]` to access first segment, `path()[-1]` for last segment
- `path(index: int) -> str`: Get URI path segment by index (0-based, negative for reverse)
  - `path(-1)`: Last path segment
  - `path(-2)`: Second-to-last path segment
  - `path(0)`: First path segment
  - Note: `path()` with no args returns list, `path(index)` with index returns string

**Branch Functions** (require branch context):
- `branch() -> str`: Current branch name (as-is)
- `norm_branch(replacement: str = "-") -> str`: Branch name with "/" replaced with `replacement` (default: "-")
  - `norm_branch()`: Branch name with "/" replaced with "-"
  - `norm_branch("_")`: Branch name with "/" replaced with "_"

**Tag Functions**:
- `tag(name: str) -> str`: Get tag value by name. Returns empty string if tag doesn't exist or has no value
  - `tag("env")`: Returns value of tag "env" (e.g., "prod", "dev")
  - `tag("project")`: Returns value of tag "project" if set, empty string otherwise
- `tag_exist(name: str) -> bool`: Check if tag exists (with or without value). Returns True if tag exists, False otherwise
  - `tag_exist("env")`: Returns True if tag "env" was provided via `--tag env` or `--tag env=value`
  - Useful in predicates: `tag_exist("env") and tag("env") == "prod"`

**Project Functions** (only in project predicates):
- `source_path() -> str`: Absolute path to current repository or worktree root. Detects based on current working directory:
  - If in source repository: returns source repository root
  - If in worktree: returns worktree root
  - If in subdirectory: finds and returns repository/worktree root
  - If not in git repository: returns empty string
- `file_exists(path: str) -> bool`: Check if file exists in source repository (path relative to repo root)
- `dir_exists(path: str) -> bool`: Check if directory exists in source repository (path relative to repo root)
- `path_exists(path: str) -> bool`: Check if path exists (file or directory) in source repository (path relative to repo root)

**Validation Rules**:
- Function names must be valid identifiers
- Argument types must match function signatures (enforced by StrictSimpleEval)
- Argument count must match function signatures
- `tag()` returns empty string for non-existent tags (never raises error)
- `tag_exist()` returns boolean (never raises error)

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
