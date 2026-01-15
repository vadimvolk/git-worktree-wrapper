# Quickstart Guide: Git Worktree Wrapper

**Date**: 2025-01-27  
**Plan**: `plan.md`

This document provides practical examples, test scenarios, and usage patterns for the `sgw` tool.

## Initial Setup

### 1. Initialize Configuration

```bash
# Create default configuration file
sgw init config

# Output:
# Created config file: ~/.config/sgw/config.yml
```

The default config will be created with:
- Basic `default_sources` and `default_worktrees` templates
- Commented examples for github, gitlab, and custom source rules
- Documentation for all template functions

### 2. Customize Configuration (Optional)

Edit `~/.config/sgw/config.yml` to add your source routing rules:

```yaml
default_sources: ~/Developer/sources/default/path(-2)/path(-1)
default_worktrees: ~/Developer/worktrees/default/path(-2)/path(-1)/norm_branch()prefix_worktree("-")

sources:
    github:
        predicate: "github" in host
        sources: ~/Developer/sources/github/path(-2)/path(-1)
        worktrees: ~/Developer/worktrees/github/path(-2)/path(-1)/branch()prefix_worktree("/")
    
    gitlab:
        predicate: "gitlab" in host and !contains(host, "scp")
        sources: ~/Developer/sources/gitlab/path(-3)/path(-2)/path(-1)
        worktrees: ~/Developer/worktrees/gitlab/path(-3)/path(-2)/path(-1)-branch()prefix_worktree("/")
```

### 3. Install Shell Completion (Optional)

```bash
# Install bash completion
sgw init shell bash
# Then add to ~/.bashrc: source ~/.bash_completion.d/sgw

# Install zsh completion
sgw init shell zsh
# Then add to ~/.zshrc: fpath=(~/.zsh/completions $fpath)

# Install fish completion
sgw init shell fish
# Restart fish shell
```

## Basic Workflows

### Workflow 1: Clone a New Repository

**Scenario**: Clone a GitHub repository

```bash
# Clone repository
sgw clone https://github.com/vadimvolk/ansible.git

# Expected output:
# ~/Developer/sources/github/vadimvolk/ansible

# Verify
cd ~/Developer/sources/github/vadimvolk/ansible
git status
```

**Test Case**:
- **Given**: No existing repository at expected location
- **When**: `sgw clone https://github.com/vadimvolk/ansible.git`
- **Then**: Repository cloned to `~/Developer/sources/github/vadimvolk/ansible`

### Workflow 2: Add a Worktree

**Scenario**: Create a worktree for a feature branch

```bash
# Navigate to source repository
cd ~/Developer/sources/github/vadimvolk/ansible

# Add worktree for feature branch
sgw add feature/new-ui

# Expected output:
# ~/Developer/worktrees/github/vadimvolk/ansible/feature-new-ui

# Verify
cd ~/Developer/worktrees/github/vadimvolk/ansible/feature-new-ui
git branch
# Output: * feature/new-ui
```

**Test Case**:
- **Given**: Source repository at `~/Developer/sources/github/vadimvolk/ansible`
- **When**: `sgw add feature/new-ui`
- **Then**: Worktree created at `~/Developer/worktrees/github/vadimvolk/ansible/feature-new-ui` with branch `feature/new-ui` checked out

### Workflow 3: Add Named Worktree

**Scenario**: Create a named worktree (name used in path template only)

```bash
cd ~/Developer/sources/github/vadimvolk/ansible

# Add named worktree
sgw add feature/new-ui ui-work

# Expected output:
# ~/Developer/worktrees/github/vadimvolk/ansible/ui-work-feature-new-ui

# Verify worktree (name is part of path, worktree remains attached)
git worktree list
# Output shows worktree at computed path
```

**Test Case**:
- **Given**: Source repository
- **When**: `sgw add feature/new-ui ui-work`
- **Then**: Worktree created at path using worktree_name in template (worktree remains attached to repository)

