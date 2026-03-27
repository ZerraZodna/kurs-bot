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

### Example Workflow

```
Goal: Update a function
  ↓
Architect: "Create TODO.md documenting the architecture"
  ↓
Code Writer: "Create swarm/TODO.md with required content"
  ↓
Reviewer: "Verify file exists and content matches specification"
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

## Benefits and Workflow

### Benefits

1. **Clear Boundaries**: Each tier knows its responsibility
2. **Anti-Drift Protection**: Rules prevent scope creep
3. **Minimal Changes**: Targeted edits reduce risk
4. **Quality Assurance**: Reviewer validates compliance
5. **Documentation**: Architecture is self-documenting

### Workflow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Architect  │────▶│  Code Writer│────▶│  Reviewer   │
└─────────────┘     └─────────────┘     └─────────────┘
      │                    │                    │
      │                    │                    │
      ▼                    ▼                    ▼
  Plan Task             Execute           Validate
  (High-Level)         (Anti-Drift)      (Compliance)
```

### Key Principles

- **Separation of Concerns**: Each tier handles different aspects
- **Controlled Communication**: Messages flow in one direction
- **Rule Enforcement**: Anti-drift rules are strict and mandatory
- **Validation First**: Reviewer checks before acceptance
- **Documentation**: Architecture is documented for clarity
