# Tasks: Git Worktree Wrapper (gww)

**Input**: Design documents from `/specs/001-git-worktree-wrapper/`
**Prerequisites**: spec.md ✅, plan.md ✅, data-model.md ✅, contracts/cli-commands.md ✅, research.md ✅, quickstart.md ✅

**Tests**: TDD is mandatory per constitution - all tests must be written first and fail before implementation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root (per plan.md structure)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create project structure per implementation plan in plan.md
- [X] T002 Initialize Python 3.11+ project with uv and pyproject.toml
- [X] T003 [P] Add dependencies: simpleeval, ruamel.yaml, pytest to pyproject.toml
- [X] T004 [P] Configure pytest in pyproject.toml with test discovery patterns
- [X] T005 [P] Setup type checking configuration (mypy or pyright) in pyproject.toml
- [X] T006 [P] Create README.md with project overview and installation instructions

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T007 [P] Implement XDG config directory handling in src/gww/utils/xdg.py
- [X] T008 [P] Implement StrictSimpleEval subclass in src/gww/template/evaluator.py with type checking
- [X] T009 [P] Implement template function registry in src/gww/template/functions.py (path, branch, norm_branch)
- [X] T010 [P] Implement template preprocessing (regex-based function call extraction, escaped parentheses handling) in src/gww/template/evaluator.py
- [X] T011 [P] Implement config loader with ruamel.yaml in src/gww/config/loader.py
- [X] T012 [P] Implement config validator in src/gww/config/validator.py
- [X] T013 [P] Implement template resolver in src/gww/config/resolver.py
- [X] T014 [P] Implement git repository detection and operations in src/gww/git/repository.py
- [X] T015 [P] Implement git worktree operations wrapper in src/gww/git/worktree.py
- [X] T016 [P] Implement git branch operations in src/gww/git/branch.py
- [X] T017 [P] Implement URI parsing (protocol, host, port, path segments) in src/gww/utils/uri.py
- [X] T018 [P] Implement project action matcher (predicate evaluation) in src/gww/actions/matcher.py
- [X] T019 [P] Implement project action executor (abs_copy, rel_copy, command) in src/gww/actions/executor.py
- [X] T020 [P] Implement shell completion generation utilities in src/gww/utils/shell.py
- [X] T021 Create base CLI argument parser structure in src/gww/cli/main.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Clone Repositories (Priority: P1) 🎯 MVP

**Goal**: Users can clone repositories to configurable source locations based on URI predicates, with project-specific actions executed after clone.

**Independent Test**: Run `gww clone https://github.com/user/repo.git` from a clean state and verify repository is cloned to expected location based on config, and source_actions are executed if project predicate matches.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T022 [P] [US1] Unit test for URI parsing in tests/unit/test_uri_parsing.py
- [X] T023 [P] [US1] Unit test for source rule predicate matching in tests/unit/test_config_resolver.py
- [X] T024 [P] [US1] Unit test for template resolution with URI context in tests/unit/test_config_resolver.py
- [X] T025 [P] [US1] Unit test for project action matching and execution in tests/unit/test_actions_matcher.py
- [X] T026 [P] [US1] Integration test for clone command end-to-end in tests/integration/test_clone_flow.py

### Implementation for User Story 1

- [X] T027 [US1] Implement clone command in src/gww/cli/commands/clone.py
- [X] T028 [US1] Integrate clone command into main CLI parser in src/gww/cli/main.py
- [X] T029 [US1] Add error handling for invalid URIs, clone failures, and action failures in src/gww/cli/commands/clone.py
- [X] T030 [US1] Add output formatting (print clone path to stdout, errors to stderr) in src/gww/cli/commands/clone.py

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently. Users can clone repositories with `gww clone <uri>`.

---

## Phase 4: User Story 2 - Add Worktrees (Priority: P1) 🎯 MVP

**Goal**: Users can add worktrees for branches with configurable paths and project-specific actions executed after worktree creation.

