from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from .state import SupervisorState
from .nodes import (
    architect_node,
    code_writer_node,
    reviewer_node,
    pre_commit_node,
)
import logging

# Configure logger
logger = logging.getLogger(__name__)

# Import integration module
from .telegram import hook_request_prompt_approval, hook_request_final_approval, hook_send_swarm_complete_notification


def build_supervisor_graph(checkpointer=None):
    """
    Build supervisor workflow with mini-swe-agent as CODE WRITER and pre-commit automation.

    Workflow:
    1. ARCHITECT - Plans task with strict constraints
    2. CODE WRITER - Uses mini-swe-agent to generate code (auto-runs tests)
    3. REVIEWER - Validates anti-drift compliance
    4. Loop back to ARCHITECT if rejected
    5. Prompt Approval (Step 2-3) - Wait for user approval of generated prompt
    6. Internal iterations (if needed)
    7. Pre-commit checks
    8. Final Approval (Step 8-9) - Wait for user approval before commit
    9. Complete
    """
    if checkpointer is None:
        checkpointer = MemorySaver()

    workflow = StateGraph(SupervisorState)

    workflow.add_node("architect", architect_node)
    workflow.add_node("code_writer", code_writer_node)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("pre_commit", pre_commit_node)

    workflow.set_entry_point("architect")
    workflow.add_edge("architect", "code_writer")
    workflow.add_edge("code_writer", "reviewer")
    workflow.add_edge("reviewer", "pre_commit")

    # === Step 2-3: Prompt Approval Hook ===
    # After architect generates prompt, request approval before proceeding
    def request_prompt_approval(state: SupervisorState):
        """
        Request prompt approval from user via Telegram.
        Called after architect generates prompt (Step 2-3).

        Args:
            state: Current graph state containing telegram_chat_id, telegram_user_id

        Returns:
            Updated state with request_id if approval was requested
        """
        # Check if we have telegram integration configured
        if not state.get("telegram_chat_id") or not state.get("telegram_user_id"):
            logger.info("[swarm-graph] Telegram approval not configured, proceeding without approval")
            return state  # Continue without approval if not configured

        request_id = None
        try:
            request_id = hook_request_prompt_approval(
                chat_id=state["telegram_chat_id"],
                user_id=state["telegram_user_id"],
                prompt=f"Architect prompt: {state.get('subtasks', [''])[0][:500]}",
                workflow_instance=None,
                request_id=state.get("telegram_request_id", ""),
            )

            # Store request_id in state for correlation
            if request_id:
                state["telegram_request_id"] = request_id
                logger.info(f"[swarm-graph] Requested prompt approval: {request_id}")

        except Exception as e:
            logger.error(f"[swarm-graph] Failed to request prompt approval: {e}")
            # Continue execution if approval fails

        return state

    # Add prompt approval hook after architect
    workflow.add_node("prompt_approval", request_prompt_approval)
    workflow.add_edge("prompt_approval", "code_writer")

    def should_continue(state: SupervisorState):
        """
        Decide next step: APPROVE -> end, REJECT -> back to architect.
        """
        decision = state.get("final_decision", "")

        if decision == "APPROVE":
            logger.info("Review approved, moving to pre-commit")
            return "pre_commit"

        if state.get("iteration_count", 0) >= 3:
            logger.warning("Max iterations reached (3), aborting")
            return "end"

        logger.info(f"Review rejected, looping back to architect (attempt {state.get('iteration_count', 0) + 1}/3)")
        return "architect"

    # === Step 8-9: Final Approval Hook ===
    # After pre_commit passes, request final approval before completion
    def request_final_approval(state: SupervisorState):
        """
        Request final approval from user via Telegram.
        Called after pre_commit passes (Step 8-9).

        Args:
            state: Current graph state containing telegram_chat_id, telegram_user_id

        Returns:
            Updated state with request_id if approval was requested
        """
        # Check if we have telegram integration configured
        if not state.get("telegram_chat_id") or not state.get("telegram_user_id"):
            logger.info("[swarm-graph] Telegram approval not configured, proceeding without approval")
            return state  # Continue without approval if not configured

        request_id = None
        try:
            request_id = hook_request_final_approval(
                chat_id=state["telegram_chat_id"],
                user_id=state["telegram_user_id"],
                summary=f"Final changes ready for commit: {state.get('proposed_changes', '')[:500]}",
                workflow_instance=None,
                request_id=state.get("telegram_request_id", ""),
            )

            # Store request_id in state for correlation
            if request_id:
                state["telegram_request_id"] = request_id
                logger.info(f"[swarm-graph] Requested final approval: {request_id}")

        except Exception as e:
            logger.error(f"[swarm-graph] Failed to request final approval: {e}")
            # Continue execution if approval fails

        return state

    # Add final approval hook after pre_commit
    workflow.add_node("final_approval", request_final_approval)

    # Add completion notification hook after final approval
    def send_completion_notification(state: SupervisorState):
        """
        Send completion notification to user via Telegram.
        Called after workflow completes successfully.

        Args:
            state: Current graph state containing telegram_chat_id, telegram_user_id

        Returns:
            Updated state with completion notification sent
        """
        # Check if we have telegram integration configured
        if not state.get("telegram_chat_id") or not state.get("telegram_user_id"):
            return state

        try:
            hook_send_swarm_complete_notification(
                chat_id=state["telegram_chat_id"],
                user_id=state["telegram_user_id"],
                completion_details=f"Workflow completed successfully! Final decision: {state.get('final_decision', 'APPROVE')}",
            )
            logger.info("[swarm-graph] Sent completion notification")
        except Exception as e:
            logger.error(f"[swarm-graph] Failed to send completion notification: {e}")

        return state

    workflow.add_node("completion_notification", send_completion_notification)
    workflow.add_edge("final_approval", "completion_notification")

    def pre_commit_result(state: SupervisorState):
        """
        Handle pre-commit result: PASS -> final_approval, FAIL -> retry.
        """
        if state.get("pre_commit_success"):
            logger.info("Pre-commit passed, moving to final approval")
            return "final_approval"

        if state.get("pre_commit_attempts", 0) >= 3:
            logger.error(f"All {3} pre-commit attempts failed, aborting")
            return "end"

        logger.warning(f"Pre-commit failed, retrying (attempt {state.get('pre_commit_attempts', 0) + 1}/3)")
        return "code_writer"

    # Update conditional edges with new node names
    workflow.add_conditional_edges("reviewer", should_continue, {"architect": "architect", "end": END})
    workflow.add_conditional_edges(
        "pre_commit", pre_commit_result, {"code_writer": "code_writer", "final_approval": "final_approval"}
    )

    return workflow.compile(checkpointer=checkpointer)
