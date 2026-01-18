# Quickstart Guide: Git Worktree Wrapper

**Date**: 2025-01-27  
**Plan**: `plan.md`

This document provides practical examples, test scenarios, and usage patterns for the `gww` tool.

## Initial Setup

### 1. Initialize Configuration

```bash
# Create default configuration file
gww init config

# Output:
# Created config file: ~/.config/gww/config.yml
```

The default config will be created with:
- Basic `default_sources` and `default_worktrees` templates
- Commented examples for github, gitlab, and custom source rules
- Documentation for all template functions

### 2. Customize Configuration (Optional)

Edit `~/.config/gww/config.yml` to add your source routing rules:

```yaml
default_sources: ~/Developer/sources/default/path(-2)/path(-1)
default_worktrees: ~/Developer/worktrees/default/path(-2)/path(-1)/norm_branch()

sources:
    github:
        predicate: "github" in host
        sources: ~/Developer/sources/github/path(-2)/path(-1)
        worktrees: ~/Developer/worktrees/github/path(-2)/path(-1)/branch()
    
    gitlab:
        predicate: "gitlab" in host and !contains(host, "scp")
        sources: ~/Developer/sources/gitlab/path(-3)/path(-2)/path(-1)
        worktrees: ~/Developer/worktrees/gitlab/path(-3)/path(-2)/path(-1)-branch()
```

### 3. Install Shell Completion (Optional)

```bash
# Install bash completion
gww init shell bash
# Then add to ~/.bashrc: source ~/.bash_completion.d/gww

# Install zsh completion
gww init shell zsh
# Then add to ~/.zshrc: fpath=(~/.zsh/completions $fpath)

# Install fish completion
gww init shell fish
# Restart fish shell
```

## Basic Workflows

### Workflow 1: Clone a New Repository

**Scenario**: Clone a GitHub repository

```bash
# Clone repository
gww clone https://github.com/vadimvolk/ansible.git

# Expected output:
# ~/Developer/sources/github/vadimvolk/ansible

# Verify
cd ~/Developer/sources/github/vadimvolk/ansible
git status
```

**Test Case**:
- **Given**: No existing repository at expected location
- **When**: `gww clone https://github.com/vadimvolk/ansible.git`
- **Then**: Repository cloned to `~/Developer/sources/github/vadimvolk/ansible`

### Workflow 2: Add a Worktree

**Scenario**: Create a worktree for a feature branch

```bash
# Navigate to source repository
cd ~/Developer/sources/github/vadimvolk/ansible

# Add worktree for feature branch
gww add feature/new-ui

# Expected output:
# ~/Developer/worktrees/github/vadimvolk/ansible/feature-new-ui

# Verify
cd ~/Developer/worktrees/github/vadimvolk/ansible/feature-new-ui
git branch
# Output: * feature/new-ui
```

**Test Case**:
- **Given**: Source repository at `~/Developer/sources/github/vadimvolk/ansible`
- **When**: `gww add feature/new-ui`
- **Then**: Worktree created at `~/Developer/worktrees/github/vadimvolk/ansible/feature-new-ui` with branch `feature/new-ui` checked out

### Workflow 3: Create Branch from Current Commit

**Scenario**: Create a new branch from current commit and add worktree

```bash
cd ~/Developer/sources/github/vadimvolk/ansible

# Create branch from current commit and add worktree
gww add new-feature -c

# Expected output:
# ~/Developer/worktrees/github/vadimvolk/ansible/new-feature

# Or from a worktree
cd ~/Developer/worktrees/github/vadimvolk/ansible/other-branch
gww add another-feature -c
# Creates branch from commit in current worktree
```

**Test Case**:
- **Given**: Source repository on commit abc123
- **When**: `gww add new-feature -c`
- **Then**: Branch 'new-feature' created from abc123, worktree added

### Workflow 4: Remove Worktree

**Scenario**: Remove a worktree when feature is complete

```bash
# Remove by branch name
cd ~/Developer/sources/github/vadimvolk/ansible
gww remove feature/new-ui

# Expected output:
# Removed worktree: ~/Developer/worktrees/github/vadimvolk/ansible/feature-new-ui

# Or remove by path
gww remove ~/Developer/worktrees/github/vadimvolk/ansible/feature-new-ui
```

**Test Case - Clean Worktree**:
- **Given**: Clean worktree at path
- **When**: `gww remove feature/new-ui`
- **Then**: Worktree removed successfully

