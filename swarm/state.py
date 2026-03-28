from typing import TypedDict, Annotated, Sequence, Literal, Any
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
    # Telegram integration fields
    telegram_chat_id: int | None  # Telegram chat ID for approval requests
    telegram_user_id: int | None  # User ID for authorization
    telegram_request_id: str | None  # Current approval request ID
    workflow_instance: Any  # The workflow instance that's waiting for approval