### Workflow 3a: Create Branch from Current Commit

**Scenario**: Create a new branch from current commit and add worktree

```bash
cd ~/Developer/sources/github/vadimvolk/ansible

# Create branch from current commit and add worktree
sgw add new-feature -c

# Expected output:
# ~/Developer/worktrees/github/vadimvolk/ansible/new-feature

# Or from a worktree
cd ~/Developer/worktrees/github/vadimvolk/ansible/other-branch
sgw add another-feature -c
# Creates branch from commit in current worktree
```

**Test Case**:
- **Given**: Source repository on commit abc123
- **When**: `sgw add new-feature -c`
- **Then**: Branch 'new-feature' created from abc123, worktree added

### Workflow 4: Remove Worktree

**Scenario**: Remove a worktree when feature is complete

```bash
# Remove by branch name
cd ~/Developer/sources/github/vadimvolk/ansible
sgw remove feature/new-ui

# Expected output:
# Removed worktree: ~/Developer/worktrees/github/vadimvolk/ansible/feature-new-ui

# Or remove by path
sgw remove ~/Developer/worktrees/github/vadimvolk/ansible/feature-new-ui
```

**Test Case - Clean Worktree**:
- **Given**: Clean worktree at path
- **When**: `sgw remove feature/new-ui`
- **Then**: Worktree removed successfully

**Test Case - Dirty Worktree**:
- **Given**: Worktree with uncommitted changes
- **When**: `sgw remove feature/new-ui` (without --force)
- **Then**: Error: "Worktree has uncommitted changes. Use --force to remove anyway."

**Test Case - Force Remove**:
- **Given**: Dirty worktree
- **When**: `sgw remove feature/new-ui --force`
- **Then**: Worktree removed despite uncommitted changes

### Workflow 5: Update Source Repository

**Scenario**: Pull latest changes to source repository

```bash
# From source repository
cd ~/Developer/sources/github/vadimvolk/ansible
sgw pull

# Expected output:
# Updated source repository: ~/Developer/sources/github/vadimvolk/ansible

# Or from worktree (updates source)
cd ~/Developer/worktrees/github/vadimvolk/ansible/feature-new-ui
sgw pull

# Expected output:
# Updated source repository: ~/Developer/sources/github/vadimvolk/ansible
```

**Test Case - Clean on Main**:
- **Given**: Source repository on `main` branch, clean working directory
- **When**: `sgw pull`
- **Then**: `git pull` executed successfully

**Test Case - Not on Main**:
- **Given**: Source repository on `develop` branch
- **When**: `sgw pull`
- **Then**: Error: "Source repository must be on 'main' or 'master' branch"

**Test Case - Dirty Repository**:
- **Given**: Source repository with uncommitted changes
- **When**: `sgw pull`
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
sgw clone https://github.com/user/repo.git
# → ~/Developer/sources/github/user/repo

# GitLab repository
sgw clone https://gitlab.com/group/subgroup/project.git
# → ~/Developer/sources/gitlab/group/subgroup/project

# Custom organization
sgw clone https://git.example.com/myorg/project.git
# → ~/Developer/sources/custom/myorg/project

# Default (no match)
sgw clone https://other.com/user/repo.git
# → ~/Developer/sources/default/user/repo
```

### Scenario 2: Project Actions

**Setup**: Config with project detection and actions

```yaml
projects:
    - predicate: file_exists(local.properties)
      source_actions:
          - abs_copy("~/sources/default-local.properties", "local.properties")
      worktree_actions:
          - rel_copy("local.properties")
          - command("custom-handler")
```

**Test Case**:
- **Given**: Repository with `local.properties` file
- **When**: `sgw clone <uri>` or `sgw add <branch>`
- **Then**: 
  - After clone: `local.properties` copied from `~/sources/default-local.properties`
  - After worktree add: `local.properties` copied from source to worktree, then `custom-handler` executed

### Scenario 3: Migration

**Setup**: Old repositories in `~/old-repos` need to be migrated

```bash
# Dry run to see what would be migrated
sgw migrate ~/old-repos --dry-run