**Test Case - Dirty Worktree**:
- **Given**: Worktree with uncommitted changes
- **When**: `gww remove feature/new-ui` (without --force)
- **Then**: Error: "Worktree has uncommitted changes. Use --force to remove anyway."

**Test Case - Force Remove**:
- **Given**: Dirty worktree
- **When**: `gww remove feature/new-ui --force`
- **Then**: Worktree removed despite uncommitted changes

### Workflow 5: Update Source Repository

**Scenario**: Pull latest changes to source repository

```bash
# From source repository
cd ~/Developer/sources/github/vadimvolk/ansible
gww pull

# Expected output:
# Updated source repository: ~/Developer/sources/github/vadimvolk/ansible

# Or from worktree (updates source)
cd ~/Developer/worktrees/github/vadimvolk/ansible/feature-new-ui
gww pull

# Expected output:
# Updated source repository: ~/Developer/sources/github/vadimvolk/ansible
```

**Test Case - Clean on Main**:
- **Given**: Source repository on `main` branch, clean working directory
- **When**: `gww pull`
- **Then**: `git pull` executed successfully

**Test Case - Not on Main**:
- **Given**: Source repository on `develop` branch
- **When**: `gww pull`
- **Then**: Error: "Source repository must be on 'main' or 'master' branch"

**Test Case - Dirty Repository**:
- **Given**: Source repository with uncommitted changes
- **When**: `gww pull`
- **Then**: Error: "Source repository has uncommitted changes. Commit or stash changes first."

## Advanced Scenarios

### Scenario 1: Multiple Source Providers

**Setup**: Config with github, gitlab, and custom rules

```yaml
sources:
    github:
        predicate: "github" in host
        sources: ~/Developer/sources/github/path(-2)/path(-1)
    
    gitlab:
        predicate: "gitlab" in host and !contains(host, "scp")
        sources: ~/Developer/sources/gitlab/path(-3)/path(-2)/path(-1)
    
    custom:
        predicate: path(0) == "myorg"
        sources: ~/Developer/sources/custom/path(-2)/path(-1)
```

**Test Cases**:
```bash
# GitHub repository
gww clone https://github.com/user/repo.git
# → ~/Developer/sources/github/user/repo

# GitLab repository
gww clone https://gitlab.com/group/subgroup/project.git
# → ~/Developer/sources/gitlab/group/subgroup/project

# Custom organization
gww clone https://git.example.com/myorg/project.git
# → ~/Developer/sources/custom/myorg/project

# Default (no match)
gww clone https://other.com/user/repo.git
# → ~/Developer/sources/default/user/repo
```

### Scenario 2: Project Actions

**Setup**: Config with project detection and actions

```yaml
actions:
    - predicate: file_exists(local.properties)
      source_actions:
          - abs_copy("~/sources/default-local.properties", "local.properties")
      worktree_actions:
          - rel_copy("local.properties")
          - command("custom-handler")
```

**Test Case**:
- **Given**: Repository with `local.properties` file
- **When**: `gww clone <uri>` or `gww add <branch>`
- **Then**: 
  - After clone: `local.properties` copied from `~/sources/default-local.properties`
  - After worktree add: `local.properties` copied from source to worktree, then `custom-handler` executed

### Scenario 3: Tag-Based Routing

**Setup**: Config with tag-based source routing

```yaml
sources:
  production:
    predicate: 'tag_exist("env") and tag("env") == "prod"'
    sources: ~/Developer/sources/prod/path(-2)/path(-1)
    worktrees: ~/Developer/worktrees/prod/path(-2)/path(-1)/norm_branch()
  
  development:
    predicate: 'tag_exist("env") and tag("env") == "dev"'
    sources: ~/Developer/sources/dev/path(-2)/path(-1)
    worktrees: ~/Developer/worktrees/dev/path(-2)/path(-1)/norm_branch()
  
  project_backend:
    predicate: 'tag_exist("project") and tag("project") == "backend"'
    sources: ~/Developer/sources/backend/path(-2)/path(-1)
    worktrees: ~/Developer/worktrees/backend/path(-2)/path(-1)/norm_branch()
```

**Test Cases**:
```bash
# Production environment
gww clone https://github.com/user/repo.git --tag env=prod
# → ~/Developer/sources/prod/user/repo

# Development environment
gww clone https://github.com/user/repo.git --tag env=dev
# → ~/Developer/sources/dev/user/repo

# Backend project
gww clone https://github.com/user/repo.git --tag project=backend
# → ~/Developer/sources/backend/user/repo

# Multiple tags
gww add feature-branch --tag env=dev --tag team=frontend
# Tags available in worktree path template
```

