# TODO: Human-In-The-Loop Swarm Integration

## Overview
See master document docs/dev/SWARM.md

Current swarm implementation operates as a closed automation cycle without explicit human intervention points. This document tracks necessary work to implement a complete 9-step human-in-the-loop workflow that puts humans in control of every automation cycle.

The architecture will be: Human tells Hermes what to do → Hermes initiates LangGraph swarm → Swarm controls Telegram bot which communicates with Human for approval points.

## Current Status
✅ Internal swarm flow implemented: architect → code_writer → reviewer → pre_commit
✅ If pre-commit fails → loops back to code_writer (testing-and-back-to-coding loop functionality)
✅ If reviewer rejects → loops back to architect (anti-drift compliance)
✅ 3-iteration limits on both loops with abortion after max attempts
✅ Anti-drift rules enforced in reviewer node
✅ Integration with mini-swe-agent as code execution layer in code_writer
❌ Human approval points missing at critical interfaces
❌ No human review of AI-generated prompts (Step 2→3 in 9-step)
❌ No verification step before commits/pushes (Step 8→9 in 9-step)
❌ No integration between Hermes, Swarm, and Telegram for approval workflow
❌ Automated workflow bypasses human oversight

## Next Steps - Hermes-Swarm-Telegram Integration

### 1. Enable Hermes to Initiate Swarm Processes (CRITICAL)
**Problem**: No connection between Hermes agent (me) and the LangGraph swarm for processing user requests
**Goal**: When you tell me "implement this feature", I (Hermes agent) start the appropriate LangGraph swarm process

- [ ] Implement mechanism for Hermes to properly invoke the swarm process when you give requests
- [ ] Pass your original request and any constraints from Hermes to the swarm
- [ ] Ensure swarm receives appropriate context that Hermes knows about your intent
- [ ] Set up proper error handling if swarm fails to start

**Priority**: CRITICAL - This bridges your interaction with swarm execution

### 2. Implement Hermes-Guided Swarm with Telegram Communication Layer (CRITICAL)
**Problem**: No communication layer that connects the swarm back to human after Hermes initiates it
**Goal**: Swarm communicates with humans via Telegram bot for approval points while maintaining connection back to the orchestrated process

- [ ] Set up swarm to communicate with human via Telegram bot when human approval needed
- [ ] Link specific swarm instances to the original Hermes initiating command that started them
- [ ] Ensure you can trace from your original request through Hermes to the swarm to its status
- [ ] Set up proper user authentication for the Telegram bot to ensure security
- [ ] Make sure the "you approve via telegram" happens for the correct requests from step 1

**Priority**: CRITICAL - This enables human approvals in the flow while maintaining connections

### 3. Implement Telegram Bot for Approval Points (CRITICAL)
**Problem**: No human approval interface using Telegram as the communication medium for Steps 2→3 and 8→9
**Goal**: Telegram bot serves as the communication channel controlled by the swarm to ask for human approval at critical stages

- [ ] Step 2: Telegram bot, controlled by swarm, generates and presents AI prompts to human based on Hermes-initiated request
- [ ] Step 2: Telegram bot displays generated AI prompt to human without timeout constraints
- [ ] Step 3: Telegram bot waits for human approval WITHOUT timeout (using Telegram message interface)
- [ ] Step 3: Human can approve, reject, or request modifications via Telegram bot commands
- [ ] Step 3: When rejected, return to prompt generation or allow cancellation
- [ ] Step 3: Only proceed with swarm internal execution if human approves via Telegram
- [ ] Step 8: After swarm completes internal steps, Telegram bot presents results to human for review
- [ ] Step 9: Telegram bot enables human to authorize final commitment and push to repository
- [ ] Create appropriate Telegram bot commands (e.g., /approve, /reject, /cancel) tied to specific pending processes

**Priority**: CRITICAL - These are the essential human control points connecting Hermes-initiated processes to human decision making

### 4. Maintain State Linkage Across Systems
**Current**: No connection between Hermes session that initiated, LangGraph run instance, and Telegram approvals
**Goal**: Enable end-to-end traceability linking your original request through all systems