**Independent Test**: From a cloned repository, run `gww add feature-branch` and verify worktree is created at expected location based on config, branch is checked out, and worktree_actions are executed if project predicate matches.

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T031 [P] [US2] Unit test for worktree template resolution with branch context in tests/unit/test_config_resolver.py
- [X] T032 [P] [US2] Unit test for branch existence checking and creation in tests/unit/test_git_branch.py
- [X] T033 [P] [US2] Unit test for source repository detection from worktree in tests/unit/test_git_repository.py
- [X] T034 [P] [US2] Integration test for add command end-to-end in tests/integration/test_worktree_management.py

### Implementation for User Story 2

- [X] T035 [US2] Implement add command in src/gww/cli/commands/add.py
- [X] T036 [US2] Add --create-branch option handling in src/gww/cli/commands/add.py
- [X] T037 [US2] Integrate add command into main CLI parser in src/gww/cli/main.py
- [X] T038 [US2] Add error handling for branch not found, worktree add failures, and action failures in src/gww/cli/commands/add.py
- [X] T039 [US2] Add output formatting (print worktree path to stdout, errors to stderr) in src/gww/cli/commands/add.py

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently. Users can clone repositories and add worktrees.

---

## Phase 5: User Story 3 - Remove Worktrees (Priority: P2)

**Goal**: Users can remove worktrees by branch name or path, with safety checks for dirty worktrees and force option.

**Independent Test**: From a repository with a worktree, run `gww remove feature-branch` and verify worktree is removed. Test dirty worktree rejection and --force override.

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T040 [P] [US3] Unit test for worktree clean/dirty detection in tests/unit/test_git_worktree.py
- [X] T041 [P] [US3] Unit test for worktree lookup by branch name or path in tests/unit/test_git_worktree.py
- [X] T042 [P] [US3] Integration test for remove command end-to-end in tests/integration/test_worktree_management.py

### Implementation for User Story 3

- [X] T043 [US3] Implement remove command in src/gww/cli/commands/remove.py
- [X] T044 [US3] Add --force option handling in src/gww/cli/commands/remove.py
- [X] T045 [US3] Integrate remove command into main CLI parser in src/gww/cli/main.py
- [X] T046 [US3] Add error handling for worktree not found, dirty worktree rejection, and removal failures in src/gww/cli/commands/remove.py
- [X] T047 [US3] Add output formatting (print removal confirmation to stdout, errors to stderr) in src/gww/cli/commands/remove.py

**Checkpoint**: At this point, User Stories 1, 2, AND 3 should all work independently. Users can clone, add, and remove worktrees.

---

## Phase 6: User Story 4 - Pull Updates (Priority: P2)

**Goal**: Users can update source repositories by pulling from remote, with safety checks for branch (main/master) and clean state.

**Independent Test**: From a source repository on main branch, run `gww pull` and verify git pull is executed. Test rejection when not on main/master or when dirty.

### Tests for User Story 4

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T048 [P] [US4] Unit test for source repository branch detection in tests/unit/test_git_repository.py
- [X] T049 [P] [US4] Integration test for pull command end-to-end in tests/integration/test_worktree_management.py

### Implementation for User Story 4

- [X] T050 [US4] Implement pull command in src/gww/cli/commands/pull.py
- [X] T051 [US4] Integrate pull command into main CLI parser in src/gww/cli/main.py
- [X] T052 [US4] Add error handling for not on main/master, dirty repository, and pull failures in src/gww/cli/commands/pull.py
- [X] T053 [US4] Add output formatting (print update confirmation to stdout, errors to stderr) in src/gww/cli/commands/pull.py

**Checkpoint**: At this point, User Stories 1-4 should all work independently. Users can clone, add, remove worktrees, and update source repositories.

---

## Phase 7: User Story 5 - Migrate Repositories (Priority: P3)

**Goal**: Users can migrate existing repositories from old locations to new locations based on current configuration.

**Independent Test**: Run `gww migrate ~/old-repos --dry-run` and verify migration plan is shown. Run without --dry-run and verify repositories are copied/moved to expected locations.

