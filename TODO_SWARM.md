# TODO: Human-In-The-Loop Swarm Integration

## Overview
Current swarm implementation operates as a closed automation cycle without explicit human intervention points. This document tracks necessary work to implement a complete 9-step human-in-the-loop workflow that puts humans in control of every automation cycle.

## Current Status
✅ Basic swarm nodes implemented (Architect → Code Writer → Reviewer → Pre-Commit)
✅ Anti-drift rules enforced programmatically
✅ Integration with mini-swe-agent as code execution layer
❌ Human approval points missing at critical interfaces
❌ No human review of AI-generated prompts
❌ No verification step before commits/pushes
❌ Automated workflow bypasses human oversight

## Next Steps - Human Integration

### 1. Implement Human Approval Points (CRITICAL)
**Problem**: System proceeds without human review at crucial decision points
**Goal**: Add explicit approval requirements following 9-step workflow design

- [ ] Before proceeding from Architect to Code Writer: Human must approve task breakdown
- [ ] Before applying changes from Code Writer: Human must review generated diff
- [ ] Before running pre-commit checks: Human must approve test execution
- [ ] In node outputs: Add `human_approval_needed: True` field when critical changes occur

**Priority**: CRITICAL - No automation without human involvement

**Implementation Requirements:**
```python
# In state.py, add approval status tracking:
human_approval_needed: bool
pending_action: str  # Description of what needs approval
approved_by_human: bool
```

### 2. Create Human Interface Layer (CRITICAL) 
**Problem**: No proper Hermes Agent mediation between humans and automation
**Goal**: Implement Hermes Agent as human/swarm interface following workflow design

- [ ] Step 2: Hermes Agent writes AI prompt for swarm and shows to human
- [ ] Step 3: Human reviews and approves prompts before swarm activation
- [ ] Step 8: Hermes Agent evaluates swarm results and prepares for final approval
- [ ] Step 9: Human performs final review and decides to push

**Priority**: CRITICAL - This is the missing interface design

### 3. Modify Graph Workflow Flow
**Current**: Automated flow from Architect → Code Writer → Reviewer → Pre-Commit
**Goal**: Add approval gates that stop workflow until human approval received

```python
# In graph.py, add conditional logic after each node:
def routing_logic(state):
    # After architect completion
    if state.get('pending_approval_for', '') == 'code_writer':
        return 'awaiting_human_approval' 
    
    # After code writer completion  
    if state.get('pending_approval_for', '') == 'review':
        return 'awaiting_human_approval'
    
    # After reviewer completion
    if state.get('pending_approval_for', '') == 'pre_commit':
        return 'awaiting_human_approval'
    
    return state.get('next_node')
```

**Priority**: HIGH - Required for human-in-the-loop workflow

### 4. Add Node Wrapping for Approval Integration
**Problem**: Current nodes don't support approval requirements
**Goal**: Wrap each node to check for human approval before advancing

For architect_node:
```python
def architect_node(state: dict[str, Any]) -> dict[str, Any]:
    # Existing architect logic
    llm_result = plan_task_with_constraints(state['original_request']) 
    subtasks = parse_to_subtasks(llm_result)
    
    # NEW: Set state to wait for human approval before code writer
    return {
        "subtasks": subtasks,
        "human_approval_needed": True,
        "pending_action": f"Approve task breakdown before code writer: {str(subtasks)[:100]}...",
        "action_details": {
            "node": "architect", 
            "next_step": "code_writer",
            "content": subtasks
        },
        "next_node": "awaiting_human_approval"  # Stop workflow until approval
    }
```

**Priority**: HIGH - Implements approval points in core logic

### 5. Create Human Approval Mechanism
**Goal**: Allow humans to review, approve, reject, or modify requests at each interface point

- [ ] Interface to show pending actions requiring approval
- [ ] Ability to approve, reject, or request modifications
- [ ] Option to cancel automation cycle entirely
- [ ] Resume workflow from appropriate state when approved

**Implementation considerations:**
- May need persistent state storage for waiting workflow instances
- Notification mechanism for humans when approval required
- Mechanism to resume workflow after approval

