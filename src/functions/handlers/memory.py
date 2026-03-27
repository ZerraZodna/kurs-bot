from typing import TYPE_CHECKING, Any, Dict

from src.lessons.state import set_current_lesson
from src.memories.constants import MemoryCategory, MemoryKey
from src.memories.semantic_search import get_semantic_search_service
from src.models.database import Session as DBSession

if TYPE_CHECKING:
    from ..executor import FunctionExecutor


class MemoryHandler:
    """Handles memory and confirmation function calls. Delegated from FunctionExecutor."""

    def __init__(self, executor: "FunctionExecutor") -> None:
        self.executor = executor

    async def confirm_yes(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle confirm_yes function."""
        user_id = context.get("user_id")
        confirmation_context = params.get("context", "general")
        memory_manager = context.get("memory_manager")

        try:
            # Special handling for lesson repeat context
            if confirmation_context == "lesson_repeat" and memory_manager:
                offered_memories = memory_manager.get_memory(user_id, MemoryKey.LESSON_REPEAT_OFFERED)
                if offered_memories:
                    lesson_id_str = offered_memories[0].get("value")
                    try:
                        lesson_id = int(lesson_id_str)
                        session = context.get("session")
                        if session:
                            lesson = self.executor._get_lesson_by_id(lesson_id, session)
                            if lesson:
                                # Clear the offered memory after use
                                memory_manager.archive_memories(user_id, [offered_memories[0].get("memory_id")])
                                return self.executor._ok_response(
                                    confirmed=True,
                                    context=confirmation_context,
                                    lesson_id=lesson_id,
                                    title=lesson.title,
                                    content=lesson.content,
                                )
                    except (ValueError, TypeError):
                        pass

            # Store confirmation
            memory_manager.store_memory(
                user_id=user_id,
                key="user_confirmation",
                value=f"yes:{confirmation_context}",
                category=MemoryCategory.CONVERSATION.value,
                source="function_executor",
                ttl_hours=1,
            )

            return self.executor._ok_response(confirmed=True, context=confirmation_context)
        except Exception as e:
            return self.executor._error_response(str(e))

    async def confirm_no(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle confirm_no function."""
        user_id = context.get("user_id")
        confirmation_context = params.get("context", "general")
        memory_manager = context.get("memory_manager")

        try:
            memory_manager.store_memory(
                user_id=user_id,
                key="user_confirmation",
                value=f"no:{confirmation_context}",
                category=MemoryCategory.CONVERSATION.value,
                source="function_executor",
                ttl_hours=1,
            )

            return self.executor._ok_response(confirmed=False, context=confirmation_context)
        except Exception as e:
            return self.executor._error_response(str(e))

    async def extract_memory(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle extract_memory function."""
        user_id = context.get("user_id")
        key = params.get("key")
        value = params.get("value")
        ttl_hours = params.get("ttl_hours")
        memory_manager = context.get("memory_manager")

        # Route lesson state writes through centralized helpers
        if key == MemoryKey.LESSON_CURRENT:
            parsed = int(value) if isinstance(value, str | int) and str(value).isdigit() else value
            set_current_lesson(memory_manager, user_id, parsed)
            return self.executor._ok_response(key=key, value=value, updated=True)

        category = self.executor._get_memory_category_for_key(key)

        try:
            existing = memory_manager.get_memory(user_id, key)
            memory_manager.store_memory(
                user_id=user_id,
                key=key,
                value=value,
                category=category,
                source="function_executor",
                ttl_hours=ttl_hours,
            )
            return self.executor._ok_response(key=key, value=value, category=category, updated=bool(existing))
        except Exception as e:
            return self.executor._error_response(str(e))

    async def forget_memories(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle forget_memories - AI callable semantic memory deletion."""
        user_id = context.get("user_id")
        query_text = params.get("query_text")
        session = context.get("session")
        memory_manager = context.get("memory_manager")

        if not query_text or not query_text.strip():
            return self.executor._error_response("query_text is required")
        if not memory_manager:
            return self.executor._error_response("Missing memory_manager")

        search_service = get_semantic_search_service()
        with DBSession(bind=session.get_bind()) as search_session:
            results = await search_service.search_memories(
                user_id=user_id, query_text=query_text, session=search_session, limit=10
            )

            memory_ids = [m.memory_id for m, _ in results]

        if not memory_ids:
            return self.executor._error_response("No matching memories found")

        archived_count = memory_manager.archive_memories(user_id, memory_ids)
        return self.executor._ok_response(
            query_text=query_text, found_count=len(memory_ids), archived_count=archived_count
        )

    async def handle(self, func_name: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch to specific handler."""
        method_name = func_name.replace("-", "_")
        method = getattr(self, method_name, None)
        if method:
            return await method(params, context)
        raise ValueError(f"Unknown memory function: {func_name}")
