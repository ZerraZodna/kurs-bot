from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from .state import SupervisorState
from .nodes import (
    architect_node,
    code_writer_node,
    reviewer_node,
    pre_commit_node,
    run_pre_commit_with_retry,
)
import logging

# Configure logger
logger = logging.getLogger(__name__)


def build_supervisor_graph(checkpointer=None):
    """
    Build supervisor workflow with mini-swe-agent as CODE WRITER and pre-commit automation.
    
    Workflow:
    1. ARCHITECT - Plans task with strict constraints
    2. CODE WRITER - Uses mini-swe-agent to generate code (auto-runs tests)
    3. REVIEWER - Validates anti-drift compliance
    4. Loop back to ARCHITECT if rejected
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

    def pre_commit_result(state: SupervisorState):
        """
        Handle pre-commit result: PASS -> end, FAIL -> retry.
        """
        if state.get("pre_commit_success"):
            logger.info("Pre-commit passed, ending workflow")
            return "end"
        
        if state.get("pre_commit_attempts", 0) >= 3:
            logger.error(f"All {3} pre-commit attempts failed, aborting")
            return "end"
        
        logger.warning(f"Pre-commit failed, retrying (attempt {state.get('pre_commit_attempts', 0) + 1}/3)")
        return "code_writer"

    workflow.add_conditional_edges("reviewer", should_continue, {"architect": "architect", "end": END})
    workflow.add_conditional_edges("pre_commit", pre_commit_result, {"code_writer": "code_writer", "end": END})

    return workflow.compile(checkpointer=checkpointer)
