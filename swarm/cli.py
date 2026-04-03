#!/usr/bin/env python
"""CLI entry-point for the kurs-bot LangGraph coding supervisor with Telegram approval integration."""

import os
import asyncio
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from .graph import build_supervisor_graph

# Import telegram integration
from .telegram import integration


async def request_swarm_approval(state: dict, summary: str, stage: str = "start") -> bool:
    """
    Request approval from user via Telegram.

    Args:
        state: Current swarm state
        summary: Summary of what needs approval
        stage: "start" for prompt approval, "end" for final approval

    Returns:
        True if approval request sent successfully
    """
    chat_id = state.get("telegram_chat_id")
    user_id = state.get("telegram_user_id")
    request_id = state.get("telegram_request_id")

    if not chat_id or not user_id:
        logger.warning("[swarm-cli] Telegram chat_id or user_id not set, skipping approval request")
        return False

    # Send approval request
    result = integration.request_approval(
        chat_id=chat_id, user_id=user_id, workflow_instance=None, stage=stage, summary=summary, request_id=request_id
    )

    if result:
        # Update state with request ID
        state["telegram_request_id"] = result
        logger.info(f"[swarm-cli] Approval request sent: {result}")
        return True

    logger.error("[swarm-cli] Failed to send approval request")
    return False


