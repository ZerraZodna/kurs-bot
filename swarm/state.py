from typing import TypedDict, Annotated, Sequence, Literal
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class SupervisorState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    current_task: str | None
    subtasks: list[str] | None
    proposed_changes: str | None
    review_feedback: str | None
    final_decision: Literal["APPROVE", "REJECT"] | None
    iteration_count: int
