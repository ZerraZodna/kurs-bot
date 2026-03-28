# SWARM SYSTEM DOCUMENTATION

## Understanding of the Swarm System
Based on recent analysis and discussions

## Human-in-the-Loop Automation Workflow

This system implements a 9-step human-centered automation workflow that uses the swarm (Architect → Code Writer → Reviewer → Pre-Commit) as the core automated component within a larger human-in-the-loop process.

### The 9-Step Process
```
1. HUMAN
   └─ Ask agent to implement an idea
      ↓
2. HERMES AGENT
   └─ Write idea as an AI prompt for the swarm and shows it to HUMAN
      ↓
3. HUMAN
   └─ Reads and approves prompts. If not, back to 2. or Cancel
      ↓
4. ARCHITECT in swarm  ← AI NODE
   └─ Define task with STRICT constraints
      ↓
5. CODE WRITER (mini-swe-agent)  ← AI NODE
   └─ Execute bash commands
   └─ Output unified git diff
   └─ Stay in swarm/ folder
      ↓
6. REVIEWER  ← AI NODE (anti-drift validation)
   └─ Validate anti-drift compliance
   └─ Approve or reject
      ↓
7. PRE-COMMIT  ← Automated tests
   └─ Run tests (pytest)
   └─ Verify no failures - if failures back to 5.
      ↓
8. TESTING & VALIDATION
   └─ Execute unit tests AND integration tests
   └─ RUN THE APPLICATION in live environment
   └─ Verify ALL runtime dependencies work properly
   └─ Confirm no runtime errors exist
   └─ Execute end-to-end scenarios
      ↓
9. FINAL APPROVAL
   └─ HERMES AGENT evaluates result from Swarm + awaits Telegram approval
   └─ Human final review and approval via TELEGRAM command
   └─ Git commit and push if approved by Telegram command
```
```

### Core Components Within the Workflow

**Swarm Automation Module:**
- **ARCHITECT:** Plans tasks with strict constraints
   - Define the high-level goal
   - Architect breaks it into sub-tasks
   - Code Writer receives the first sub-task

- **CODE WRITER:** Uses mini-swe-agent to execute coding tasks
   - Execute the assigned sub-task
   - Follow strict anti-drift rules
   - Keep changes minimal and focused

- **REVIEWER:** Validates anti-drift compliance and code quality
   - Review the changes
   - Ensure anti-drift compliance
   - Approve or request corrections

- **PRE-COMMIT:** Runs tests and validation
   - Run `npm test` on the changes -> fail -> back to CODE WRITER to fix as new task
   - Run `npm lint` on the changes -> fail -> back to CODE WRITER to fix as new task
   - Verify no test failures introduced
   - Ensure type checking passes
   - Only approved changes to be committed

**Human Interface Layer:**
- **HERMES AGENT:** Translates human requests to swarm prompts and presents them for approval
   - Run `npm test` on the ALL code -> fail -> back to CODE WRITER to fix as new task
   - Run `npm lint` on the ALL code -> fail -> back to CODE WRITER to fix as new task
- **HUMAN:** Reviews, approves, and finalizes the automation cycle

### Current Implementation vs Intent
**Currently Implemented:**
- Internal workflow from steps 4-7 (Architect → Code Writer → Reviewer → Pre-Commit) is automated
- Anti-drift rules enforced programmatically
- Integration with mini-swe-agent as the code execution layer

**Intended Design (Pending Implementation):**
- All 9 steps of the human-in-the-loop workflow completed
- Proper human decision gates (steps 2-3 and 8-9) to prevent unauthorized changes
- Complete loop where each execution starts with human input and ends with human verification

### Current Gap
The most vital missing pieces are the human-interface components that surround the automated swarm workflow - specifically steps 1-3 for input and 8-9 for output evaluation and final approval. The system currently operates as an internal automation without human involvement at the critical entry and exit points.

### Integration Context
This design ensures that humans remain in control of the automation process, using Hermes agent as the intermediary between human requests and the swarm's automated execution capabilities.

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