async def main(task: str) -> None:
    checkpointer = MemorySaver()
    graph = build_supervisor_graph(checkpointer)

    config = {"configurable": {"thread_id": f"task-{hash(task) % 100000}"}}

    initial_state = {
        "messages": [HumanMessage(content=f"Task: {task}")],
        "current_task": task,
        "subtasks": None,
        "proposed_changes": None,
        "review_feedback": None,
        "final_decision": None,
        "iteration_count": 0,
        # Telegram integration fields
        "telegram_chat_id": int(os.getenv("TELEGRAM_CHAT_ID", "0")),
        "telegram_user_id": int(os.getenv("TELEGRAM_USER_ID", "0")),
        "telegram_request_id": None,
    }

    # Check if Telegram is configured
    chat_id = initial_state.get("telegram_chat_id")
    user_id = initial_state.get("telegram_user_id")

    if chat_id and user_id and chat_id != 0:
        # Register authorization
        integration.register_chat_authorization(chat_id, user_id)

        # Update state with registered values
        initial_state["telegram_chat_id"] = chat_id
        initial_state["telegram_user_id"] = user_id

    print("=" * 80)
    print("   KURS-BOT SWARM CODING SUPERVISOR")
    print("   (Technical only — no spiritual content)")
    print("=" * 80)
    print(f"\nTask: {task}\n")
    print("Running architect → prompt_approval → code_writer → reviewer cycle...\n")
    print(f"[DEBUG] Task received: {task}")
    print(f"[DEBUG] Config created: {config}")
    print(f"[DEBUG] Initial state created: {initial_state}")
    print(f"[DEBUG] Thread ID: {config['configurable']['thread_id']}")
    print(f"[DEBUG] Chat ID: {initial_state['telegram_chat_id']}")
    print(f"[DEBUG] User ID: {initial_state['telegram_user_id']}")
    print(f"[DEBUG] Checkpointer: {checkpointer}")
    print(f"[DEBUG] Graph: {graph}")
    print("Step 1/4: Architect planning...")
    print("Step 2/4: Requesting prompt approval via Telegram...")
    print("Step 3/4: Code writer generating...")
    print("Step 4/4: Review complete!\n")

    #try:
    print("=" * 80)
    print("[DEBUG] Starting graph.ainvoke()...")
    print("[DEBUG] Initial state messages count:", len(initial_state['messages']))
    for i, msg in enumerate(initial_state['messages']):
        if hasattr(msg, 'content'):
            content = str(msg.content)
        else:
            content = str(msg)
        print(f"[DEBUG] Message {i}: {content[:200] if len(str(content)) > 200 else content}...")
    result = await graph.ainvoke(initial_state, config, timeout=120)
    print("[DEBUG] graph.invoke() completed!")
    print(f"[DEBUG] Result keys: {result.keys()}")
    print(f"[DEBUG] Result messages count: {len(result.get('messages', []))}")
    
    # Show ENTIRE LLM messages from result
    print("\n" + "=" * 80)
    print("[DEBUG] ENTIRE RESULT MESSAGES:")
    for i, msg in enumerate(result.get('messages', [])):
        if hasattr(msg, 'content'):
            content = str(msg.content)
        else:
            content = str(msg)
        print(f"\n--- Message {i} ({msg.role if hasattr(msg, 'role') else 'unknown'}):")
        print(content[:1000] + ("..." if len(content) > 1000 else ""))

    print("=" * 80)
    print(f"FINAL DECISION: {result.get('final_decision', 'UNKNOWN')}")
    print("=" * 80)
    print("Step 3/3: Review complete!")
    print("\n📝 Reviewer feedback:", "✅ Approved" if result.get("final_decision") == "APPROVE" else "❌ Rejected")
    print("\n✅ Task completed successfully!")
    print(f"\n[DEBUG] Final decision: {result.get('final_decision')}")
    print(f"[DEBUG] Proposed changes exists: {bool(result.get('proposed_changes'))}")
    print(f"[DEBUG] Review feedback exists: {bool(result.get('review_feedback'))}")

    # Proposed diff (most important)
    if result.get("proposed_changes"):
        print(f"\n--- PROPOSED DIFF ---\n{result['proposed_changes']}")

    # Reviewer feedback
    if result.get("review_feedback"):
        print(f"\n--- REVIEWER FEEDBACK ---\n{result['review_feedback']}")

    # Safe node messages (debug info)
    messages = result.get("messages", [])
    if messages:
        print("\n--- LAST 3 NODE MESSAGES ---")
        for msg in messages[-3:]:
            # Safe way to get content from BaseMessage or dict
            if hasattr(msg, "content"):
                content = str(msg.content)
            else:
                content = str(msg)
            preview = content[:600] + ("..." if len(content) > 600 else "")
            role = getattr(msg, "role", "assistant") if hasattr(msg, "role") else "assistant"
            print(f"\n[{role.upper()}]:")
            print(preview)
            print("-" * 60)

    print("\n" + "=" * 80)

    # If final decision is APPROVE and we have Telegram configured, request final approval
    if result.get("final_decision") == "APPROVE":
        chat_id = initial_state.get("telegram_chat_id")
        user_id = initial_state.get("telegram_user_id")

        if chat_id and user_id and chat_id != 0:
            print("\n🔄 REQUESTING FINAL APPROVAL via Telegram...")
            print("Please use /approve to commit changes or /decline to cancel")

            # Request final approval with summary
            approval_summary = f"""
SWARM OPERATION COMPLETE - READY FOR COMMIT

Summary:
- Task: {task}
- Review Decision: APPROVED
- Proposed Changes: {result.get("proposed_changes", "")[:500]}

Please review and approve via Telegram bot to proceed with git commit.

Commands:
- /approve - Commit and push changes
- /decline - Cancel without committing
- /retry - Request adjustments before commit
- /help - Show help
            """.strip()

            # Send final approval request
            integration.request_final_approval(
                chat_id=chat_id,
                user_id=user_id,
                summary=approval_summary,
                request_id=initial_state.get("telegram_request_id"),
            )

            print("\n✅ Final approval request sent to Telegram!")
            print("Waiting for user response...")

        else:
            print("\nℹ️ No Telegram configured for final approval")
            print("Proceeding with git commit without approval...")
            # TODO: Implement git commit here

    # If we're here and have a proposal, show it
    if result.get("proposed_changes"):
        print(f"\n--- PROPOSED DIFF ---\n{result['proposed_changes']}")

    #except Exception as e:
    #    print(f"\n❌ Error during swarm execution: {e}")
    #    import traceback
    
    #    traceback.print_exc()
# Synchronous wrapper for backward compatibility
def main_sync(task: str) -> None:
    """Synchronous wrapper that runs the async main function."""
    asyncio.run(main(task))


if __name__ == "__main__":
    asyncio.run(main("Update /help with icons in the message"))