#### 5a. Human Approval Interface
- [ ] Present clear information about what's happening and what's requesting approval
- [ ] Allow for contextual decision making with full information
- [ ] Implement feedback pathway to adjust workflow if rejected

**Priority**: CRITICAL - No human-in-the-loop without this mechanism

## Next Steps - Testing with Human Oversight

### 6. Update Testing Approach for Human Integration
**Problem**: Tests run without human involvement defeating purpose of safe automation
**Goal**: Test human-in-the-loop workflow, not just autonomous automation

- [ ] Develop tests that include human decision points (simulated or mocked)
- [ ] Verify approval mechanisms work correctly
- [ ] Test cancellation and modification flows  
- [ ] Confirm all anti-drift rules enforced through human oversight

**Priority**: HIGH - Tests must validate complete workflow

### 7. Test Edge Cases with Human Interface
- [ ] What happens with human not available for extended period?
- [ ] How to handle rejected approval requests?
- [ ] How to handle cancelled automation cycles?
- [ ] Multiple concurrent automation requests?
- [ ] Emergency cancellation during complex workflow?

**Priority**: MEDIUM - Important for production reliability

## Next Steps - Safety & Validation

### 8. Implement Pre-Commit Safety Checks with Human Authorization
**Current**: Pre-commit testing runs in closed loop with automated retries
**Goal**: Add human awareness of test results and failures

- [ ] When tests fail, escalate to human for decision on how to proceed
- [ ] Don't hide failed tests - humans should see what changes break tests
- [ ] Allow humans to request fixes as new tasks when failures occur

**Priority**: HIGH - Critical safety mechanism

```python
# In pre-commit node:
def pre_commit_node(state):
    test_results = run_tests(state['proposed_changes'])
    
    if not all([r.success for r in test_results]):
        return {
            "test_failures": test_results,
            "human_approval_needed": True,
            "pending_action": f"Review failing tests before fixes: {[f.name for f in test_results if not f.success]}",
            "next_node": "awaiting_human_approval"
        }
    
    return {"tests_passed": True}
```

### 9. Add Human Verification of Final Commits
**Problem**: Automated commit without final human review allows mistakes to propagate
**Goal**: Create mandatory human review point before changes reach repository

From our 9-step workflow in SWARM.md this is Steps 8-9:
```
8. HERMES AGENT evaluates result from Swarm
   └─ Informs human that job is finished
   └─ Awaits human commit decision
      ↓
9. FINAL APPROVAL
   └─ Human review and verification
   └─ Human decision to commit and push
```

**Priority**: CRITICAL - Prevents bad changes reaching repository without review

## Next Steps - Documentation
### 10. Update Integration Documentation
- [ ] Add human-in-the-loop workflow explanation to AGENTS.md
- [ ] Document approval mechanism to SWARM.md
- [ ] Create troubleshooting guide for human interface (how to approve, reject, etc.)

**Priority**: MEDIUM - Critical for user adoption

## Quick Wins (Top Priority)

### Immediate Actions for Human Control
- [ ] Add human approval flag to state management
- [ ] Modify one node (architect) with approval requirement as proof of concept
- [ ] Implement basic approval mechanism for proof of concept
- [ ] Test simple approval workflow

## Testing Checklist for Human Integration

### Before Each Test Run
- [ ] Human interface capability available for approval points
- [ ] State tracking for approval status functional  
- [ ] Approval mechanism prevents workflow progression without consent
- [ ] Ability to cancel workflows during approval steps

### After Each Test Run  
- [ ] Human control points working correctly
- [ ] Workflow properly stops at approval gates
- [ ] Approval/Rejection decisions processed correctly
- [ ] Cancellation terminates workflow as expected

## Resources
- SWARM.md: Complete 9-step human-in-the-loop workflow design
- archive/HUMAN_INTEGRATION_GUIDE.md: Technical recommendations for implementation
- AGENTS.md: Integration patterns with Hermes Agent

---

**Document Status**: Active Development  
**Last Updated**: 2026-03-28  
**Focus**: Human-First Architecture Implementation