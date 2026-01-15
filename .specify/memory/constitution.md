<!--
Sync Impact Report:
Version: 0.0.0 → 1.0.0 (Initial constitution)
Modified principles: N/A (new)
Added sections: Core Principles (5 principles), Technology Stack, Development Workflow
Removed sections: N/A
Templates requiring updates:
  ✅ plan-template.md - Constitution Check section aligns with TDD and minimalism principles
  ✅ spec-template.md - No changes needed (already supports TDD via user scenarios)
  ✅ tasks-template.md - Already includes TDD workflow and test-first approach
Follow-up TODOs: None
-->

# Git Worktree Wrapper Constitution

## Core Principles

### I. Test-Driven Development (TDD) (NON-NEGOTIABLE)
All features MUST follow strict TDD workflow: Write tests first → User approves tests → Tests fail → Implement to pass → Refactor. Red-Green-Refactor cycle is mandatory. No implementation code is written without a failing test first. Tests serve as executable specifications and documentation.

### II. Minimalism & Dependency Management
Code MUST be minimalistic and focused. External dependencies MUST be kept to an absolute minimum. Every dependency addition requires justification. Prefer standard library solutions over third-party packages. When external dependencies are necessary, they MUST be minimal, well-maintained, and add significant value. Code complexity must be justified; simpler solutions are preferred.

### III. Single Command Interface
The application MUST expose a single command-line entry point with consistent parameter patterns across all usage scenarios. Command structure MUST be intuitive and follow predictable patterns. All functionality MUST be accessible through this unified interface. Parameters MUST be consistent in naming, positioning, and behavior across different subcommands or modes.

### IV. Python 3.11+ & uv Requirements
The project MUST use Python 3.11 or higher. Dependency management MUST use `uv` exclusively. All project setup, installation, and dependency resolution MUST be performed through `uv`. No alternative package managers (pip, poetry, etc.) are permitted. Project configuration MUST be compatible with `uv`'s standards.

### V. Git Worktree Focus
The application MUST be a wrapper around git worktree functionality, providing additional convenience functions while maintaining compatibility with standard git worktree behavior. All features MUST enhance or extend git worktree capabilities without breaking existing git workflows. The wrapper MUST not interfere with native git commands or worktree operations.

## Technology Stack

**Language**: Python 3.11+  
**Dependency Manager**: uv (exclusive)  
**Project Type**: Console application (CLI)  
**Target Platform**: Unix-like systems (Linux, macOS) with git installed  
**Testing Framework**: pytest (standard for Python TDD)  
**Code Quality**: Minimal external tooling; prefer built-in Python tooling where possible

## Development Workflow

**TDD Enforcement**: All development MUST follow TDD cycle. Tests are written first, reviewed/approved, then implementation follows.  
**Code Review**: All changes MUST pass tests before review. Constitution compliance MUST be verified in reviews.  
**Dependency Review**: Every new external dependency MUST be justified and approved. Minimalism principle MUST be upheld.  
**Command Interface Review**: All new commands or parameters MUST maintain consistency with existing interface patterns.

## Governance

This constitution supersedes all other development practices and guidelines. All code, tests, and documentation MUST comply with these principles. Amendments to this constitution require:

1. Documentation of the rationale for change
2. Impact assessment on existing codebase
3. Version increment following semantic versioning (MAJOR.MINOR.PATCH)
4. Update of dependent templates and documentation

All PRs and code reviews MUST verify compliance with constitution principles. Complexity and dependency additions MUST be justified. Violations of TDD principle are non-negotiable and MUST be rejected.

**Version**: 1.0.0 | **Ratified**: 2025-01-27 | **Last Amended**: 2025-01-27
