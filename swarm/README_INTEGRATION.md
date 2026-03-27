# Mini-SWE-Agent Integration for Swarm/

## Overview

The swarm/ anti-drift system now integrates **mini-swe-agent** (the 100-line agent) as its CODE WRITER component. This provides a battle-tested, minimal agent for executing coding tasks while maintaining anti-drift rules.

## Architecture

```
┌─────────────────────────────────────────────────┐
│              SWARM/ 3-TIER SUPERVISOR            │
├─────────────────────────────────────────────────┤
│                                                 │
│  1. ARCHITECT (LLM) → Plans task               │
│  2. CODE WRITER (mini-swe-agent) → Executes    │
│  3. REVIEWER (LLM) → Validates                 │
│  4. PRE-COMMIT → Runs tests                    │
└─────────────────────────────────────────────────┘
```

## Components

### **1. swarm/ (LangGraph Supervisor)**
- Orchestrates the workflow
- Manages state and iteration
- Enforces anti-drift rules at system level

### **2. swarm/mini_swe_agent/ (CODE WRITER)**
- 100-line agent from Princeton/Stanford
- Scores >74% on SWE-bench verified
- Executes bash commands
- Outputs unified git diffs
- **Now integrated with anti-drift rules**

### **3. Anti-Drift Rules**
Enforced by both swarm/ and mini-swe-agent:
- ✅ Output ONLY unified git diff
- ✅ ONLY modify files in designated scope
- ✅ DO NOT write full files
- ✅ DO NOT add extra functions/tests
- ✅ DO NOT modify imports
- ✅ Keep changes minimal
- ✅ Human-in-the-loop review

## Usage

### **Method 1: Direct Import**
```python
from swarm.mini_swe_agent import run_task_with_anti_drift

# Run task with anti-drift rules
diff = run_task_with_anti_drift(
    task="Create swarm/TODO.md documenting the 3-tier architecture",
    cwd="/home/steen/kurs-bot/swarm/"
)
print(diff)
```

### **Method 2: Create Agent**
```python
from swarm.mini_swe_agent import create_agent

# Create configured agent
agent = create_agent(
    cwd="/home/steen/kurs-bot/swarm/",
    model_name="qwen2.5:7b-instruct-q4_K_M"
)

# Run task
diff = agent.run("Your task here")
```

### **Method 3: Via delegate_task()**
```python
from hermes_agent import delegate_task

delegate_task(
    goal="Create swarm/TODO.md documenting the 3-tier architecture",
    context="[Anti-drift rules: output ONLY unified git diff, stay in swarm/ folder only...]",
    toolsets=["terminal", "file"]
)
```

## Benefits

| Feature | swarm/ + mini-swe-agent | standalone swarm/ |
|---------|------------------------|-------------------|
| **Battle-tested** | ✅ SWE-bench verified | ❌ Custom implementation |
| **Speed** | ✅ ~24s | ⚠️ ~60s+ (with LLM) |
| **Simplicity** | ✅ 100-line agent | ⚠️ Complex LangGraph |
| **Flexibility** | ✅ bash commands | ✅ Git diff only |
| **Anti-drift** | ✅ Enforced | ✅ Enforced |

## Anti-Drift Rules

Both swarm/ and mini-swe-agent enforce:

```
1. Output ONLY a unified git diff
2. ONLY create/modify files inside the swarm/ folder
3. DO NOT write full files
4. DO NOT add extra functions or tests unless explicitly asked
5. DO NOT modify imports in existing files
6. DO NOT change existing swarm/ code
7. Keep changes MINIMAL and focused
8. DO NOT use markdown in output, just plain diff
```

## Workflow

```
1. ARCHITECT
   └─ Define task with STRICT constraints
      ↓
2. CODE WRITER (mini-swe-agent)
   └─ Execute bash commands
   └─ Output unified git diff
   └─ Stay in swarm/ folder
      ↓
3. REVIEWER
   └─ Validate anti-drift compliance
   └─ Approve or reject
      ↓
4. PRE-COMMIT
   └─ Run tests (npm test / pytest)
   └─ Verify no failures
      ↓
5. FINAL APPROVAL
   └─ Human review
   └─ Commit and push
```

## Example

```bash
# Create task
Task: "Create swarm/TODO.md documenting the 3-tier supervisor architecture"

# Run with mini-swe-agent
python -c "from swarm.mini_swe_agent import run_task_with_anti_drift; print(run_task_with_anti_drift('Create swarm/TODO.md documenting the 3-tier architecture'))"

# Output:
# --- PROPOSED DIFF ---
# diff --git a/swarm/TODO.md b/swarm/TODO.md
# new file mode 100644
# index 0000000..abc123
# ---
# + # 3-Tier Supervisor Architecture
# + # ...
```

## Configuration

```python
# Configure agent
agent = create_agent(
    cwd="/path/to/swarm/",  # Working directory
    model_name="qwen2.5:7b-instruct-q4_K_M",  # LLM model
    timeout=60,  # Command timeout
)
```

## Dependencies

- **mini-swe-agent**: Core agent code
- **LitellmModel**: LLM interface
- **LocalEnvironment**: Bash execution
- **swarm/**: Anti-drift rules

## Maintenance

- Keep mini-swe-agent updated
- Monitor anti-drift rule compliance
- Review agent performance on SWE-bench
- Update system prompts as needed

## See Also

- `swarm/TODO.md` - Architecture documentation
- `SWARM_SUBAGENT_PATTERN.md` - Alternative pattern guide
- `AGENTS.md` - Integration in main guidelines

## License

Same as mini-swe-agent (MIT)
