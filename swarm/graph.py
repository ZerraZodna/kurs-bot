from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from .state import SupervisorState
from .nodes import architect_node, code_writer_node, reviewer_node


def build_supervisor_graph(checkpointer=None):
    if checkpointer is None:
        checkpointer = MemorySaver()

    workflow = StateGraph(SupervisorState)

    workflow.add_node("architect", architect_node)
    workflow.add_node("code_writer", code_writer_node)
    workflow.add_node("reviewer", reviewer_node)

    workflow.set_entry_point("architect")
    workflow.add_edge("architect", "code_writer")
    workflow.add_edge("code_writer", "reviewer")

    def should_continue(state: SupervisorState):
        if state.get("final_decision") == "APPROVE":
            return "end"
        if state.get("iteration_count", 0) >= 3:
            return "end"
        return "architect"

    workflow.add_conditional_edges("reviewer", should_continue, {"architect": "architect", "end": END})

    return workflow.compile(checkpointer=checkpointer)
