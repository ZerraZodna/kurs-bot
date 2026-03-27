# 3-Tier Supervisor Architecture Documentation

## Architecture Overview

This system implements a 3-tier supervisor architecture designed for anti-drift coding tasks:

1. **Architect**: High-level planning and task decomposition
2. **Code Writer**: Implements the actual coding tasks
3. **Reviewer**: Validates and ensures anti-drift compliance

Each tier has specific responsibilities and communicates in a controlled manner to prevent scope creep and maintain task boundaries.

## Step-by-Step Usage Guide

### Starting a Task

1. **Initiate with Architect**:
   - Define the high-level goal
   - Architect breaks it into sub-tasks
   - Code Writer receives the first sub-task

2. **Code Writer Execution**:
   - Execute the assigned sub-task
   - Follow strict anti-drift rules
   - Keep changes minimal and focused

3. **Reviewer Validation**:
   - Review the changes
   - Ensure anti-drift compliance
   - Approve or request corrections

4. **Pre-Commit Runner** (NEW):
   - Run `npm test` on the changes
   - Verify no test failures introduced
   - Ensure type checking passes
   - Only approved changes to be committed

### Example Workflow

```
Goal: Update a function
  ↓
Architect: "Create TODO.md documenting the architecture"
  ↓
Code Writer: "Create swarm/TODO.md with required content"
  ↓
Reviewer: "Verify file exists and content matches specification"
  ↓
Pre-Commit: "Run npm test to verify no failures introduced"
  ↓
You: Final approval to commit
```

## Anti-Drift Rules

### General Rules

- Output ONLY a unified git diff
- DO NOT write full files (use targeted edits)
- DO NOT touch files outside the designated scope
- DO NOT add extra files or tests
- DO NOT use markdown in output, just plain diff
- Keep changes minimal and focused

### Code Writer Specific Rules

- ONLY create/modify the assigned files
- DO NOT modify existing swarm/ files
- DO NOT add extra functions or tests
- DO NOT modify imports in existing files
- DO NOT change existing swarm/ code
- DO NOT use markdown, just plain diff

### Reviewer Checklist

- File exists at the correct path
- Changes match the specification
- No extra files created
- No unrelated modifications
- Anti-drift rules followed

### Pre-Commit Checklist (Step 4)

- Run `npm test` or `pytest` on changes
- Verify no new test failures introduced
- Check type checking passes (if configured)
- Ensure pre-commit hooks pass
- Only approved changes to be committed

## Example Tasks

### Task 1: Create Documentation File

**Goal**: Create swarm/TODO.md documenting the 3-tier architecture

**Architect**: "Create swarm/TODO.md documenting the 3-tier supervisor architecture (Architect → Code Writer → Reviewer) and how to use it for anti-drift coding tasks"

**Code Writer**: "Create swarm/TODO.md with content including: 1. Architecture overview, 2. Step-by-step usage guide, 3. Anti-drift rules, 4. Example tasks, 5. Benefits and workflow"

**Reviewer**: "Verify swarm/TODO.md exists, contains all required sections, and follows anti-drift rules"

### Task 2: Targeted File Edit

**Goal**: Add a configuration option to swarm/config.py

**Architect**: "Add max_retries=3 to swarm/config.py"

**Code Writer**: "Use patch to replace existing retry config with max_retries=3"

**Reviewer**: "Verify only the retry config changed, no other modifications"

### Task 3: Pre-Commit Runner Verification

**Goal**: Test changes before final commit

**Architect**: "Add a new validation function to swarm/utils.py and run tests before committing"

**Code Writer**: "Create a new function validate_input() in swarm/utils.py using patch to add minimal changes"

**Pre-Commit Runner**: "Run npm test or pytest on specific changes to verify no test failures"

**Command**: "npm test -- --testPathPattern=utils.test.js"

**Pre-Commit Checklist Verification**:
- Run `npm test` to verify no test failures introduced
- Check type checking passes with `npm run lint`
- Verify pre-commit hooks pass
- Ensure no breaking changes to existing functionality

**Expected Output**:
```
PASS  utils.test.js
  validate_input
    ✓ should return true for valid input
    ✓ should return false for invalid input
    ✓ should handle edge cases

Test Suites: 1 passed, 1 total
Tests:       3 passed, 3 total
Duration:    0.5s

Pre-commit hooks: PASSED
Type checking: PASSED
```

**Reviewer**: "Verify tests pass, type checking passes, and only the intended function was added"

## Benefits and Workflow

### Benefits

1. **Clear Boundaries**: Each tier knows its responsibility
2. **Anti-Drift Protection**: Rules prevent scope creep
3. **Minimal Changes**: Targeted edits reduce risk
4. **Quality Assurance**: Reviewer validates compliance
5. **Safety Net**: Pre-Commit step catches test failures before merge
6. **Documentation**: Architecture is self-documenting

### Workflow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Architect  │───▶│  Code Writer│────▶│  Reviewer   │────▶│ Pre-Commit  │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
      │                    │                    │                    │
      │                    │                    │                    │
      ▼                    ▼                    ▼                    ▼
  Plan Task             Execute           Validate           Run Tests
  (High-Level)         (Anti-Drift)      (Compliance)      (Safety Net)
```

### Key Principles

- **Separation of Concerns**: Each tier handles different aspects
- **Controlled Communication**: Messages flow in one direction
- **Rule Enforcement**: Anti-drift rules are strict and mandatory
- **Validation First**: Reviewer checks before acceptance
- **Safety First**: Pre-Commit step runs tests before final approval
- **Documentation**: Architecture is documented for clarity