### Scenario 4: Tag-Based Path Templates

**Setup**: Config using tags in path templates

```yaml
default_sources: ~/Developer/sources/tag("env")/path(-2)/path(-1)
default_worktrees: ~/Developer/worktrees/tag("team")/path(-2)/path(-1)/norm_branch()
```

**Test Cases**:
```bash
# Clone with environment tag
gww clone https://github.com/user/repo.git --tag env=prod
# → ~/Developer/sources/prod/user/repo

# Add worktree with team tag
cd ~/Developer/sources/prod/user/repo
gww add feature-branch --tag team=frontend
# → ~/Developer/worktrees/frontend/user/repo/feature-branch

# Tags without values (tag_exist() returns True, tag() returns "")
gww clone https://github.com/user/repo.git --tag experimental
# tag_exist("experimental") returns True
# tag("experimental") returns ""
```

### Scenario 3: Migration

**Setup**: Old repositories in `~/old-repos` need to be migrated

```bash
# Dry run to see what would be migrated
gww migrate ~/old-repos --dry-run

# Expected output:
# Would migrate 3 repositories:
#   ~/old-repos/repo1 -> ~/Developer/sources/github/user/repo1
#   ~/old-repos/repo2 -> ~/Developer/sources/gitlab/group/repo2
#   ~/old-repos/repo3 -> ~/Developer/sources/default/org/repo3

# Actual migration (copy)
gww migrate ~/old-repos

# Or move instead of copy
gww migrate ~/old-repos --move
```

**Test Case**:
- **Given**: Old repositories in `~/old-repos` with various origins
- **When**: `gww migrate ~/old-repos --dry-run`
- **Then**: List of repositories that would be migrated with old and new paths

**Test Case**:
- **Given**: Old repositories
- **When**: `gww migrate ~/old-repos`
- **Then**: Repositories copied to new locations based on current config

## Template Function Examples

**Function Availability**:
- **Shared functions** (available in templates, URI predicates, and project predicates):
  - URI functions: `host()`, `port()`, `protocol()`, `uri()`, `path(index)`
  - Branch functions: `branch()`, `norm_branch(replacement)` (when branch context available)
  - Tag functions: `tag(name)`, `tag_exist(name)`
- **Project-specific functions** (only in project predicates):
  - `source_path()` - returns current repository/worktree root path (detects from cwd, returns empty string if not in git repo)
  - `file_exists(path)`, `dir_exists(path)`, `path_exists(path)` - check paths relative to source repository

### Path Functions

```yaml
# URI: https://github.com/vadimvolk/ansible.git
# Path segments: ["vadimvolk", "ansible"]

default_sources: ~/Developer/sources/path(-2)/path(-1)
# Evaluates to: ~/Developer/sources/vadimvolk/ansible

default_sources: ~/Developer/sources/path(0)/path(1)
# Evaluates to: ~/Developer/sources/vadimvolk/ansible

default_sources: ~/Developer/sources/path(-1)
# Evaluates to: ~/Developer/sources/ansible
```

### Branch Functions

```yaml
# Branch: "feature/new-ui"

worktrees: ~/worktrees/branch()
# Evaluates to: ~/worktrees/feature/new-ui

worktrees: ~/worktrees/norm_branch()
# Evaluates to: ~/worktrees/feature-new-ui

worktrees: ~/worktrees/norm_branch("_")
# Evaluates to: ~/worktrees/feature_new_ui
```

### URI Functions

```yaml
# URI: https://github.com/vadimvolk/ansible.git

# Using URI functions in templates (now available!)
sources: ~/Developer/sources/host()/path(-2)/path(-1)
# Evaluates to: ~/Developer/sources/github.com/vadimvolk/ansible

sources: ~/Developer/sources/protocol()/path(-2)/path(-1)
# Evaluates to: ~/Developer/sources/https/vadimvolk/ansible

# Using URI functions in predicates
sources:
  github:
    predicate: '"github" in host()'
    sources: ~/Developer/sources/github/path(-2)/path(-1)
  
  custom:
    predicate: 'path(0) == "myorg"'
    sources: ~/Developer/sources/custom/path(-2)/path(-1)
```

### Tag Functions