# Expected output:
# Would migrate 3 repositories:
#   ~/old-repos/repo1 -> ~/Developer/sources/github/user/repo1
#   ~/old-repos/repo2 -> ~/Developer/sources/gitlab/group/repo2
#   ~/old-repos/repo3 -> ~/Developer/sources/default/org/repo3

# Actual migration (copy)
sgw migrate ~/old-repos

# Or move instead of copy
sgw migrate ~/old-repos --move
```

**Test Case**:
- **Given**: Old repositories in `~/old-repos` with various origins
- **When**: `sgw migrate ~/old-repos --dry-run`
- **Then**: List of repositories that would be migrated with old and new paths

**Test Case**:
- **Given**: Old repositories
- **When**: `sgw migrate ~/old-repos`
- **Then**: Repositories copied to new locations based on current config

## Template Function Examples

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
# Worktree name: "ui-work"

worktrees: ~/worktrees/branch()
# Evaluates to: ~/worktrees/feature/new-ui

worktrees: ~/worktrees/norm_branch()
# Evaluates to: ~/worktrees/feature-new-ui

worktrees: ~/worktrees/norm_branch("_")
# Evaluates to: ~/worktrees/feature_new_ui

worktrees: ~/worktrees/prefix_worktree("-")
# If worktree has name: ~/worktrees/-ui-work
# If no name: ~/worktrees/

worktrees: ~/worktrees/norm_prefix_branch()
# If worktree has name: ~/worktrees/ui-work-feature-new-ui
# If no name: ~/worktrees/feature-new-ui
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
sgw clone https://github.com/user/repo.git

# Expected output (stderr):
# Error: Invalid YAML in config file ~/.config/sgw/config.yml
# Line 5: unexpected character
```

### Invalid URI

```bash
# Invalid git URI
sgw clone not-a-uri

# Expected output (stderr):
# Error: Invalid repository URI: not-a-uri
```

### Branch Not Found

```bash
# Branch doesn't exist
cd ~/Developer/sources/github/user/repo
sgw add nonexistent-branch

# Expected output (stderr):
# Error: Branch 'nonexistent-branch' not found in repository
```

### Worktree Already Exists

```bash
# Worktree for branch already exists
cd ~/Developer/sources/github/user/repo
sgw add feature-branch
sgw add feature-branch  # Again

# Expected output (stderr):
# Error: Worktree for branch 'feature-branch' already exists at <path>
```

## Integration Test Scenarios

### End-to-End: Clone to Worktree

```bash
# 1. Clone repository
sgw clone https://github.com/user/repo.git
# → ~/Developer/sources/github/user/repo

# 2. Add worktree
cd ~/Developer/sources/github/user/repo
sgw add feature-branch
# → ~/Developer/worktrees/github/user/repo/feature-branch

# 3. Work in worktree
cd ~/Developer/worktrees/github/user/repo/feature-branch
# ... make changes, commit ...

# 4. Update source
sgw pull
# Updates source repository

# 5. Remove worktree when done
cd ~/Developer/sources/github/user/repo
sgw remove feature-branch
# Worktree removed
```

### Multiple Worktrees

```bash
cd ~/Developer/sources/github/user/repo

# Create multiple worktrees
sgw add feature-1
sgw add feature-2
sgw add feature-3

# List worktrees
git worktree list

# Remove specific worktree
sgw remove feature-2
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
# Solution: Run sgw init config
sgw init config
```

### Template Evaluation Error

```bash
# Error: Template evaluation failed: Function 'unknown_func' not defined
# Solution: Check config file for typos in function names
# Valid functions: path, branch, norm_branch, worktree, prefix_worktree, norm_prefix_branch
```

### Git Command Failures

```bash
# Error: git clone failed: repository not found
# Solution: Verify URI is correct and accessible
# Check: git clone <uri> works manually
```