- [ ] Establish identifiers linking Hermes commands to specific swarm runs
- [ ] Ensure each Telegram approval request identifies which original request it relates to
- [ ] Maintain ability to cancel or modify a pending request across all three systems
- [ ] Log chain of actions from initial request through completion for audit trail

**Priority**: HIGH - Needed for proper operation and debugging

## Next Steps - Safety & Validation

### 5. Implement Secure Handoffs Between Systems
**Problem**: Multiple systems (Hermes, Swarm, Telegram) must coordinate safely
**Goal**: Ensure appropriate security and validation between all system interactions

- [ ] Validate swarm operations originate from authorized Hermes commands
- [ ] Verify Telegram approval commands come from authorized user
- [ ] Ensure only approved changes are committed to the repository
- [ ] Implement proper authentication at each handoff point
- [ ] Audit log all cross-system operations

**Priority**: HIGH - Critical for security with multiple system interactions

### 6. Test Full Integration Flow
**Problem**: Need to test the complete flow from top to bottom: Human→Hermes→Swarm→Telegram→Human→Swarm→Hermes→Completion
**Goal**: Validate the end-to-end workflow functions correctly

- [ ] Test complete 9-step flow from original request to final git push
- [ ] Test rejection scenarios at both approval points
- [ ] Test interruption/cancellation scenarios
- [ ] Test multiple simultaneous request scenarios

**Priority**: HIGH - Required to validate the complete architecture

## Next Steps - Testing with Integrated Systems

### 7. Update Testing Approach
**Problem**: Need to simulate the coordinated multi-system workflow
**Goal**: Test the integrated systems as they will operate in production

- [ ] Create tests that validate Hermes can properly initiate swarm processes
- [ ] Test state linkage between all three systems
- [ ] Test failure resilience (what happens if Telegram unavailable?)
- [ ] Test the complete approval flow through all systems

**Priority**: MEDIUM - Required for stability

### 8. Test Edge Cases in Multi-System Environment
- [ ] What if the same user has multiple pending requests? (avoid mix-ups between requests)
- [ ] What if you approve the wrong pending request? (verification before applying)
- [ ] How to handle interruptions where Hermes is doing other work while swarm waits for approval?
- [ ] What about authorization verification for git operations?
- [ ] What happens if Hermes restarts while swarm is waiting for approval?

**Priority**: MEDIUM - Important for reliability

## Next Steps - Documentation
### 9. Update Integration Documentation
- [ ] Document the 3-part workflow (Hermes→Swarm→Telegram→Swarm→etc.)
- [ ] Explain how each system connects to the others
- [ ] Create troubleshooting guide for multi-system interactions
- [ ] Document security considerations and user authorization flows

**Priority**: MEDIUM - Critical for operation and maintenance

## Quick Wins (Top Priority)

### Immediate Actions for Integration
- [ ] Enable Hermes to securely initiate swarm processes when told to do so
- [ ] Set up identity verification for linking systems properly
- [ ] Connect Telegram bot to receive requests from and respond to swarm operations
- [ ] Implement secure approval flow from Telegram to complete the loop

## Testing Checklist for Integrated Systems

### Before Each Test Run
- [ ] Hermes can be instructed to initiate swarm processes
- [ ] Unique identification system linking requests across all components
- [ ] Telegram bot ready to receive and respond to user approval requests
- [ ] Permission and security verification working between systems

### After Each Test Run
- [ ] Complete 9-step path works: Human→Hermes→Swarm→Telegram→Human→Swarm→Hermes→Final Action
- [ ] Human maintains control throughout via the integrated approval points
- [ ] Multiple requests properly isolated and traced
- [ ] Changes only pushed after human approves through the full chain

## Resources
- SWARM.md: Complete 9-step human-in-the-loop workflow design
- LangGraph swarm: Architect → Code Writer → Reviewer → Pre-Commit implementation

---

**Document Status**: Active Development
**Last Updated**: 2026-03-28
**Focus**: Integrated Hermes→Swarm→Telegram Human Control Architecture