```yaml
# Tags provided: --tag env=prod --tag project=backend

# Using tag() in path templates
sources: ~/Developer/sources/tag("env")/path(-2)/path(-1)
# Evaluates to: ~/Developer/sources/prod/vadimvolk/ansible

worktrees: ~/Developer/worktrees/tag("project")/path(-1)/branch()
# Evaluates to: ~/Developer/worktrees/backend/ansible/feature-branch

# Using tag_exist() in predicates
sources:
  production:
    predicate: 'tag_exist("env") and tag("env") == "prod"'
    sources: ~/Developer/sources/prod/path(-2)/path(-1)
  
  development:
    predicate: 'tag_exist("env") and tag("env") == "dev"'
    sources: ~/Developer/sources/dev/path(-2)/path(-1)
```

**Examples with tags**:
```bash
# Clone with tags
gww clone https://github.com/user/repo.git --tag env=prod --tag project=backend
# Tags available in templates and predicates

# Add worktree with tags
gww add feature-branch --tag env=dev --tag team=frontend
# Tags can be used in worktree path templates
```

### Project Predicate Functions

```yaml
# Project-specific functions (only available in project predicates)
actions:
  - predicate: 'file_exists("package.json")'
    source_actions:
      - type: command
        command: npm
        args: ["install"]
  
  - predicate: 'dir_exists("src") and file_exists("pom.xml")'
    source_actions:
      - type: command
        command: mvn
        args: ["install", "-DskipTests"]
  
  - predicate: 'path_exists("setup.py")'
    source_actions:
      - type: command
        command: pip
        args: ["install", "-e", "."]

# Shared functions also available in project predicates
actions:
  - predicate: 'file_exists("package.json") and tag("env") == "prod"'
    source_actions:
      - type: command
        command: npm
        args: ["run", "build:prod"]
  
  - predicate: 'host() == "github.com" and file_exists("Makefile")'
    source_actions:
      - type: command
        command: make
        args: ["install"]
```

### Escaping Parentheses

```yaml
# Template with literal parentheses
worktrees: ~/worktrees/not_function((my folder))
# Evaluates to: ~/worktrees/not_function(my folder)
# Double parentheses (( become single (
```

## Error Scenarios

### Invalid Configuration

```bash
# Config file has syntax error
gww clone https://github.com/user/repo.git

# Expected output (stderr):
# Error: Invalid YAML in config file ~/.config/gww/config.yml
# Line 5: unexpected character
```

### Invalid URI

```bash
# Invalid git URI
gww clone not-a-uri

# Expected output (stderr):
# Error: Invalid repository URI: not-a-uri
```

### Branch Not Found

```bash
# Branch doesn't exist
cd ~/Developer/sources/github/user/repo
gww add nonexistent-branch

# Expected output (stderr):
# Error: Branch 'nonexistent-branch' not found in repository
```

### Worktree Already Exists

```bash
# Worktree for branch already exists
cd ~/Developer/sources/github/user/repo
gww add feature-branch
gww add feature-branch  # Again

# Expected output (stderr):
# Error: Worktree for branch 'feature-branch' already exists at <path>
```

## Integration Test Scenarios

### End-to-End: Clone to Worktree

```bash
# 1. Clone repository
gww clone https://github.com/user/repo.git
# → ~/Developer/sources/github/user/repo

# 2. Add worktree
cd ~/Developer/sources/github/user/repo
gww add feature-branch
# → ~/Developer/worktrees/github/user/repo/feature-branch

# 3. Work in worktree
cd ~/Developer/worktrees/github/user/repo/feature-branch
# ... make changes, commit ...

# 4. Update source
gww pull
# Updates source repository

# 5. Remove worktree when done
cd ~/Developer/sources/github/user/repo
gww remove feature-branch
# Worktree removed
```

### Multiple Worktrees

```bash
cd ~/Developer/sources/github/user/repo

# Create multiple worktrees
gww add feature-1
gww add feature-2
gww add feature-3

# List worktrees
git worktree list

# Remove specific worktree
gww remove feature-2
```

## Performance Expectations

- **Config loading**: < 50ms
- **Template evaluation**: < 10ms per template
- **Clone operation**: Depends on git clone speed (typically 1-5 seconds)
- **Worktree add**: < 1 second
- **Worktree remove**: < 500ms
- **Pull operation**: Depends on network (typically 1-3 seconds)

## Troubleshooting

### Config Not Found

```bash
# Error: Config file not found
# Solution: Run gww init config
gww init config
```

### Template Evaluation Error

```bash
# Error: Template evaluation failed: Function 'unknown_func' not defined
# Solution: Check config file for typos in function names
# Valid functions: path, branch, norm_branch
```

### Git Command Failures

```bash
# Error: git clone failed: repository not found
# Solution: Verify URI is correct and accessible
# Check: git clone <uri> works manually
```