### Tests for User Story 5

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T054 [P] [US5] Unit test for repository scanning and URI extraction in tests/unit/test_git_repository.py
- [X] T055 [P] [US5] Unit test for migration path calculation in tests/unit/test_config_resolver.py
- [X] T056 [P] [US5] Integration test for migrate command end-to-end in tests/integration/test_migration.py

### Implementation for User Story 5

- [X] T057 [US5] Implement migrate command in src/gww/cli/commands/migrate.py
- [X] T058 [US5] Add --dry-run and --move option handling in src/gww/cli/commands/migrate.py
- [X] T059 [US5] Integrate migrate command into main CLI parser in src/gww/cli/main.py
- [X] T060 [US5] Add error handling for invalid paths, migration failures, and worktree updates in src/gww/cli/commands/migrate.py
- [X] T061 [US5] Add output formatting (print migration summary to stdout, errors to stderr) in src/gww/cli/commands/migrate.py

**Checkpoint**: At this point, User Stories 1-5 should all work independently. Users can clone, add, remove worktrees, update sources, and migrate repositories.

---

## Phase 8: User Story 6 - Initialize Configuration (Priority: P3)

**Goal**: Users can create a default configuration file with examples and documentation.

**Independent Test**: Run `gww init config` and verify config file is created at expected location with default templates and documentation. Test rejection when config already exists.

### Tests for User Story 6

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T062 [P] [US6] Unit test for default config generation in tests/unit/test_config_loader.py
- [X] T063 [P] [US6] Integration test for init config command end-to-end in tests/integration/test_cli_commands.py

### Implementation for User Story 6

- [X] T064 [US6] Implement init config command in src/gww/cli/commands/init.py
- [X] T065 [US6] Create default config template with examples and documentation in src/gww/cli/commands/init.py
- [X] T066 [US6] Integrate init config command into main CLI parser in src/gww/cli/main.py
- [X] T067 [US6] Add error handling for existing config file and write failures in src/gww/cli/commands/init.py
- [X] T068 [US6] Add output formatting (print config file path to stdout, errors to stderr) in src/gww/cli/commands/init.py

**Checkpoint**: At this point, User Stories 1-6 should all work independently. Users can initialize configuration files.

---

## Phase 9: User Story 7 - Initialize Shell Completion (Priority: P3)

**Goal**: Users can generate and install shell autocompletion scripts for bash, zsh, and fish.

**Independent Test**: Run `gww init shell bash` and verify completion script is generated and installed at expected location. Test completion for subcommands, options, and dynamic values (branches, worktrees).

### Tests for User Story 7

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T069 [P] [US7] Unit test for completion script generation in tests/unit/test_shell_completion.py
- [X] T070 [P] [US7] Integration test for init shell command end-to-end in tests/integration/test_cli_commands.py

### Implementation for User Story 7

- [X] T071 [US7] Implement init shell command in src/gww/cli/commands/init.py
- [X] T072 [US7] Add completion script generation using argparse methods in src/gww/cli/commands/init.py
- [X] T073 [US7] Add dynamic completion for branches and worktrees in src/gww/cli/main.py
- [X] T074 [US7] Integrate init shell command into main CLI parser in src/gww/cli/main.py
- [X] T075 [US7] Add error handling for invalid shell names and write failures in src/gww/cli/commands/init.py
- [X] T076 [US7] Add output formatting (print installation path and instructions to stdout, errors to stderr) in src/gww/cli/commands/init.py

