# TODO: Swarm/ Mini-SWE-Agent Integration - Next Steps

## Overview
Mini-swe-agent is now integrated into swarm/ with extended workflow functions. This file tracks remaining work for testing, integration, and production deployment.

## Current Status
✅ Mini-swe-agent copied into `swarm/mini_swe_agent/`
✅ Extended workflow functions implemented:
  - `plan_task_with_tests()`
  - `create_code_with_tests()`
  - `run_pre_commit()`
  - `execute_extended_workflow()`
✅ Unit tests created: `swarm/mini_swe_agent/test_extended_workflow.py`
✅ Dependencies resolved in `.venv`

## Next Steps - Testing

### 1. Fix Test Execution Issues
**Problem**: Tests fail because no LLM server is running
**Action**: Set up a test LLM or mock responses

```bash
# Option A: Start local Qwen LLM
# Option B: Use Ollama with a model
# Option C: Mock the LLM for unit testing

# Add to test file:
@mock.patch('swarm.mini_swe_agent.LitellmModel.query')
def test_with_mocked_llm(mock_query):
    mock_query.return_value = {"content": "test diff"}
    # ... test logic
```

**Priority**: HIGH - Tests must pass before production deployment

### 2. Test Individual Functions
- [ ] `plan_task_with_tests()` - Verify task planning output
- [ ] `create_code_with_tests()` - Verify code + test generation
- [ ] `run_pre_commit()` - Verify test execution and failure loop
- [ ] `execute_extended_workflow()` - Verify full workflow coordination

### 3. Test Edge Cases
- [ ] Empty task string
- [ ] Very long task string
- [ ] Invalid task description
- [ ] File already exists
- [ ] File permissions issues
- [ ] Network errors during LLM calls
- [ ] LLM timeout
- [ ] Pre-commit with 0 retries

### 4. Test Integration
- [ ] Multi-task workflow (break down large tasks)
- [ ] Test creation for new functions
- [ ] Test modification for existing functions
- [ ] Pre-commit failure loop (3 retries)
- [ ] Anti-drift rule violations

## Next Steps - Integration

### 5. Integrate with Existing Swarm Workflow
**Current**: swarm/nodes.py uses LangGraph with LLM
**Goal**: Use mini-swe-agent as CODE WRITER node

```python
# Add to swarm/nodes.py
from swarm.mini_swe_agent import create_agent

def code_writer_node_with_mini_swe(state):
    """Use mini-swe-agent as CODE WRITER"""
    agent = create_agent()
    # ... implement
```

**Status**: NOT STARTED
**Priority**: HIGH

### 6. Add Pre-Commit to Swarm Workflow
**Current**: Pre-commit is manual step
**Goal**: Auto-run pre-commit after Code Writer

```python
# Add Pre-Commit node after Reviewer
def pre_commit_node(state):
    """Run pre-commit checks"""
    from swarm.mini_swe_agent import run_pre_commit
    result = run_pre_commit(state['current_task'])
    # Handle failure loop
```

**Status**: NOT STARTED
**Priority**: MEDIUM

### 7. Add Multi-Task Support
**Current**: Single task at a time
**Goal**: Break large tasks into subtasks

```python
# Update architect_node()
def architect_node_with_subtasks(state):
    """Break large tasks into subtasks"""
    # Use mini-swe-agent to plan subtasks
    # Execute each subtask
    # Return combined result
```

**Status**: NOT STARTED
**Priority**: MEDIUM

### 8. Add Test Creation Automation
**Current**: Tests must be explicitly requested
**Goal**: Auto-generate tests for new code

```python
# In create_code_with_tests()
def create_code_with_tests_auto(state):
    """Auto-generate tests for new functions"""
    # Analyze code changes
    # Generate test file
    # Add to changes
```

**Status**: NOT STARTED
**Priority**: HIGH

## Next Steps - Production Deployment

### 9. Add Configuration Options
```python
# Add to create_agent()
def create_agent(
    cwd="/home/steen/kurs-bot/swarm/",
    model_name="qwen2.5:7b-instruct-q4_K_M",
    base_url="http://localhost:8080/v1",
    max_retries=3,
    timeout=60
):
    """Create agent with configurable options"""
```

**Status**: PARTIAL - Some options exist, need more
**Priority**: LOW

### 10. Add Logging
```python
# Add logging to all functions
import logging
logger = logging.getLogger(__name__)

logger.info(f"Planning task: {task}")
logger.info(f"Code creation result: {result}")
logger.warning(f"Pre-commit failed, retry {retry}/3")
```

**Status**: NOT STARTED
**Priority**: LOW

### 11. Add Error Handling
```python
# Add try/except blocks
def plan_task_with_tests_safe(task):
    try:
        return plan_task_with_tests(task)
    except Exception as e:
        logger.error(f"Planning failed: {e}")
        raise
```

**Status**: NOT STARTED
**Priority**: MEDIUM

