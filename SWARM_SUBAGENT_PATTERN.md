# Subagent-Based Anti-Drift Pattern

## Overview

This pattern adapts the swarm/ supervisor architecture to work with Hermes Agent's subagent system, avoiding the need for a running LLM instance.

## Architecture

```
┌─────────────────────────────────────────────────┐
│           ARCHITECT (You + Me)                  │
│  • Define task with STRICT constraints          │
│  • Set scope (files/folders)                    │
│  • Define success criteria                      │
├─────────────────────────────────────────────────┤
│                                                 │
│  STEP 1: ARCHITECT                              │
│  • We (You + Me) collaborate on task definition │
│  • Write anti-drift constraints in context      │
│                                                 │
│  STEP 2: CODE WRITER (Subagent)                 │
│  • Spawn with delegate_task                     │
│  • Pass constraints in 'context' field          │
│  • Subagent outputs ONLY unified git diff       │
│  • No markdown, no explanations                 │
│                                                 │
│  STEP 3: REVIEWER (You + Me)                    │
│  • Review the diff before accepting             │
│  • Reject if violates constraints               │
│  • Loop back to Code Writer if needed           │
└─────────────────────────────────────────────────┘
```

## Implementation

### Example: Fix Test Warning

**ARCHITECT (You + Me):**
```markdown
TASK: Remove @pytest.mark.serial markers causing warnings

STRICT CONSTRAINTS:
1. ONLY modify: tests/unit/scheduler/test_scheduler_jobs.py
2. DO NOT add new tests
3. DO NOT modify other files
4. Remove ONLY @pytest.mark.serial decorators
5. Keep all test logic exactly the same

SCOPE:
- Only the 5 test methods with @pytest.mark.serial
- Nothing else
```

**SUBAGENT CONTEXT:**
```markdown
You are a CODE WRITER for kurs-bot. Your ONLY job is to implement the task above.

ANTI-DRIFT RULES:
• Output ONLY a unified git diff
• DO NOT write full files
• DO NOT touch files outside tests/unit/scheduler/
• DO NOT add extra functions or tests
• DO NOT modify imports
• DO NOT change test logic
• DO NOT use markdown, just plain diff

If you violate any rule, the REVIEWER will reject you.
```

### Workflow

1. **Define Task** (You + Me)
   - Clear requirements
   - Explicit constraints
   - File scope

2. **Spawn Subagent**
   ```python
   delegate_task(
       goal="Implement the task above with STRICT adherence to constraints",
       context="Your anti-drift rules here...",
       toolsets=["terminal", "file"]
   )
   ```

3. **Review Output**
   - Check diff is minimal
   - Verify no violations
   - Approve or reject

4. **Loop if Needed**
   - If rejected, send back specific violations
   - Subagent retrials until approved

## Benefits Over swarm/

✅ **No LLM dependency** - works with subagents
✅ **Faster iteration** - no graph overhead
✅ **More explicit** - constraints in text, not prompts
✅ **Easier debugging** - human-in-the-loop
✅ **Cross-platform** - works everywhere

## Template Usage

**For each task:**
1. Define task with constraints (You + Me)
2. Spawn subagent with delegate_task
3. Review output
4. Apply if approved

## Example Commands

```bash
# Define task
TASK: "Fix X with constraints A, B, C"

# Spawn subagent
delegate_task(
    goal="Implement task above",
    context="[Anti-drift rules here]",
    toolsets=["terminal", "file"]
)

# Review output
# If good: apply changes
# If bad: send rejection with specific issues
```

## Next Steps

1. Test this pattern on a small task
2. Refine the constraint language
3. Document common anti-drift rules
4. Integrate into team workflow
