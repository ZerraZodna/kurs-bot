# TODO: Telegram Bot Integration for Swarm Human-in-the-Loop

## Overview
Implement Telegram bot communication layer for the 9-step human-in-the-loop workflow. The bot will serve as the communication interface controlled by the swarm to get human approvals at critical points.

## Dependencies
- See master document docs/dev/SWARM.md for the 9-step workflow details
- See TODO_SWARM.md for overall roadmap
- Basic Telegram polling code created in `swarm/telegram/telegram_swarm_polling.py`

## Requirements: Telegram Bot Commands
- `/approve` - Approve pending swarm request
- `/retry "What needs to be adjusted..."` - Request adjustments to current task
- `/decline` - Decline pending request completely
- `/help` - Show available commands and usage

## Implementation Plan

### 1. ~~Complete Telegram Bot Implementation~~
**Status:** Completed - Basic implementation with command handlers, state management, and polling is in place
**Goal**: Finish and test the basic implementation in `swarm/telegram/telegram_swarm_polling.py`

- [ ] Add proper authorization verification (only authorized user can approve commands)
- [ ] Add timeout handling for pending approval requests
- [ ] Implement error logging and monitoring for approval process
- [ ] Create proper data structure for linking swarm operations to chat IDs
- [ ] Add graceful shutdown handling for polling
- [ ] Implement unit testing for command handling functions

### 2. Connect Swarm to Telegram Approval System
**Goal**: Integrate the approval bot with the current swarm workflow

- [ ] Modify swarm graph to call `send_swarm_approval_request` at step 2-3 (prompt approval)
- [ ] Modify swarm graph to call `send_swarm_approval_request` at step 8-9 (final approval)
- [ ] Add request ID generation for tracking approval states
- [ ] Update supervisor state to include Telegram chat information

### 3. Implement Step 2-3 Approval Flow (Prompt Approval)
**Goal**: Enable human to approve AI swarm prompts via Telegram after Hermes initiates

For this flow: 2. HERMES AGENT → Write idea as an AI prompt for the swarm and shows it to HUMAN → 3. HUMAN → Reads and approves prompts via Telegram

- [ ] When swarm needs human prompt approval (after step 2), trigger `send_swarm_approval_request`
- [ ] Pass generated prompt as the prompt_or_change_summary
- [ ] Set approval_stage="start" for this phase
- [ ] CRITICAL: Handle approval responses by resuming the blocked swarm workflow
- [ ] Handle rejection responses by terminating or adjusting workflow

### 4. CRITICAL FIX: Implement Workflow Resume After Approval (Final Approval)
**Goal**: Enable human final approval via Telegram before committing changes

For this flow: 8. HERMES AGENT evaluates result from Swarm → informs human that job is finished → 9. FINAL APPROVAL → Human review and push via Telegram

- [ ] When swarm completes internal work (steps 4-7 finish with all loops completed), trigger `send_swarm_approval_request`
- [ ] Pass summary of changes and test results as the prompt_or_change_summary
- [ ] Set approval_stage="end" for this phase
- [ ] Handle approval by executing git commit/push operations
- [ ] Handle rejection by cancelling without committing
- [ ] Handle retry by restarting workflow with user feedback

### 5. Integration with Internal Swarm Loops
**Goal**: Ensure the Telegram bot interface works correctly with internal workflow loops.

The internal implemented system (architect → code_writer → reviewer → pre_commit):
- Internal pre-commit failure loops back to code_writer (testing failures)
- Internal reviewer rejection loops back to architect (anti-drift violations)
- These internal loops continue automatically without user involvement
- Only the external interfaces (initial approval step and final approval step) should involve the user

- [ ] Ensure internal loops (pre-commit→code_writer, reviewer→architect) continue automatically
- [ ] Human approval via Telegram should only be required at the external interface points (start and end)
- [ ] Don't interrupt existing internal flow logic for test failures or anti-drift rejections

### 6. Security and Authentication
**Goal**: Ensure secure operation and verify only authorized user can approve changes

- [ ] Verify Telegram user ID against known authorized user
- [ ] Implement additional security token verification if needed
- [ ] Create error handling for unauthorized approval attempts
- [ ] Log all approval/rejection activities with user identity

### 7. Connection to Swarm State Management
**Goal**: Connect the Telegram approval system to the actual swarm execution state

- [ ] Link approval states back to specific swarm thread/run instance
- [ ] Ensure that approving user receives approval results properly after processing
- [ ] Clean up approval state properly after operation completes
- [ ] Add audit trail linking user approvals to Git operations

### 8. User Experience Refinements
**Goal**: Provide good user experience for approval workflow

- [ ] Improve approval request messages with more detailed context
- [ ] Add progress indicators showing swarm status in ongoing operations
- [ ] Provide clear summary information when requesting final approval
- [ ] Add feedback to user during approval processing phase

### 9. Error Handling and Resilience
**Goal**: Create robust error handling for all system failure scenarios

- [ ] Handle Telegram connectivity issues gracefully
- [ ] Recover from approval system crashes without losing pending approvals
- [ ] Handle edge cases like conflicting approvals for same request
- [ ] Implement retry logic for failed message sending

### 10. Testing Plan
**Goal**: Fully test the complete approval workflow integration

- [ ] Unit test individual command handlers
- [ ] Test complete 9-step workflow with approval integration
- [ ] Test all command scenarios (/approve, /retry, /decline, /help)
- [ ] Test security and authorization flows
- [ ] Test error recovery scenarios
- [ ] Test internal swarm loop resilience with approval interruptions

## Anti-Drift Constraints
- Only modify files in appropriate directories (respect project structure)
- Do not modify existing swarm core functionality unnecessarily, only add communication layer
- Do not modify the basic telegram polling structure created in `swarm/telegram/telegram_swarm_polling.py`
- Keep changes minimal and focused - only implement the integration pieces
- Do not implement entirely new features beyond the approval workflow

## Files to Modify/Extend
- `swarm/telegram/telegram_swarm_polling.py` (extend the existing implementation)
- `swarm/graph.py` (connect approval function calls)
- `swarm/nodes.py` (modify nodes to send approval requests as needed)
- `swarm/state.py` (add fields for Telegram chat/authorization information)

## Success Criteria
- [ ] Step 2-3 approval flow works: Swarm pauses for Telegram approval of prompts
- [ ] Step 8-9 approval flow works: Swarm pauses for Telegram approval before committing
- [ ] All commands (`/approve`, `/retry`, `/decline`, `/help`) work correctly
- [ ] Authorization verification prevents unauthorized usage
- [ ] Internal swarm loops continue automatically without user intervention
- [ ] Git operations only happen on user approval in step 8-9
- [ ] Proper error handling and logging in place
- [ ] Existing swarm functionality unaffected by integration

---

**Document Dependencies**:
- Master SWARM.md has workflow details
- TODO_SWARM.md has overall roadmap
- This document has Telegram implementation specifics
- `swarm/telegram/telegram_swarm_polling.py` has basic implementation

**Status**: Foundation ready, ready to delegate to sub-agent for implementation
**Complexity**: MEDIUM
**Reference**: Master SWARM.md and TODO_SWARM.md for workflow context