### 12. Add Performance Monitoring
- [ ] Track execution time per phase
- [ ] Track LLM call costs
- [ ] Track retry counts
- [ ] Track success/failure rates

**Status**: NOT STARTED
**Priority**: LOW

## Next Steps - Documentation

### 13. Update AGENTS.md
**Current**: Has basic description
**Goal**: Add detailed examples and troubleshooting

```markdown
## Swarm/ Mini-SWE-Agent Integration

### Usage Examples
```python
# Simple usage
from swarm.mini_swe_agent import run_task_with_anti_drift
diff = run_task_with_anti_drift("Task description")

# Extended workflow
from swarm.mini_swe_agent import execute_extended_workflow
result = execute_extended_workflow("Complex task")
```

### Troubleshooting
- **No LLM server**: Start Qwen or Ollama
- **Timeout**: Increase timeout parameter
- **Anti-drift violations**: Review anti-drift rules
- **Test failures**: Check pre-commit configuration
```

**Status**: PARTIAL
**Priority**: MEDIUM

### 14. Create Troubleshooting Guide
```markdown
# Swarm/ Mini-SWE-Agent Troubleshooting

## Common Issues

### LLM Connection Errors
**Symptom**: `Connection refused`
**Solution**: Start local LLM server

### Timeout Errors
**Symptom**: `Timeout after 60s`
**Solution**: Increase timeout parameter

### Anti-Drift Violations
**Symptom**: `REJECT from Reviewer`
**Solution**: Review anti-drift rules
```

**Status**: NOT STARTED
**Priority**: LOW

### 15. Add Release Notes
```markdown
# Swarm/ Mini-SWE-Agent Release Notes

## Version 0.2.0
- Extended workflow functions added
- Test creation automation
- Pre-commit failure loop
- Anti-drift rules enforcement
```

**Status**: NOT STARTED
**Priority**: LOW

## Next Steps - Future Enhancements

### 16. Add Custom Anti-Drift Rules
```python
# Allow custom rules per task
def create_agent(
    custom_rules=["rule1", "rule2"],
):
    pass
```

**Status**: NOT STARTED
**Priority**: LOW

### 17. Add Tool Integration
```python
# Integrate with other tools
- git operations (commit, push)
- file operations (read, write)
- terminal commands
```

**Status**: NOT STARTED
**Priority**: LOW

### 18. Add Docker/Sandbox Support
```python
# Allow running in sandbox
def create_agent(
    sandbox=True,
    sandbox_type="docker",
):
    pass
```

**Status**: NOT STARTED
**Priority**: LOW

### 19. Add Multi-Model Support
```python
# Support multiple models
def create_agent(
    models=[
        {"name": "qwen", "weight": 0.7},
        {"name": "claude", "weight": 0.3},
    ]
):
    pass
```

**Status**: NOT STARTED
**Priority**: LOW

### 20. Add Analytics Dashboard
```python
# Track usage statistics
- Tasks completed
- Test failures
- Pre-commit issues
- Anti-drift violations
```

**Status**: NOT STARTED
**Priority**: LOW

## Quick Wins (Do First)

### 30-Minute Tasks
- [ ] Fix test execution (setup mock LLM)
- [ ] Add basic error logging
- [ ] Add simple error handling
- [ ] Test with mock responses

### 1-Hour Tasks
- [ ] Add configuration options
- [ ] Update AGENTS.md with examples
- [ ] Add troubleshooting section
- [ ] Test multi-task workflow

### 2-Hour Tasks
- [ ] Integrate with swarm/nodes.py
- [ ] Add pre-commit automation
- [ ] Add test creation automation
- [ ] Add performance monitoring

## Testing Checklist

### Before Each Test Run
- [ ] LLM server is running
- [ ] `.venv` is activated
- [ ] `mini-swe-agent` is installed
- [ ] `qwen2.5:7b-instruct-q4_K_M` model is available

### After Each Test Run
- [ ] Check for errors
- [ ] Verify output format
- [ ] Check anti-drift compliance
- [ ] Review test coverage

## Resources

### Documentation
- mini-swe-agent docs: https://mini-swe-agent.com/
- swarm/ docs: `docs/` directory
- AGENTS.md: Main workflow guide

### Tools
- mini-swe-agent: `pip install mini-swe-agent`
- swarm/: `swarm/mini_swe_agent/`
- tests: `swarm/mini_swe_agent/test_extended_workflow.py`

### Commands
```bash
# Run tests
node ./scripts/venv.js test -- swarm/mini_swe_agent/test_extended_workflow.py

# Start LLM server (Qwen example)
# See .env for configuration

# Use mini-swe-agent
python -c "from swarm.mini_swe_agent import execute_extended_workflow; print(execute_extended_workflow('task'))"
```

## Notes

- **Version**: 0.2.0
- **Last Updated**: 2024-03-27
- **Status**: Active Development
- **Next Review**: After all tests pass

## Contributors

- [Your Name] - Initial integration
- [Next Person] - Testing and production deployment

---

**End of TODO_SWARM.md**