**Checkpoint**: At this point, all user stories should work independently. Users can initialize shell completion.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T077 [P] Add comprehensive error messages with context throughout all commands
- [X] T078 [P] Add verbose/quiet output options to all commands in src/gww/cli/main.py
- [X] T079 [P] Add help text and documentation for all commands in src/gww/cli/main.py
- [ ] T080 [P] Performance optimization: cache config loading during command execution
- [ ] T081 [P] Add logging infrastructure for debugging in src/gww/utils/logging.py
- [ ] T082 [P] Code cleanup and refactoring: ensure all functions have type hints
- [ ] T083 [P] Update README.md with usage examples and quickstart guide
- [ ] T084 [P] Run quickstart.md validation: verify all test scenarios from quickstart.md work
- [ ] T085 [P] Add integration tests for complex scenarios (multiple worktrees, project actions, etc.) in tests/integration/
- [ ] T086 [P] Security review: validate all user inputs, sanitize paths, verify git command safety

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-9)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Phase 10)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1) - Clone**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P1) - Add Worktrees**: Can start after Foundational (Phase 2) - Depends on US1 for testing (needs cloned repo), but implementation is independent
- **User Story 3 (P2) - Remove Worktrees**: Can start after Foundational (Phase 2) - Depends on US2 for testing (needs worktrees), but implementation is independent
- **User Story 4 (P2) - Pull**: Can start after Foundational (Phase 2) - Depends on US1 for testing (needs cloned repo), but implementation is independent
- **User Story 5 (P3) - Migrate**: Can start after Foundational (Phase 2) - Independent, can test with mock repositories
- **User Story 6 (P3) - Init Config**: Can start after Foundational (Phase 2) - Independent, no dependencies
- **User Story 7 (P3) - Init Shell**: Can start after Foundational (Phase 2) - Depends on CLI parser being complete, but can be tested independently

### Within Each User Story

- Tests (TDD mandatory) MUST be written and FAIL before implementation
- Foundation components before command implementation
- Command implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, user stories can start in parallel (if team capacity allows)
- All tests for a user story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task T022: "Unit test for URI parsing in tests/unit/test_uri_parsing.py"
Task T023: "Unit test for source rule predicate matching in tests/unit/test_config_resolver.py"
Task T024: "Unit test for template resolution with URI context in tests/unit/test_config_resolver.py"
Task T025: "Unit test for project action matching and execution in tests/unit/test_actions_matcher.py"
Task T026: "Integration test for clone command end-to-end in tests/integration/test_clone_flow.py"
```

---

## Parallel Example: User Story 2

```bash
# Launch all tests for User Story 2 together:
Task T031: "Unit test for worktree template resolution with branch context in tests/unit/test_config_resolver.py"
Task T032: "Unit test for branch existence checking and creation in tests/unit/test_git_branch.py"
Task T033: "Unit test for source repository detection from worktree in tests/unit/test_git_repository.py"
Task T034: "Integration test for add command end-to-end in tests/integration/test_worktree_management.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1 & 2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Clone)
4. Complete Phase 4: User Story 2 (Add Worktrees)
5. **STOP and VALIDATE**: Test User Stories 1 & 2 independently
6. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (Partial MVP)
3. Add User Story 2 → Test independently → Deploy/Demo (Full MVP!)
4. Add User Story 3 → Test independently → Deploy/Demo
5. Add User Story 4 → Test independently → Deploy/Demo
6. Add User Stories 5-7 → Test independently → Deploy/Demo
7. Polish → Final release

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Clone)
   - Developer B: User Story 2 (Add Worktrees) - can start in parallel after US1 tests pass
   - Developer C: User Story 3 (Remove) - can start after US2
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- TDD is mandatory: verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
- All functions must have type hints per plan.md constraints
- Performance goals: command execution < 2s, config parsing < 100ms, template evaluation < 50ms

---

## Summary

- **Total Tasks**: 86
- **Tasks per User Story**:
  - US1 (Clone): 9 tasks (5 tests + 4 implementation)
  - US2 (Add Worktrees): 9 tasks (4 tests + 5 implementation)
  - US3 (Remove): 8 tasks (3 tests + 5 implementation)
  - US4 (Pull): 6 tasks (2 tests + 4 implementation)
  - US5 (Migrate): 8 tasks (3 tests + 5 implementation)
  - US6 (Init Config): 7 tasks (2 tests + 5 implementation)
  - US7 (Init Shell): 8 tasks (2 tests + 6 implementation)
- **Parallel Opportunities**: All foundational tasks, all test tasks within a story, user stories after foundational phase
- **Independent Test Criteria**: Each user story can be tested independently with appropriate setup
- **Suggested MVP Scope**: User Stories 1 & 2 (Clone and Add Worktrees) - core functionality
- **Format Validation**: ✅ All tasks follow checklist format (checkbox, ID, labels, file paths)
