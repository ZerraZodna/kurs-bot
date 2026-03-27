#!/usr/bin/env python
"""CLI entry-point for the kurs-bot LangGraph coding supervisor."""

import sys
from dotenv import load_dotenv

load_dotenv()

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from .graph import build_supervisor_graph


def main(task: str) -> None:
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
    }

    print("=" * 80)
    print("   KURS-BOT SWARM CODING SUPERVISOR")
    print("   (Technical only — no spiritual content)")
    print("=" * 80)
    print(f"\nTask: {task}\n")
    print("Running architect → code_writer → reviewer cycle...\n")
    print("Step 1/3: Architect planning...")
    print("Step 2/3: Code writer generating...")

    result = graph.invoke(initial_state, config)

    print("=" * 80)
    print(f"FINAL DECISION: {result.get('final_decision', 'UNKNOWN')}")
    print("=" * 80)
    print("Step 3/3: Review complete!")
    print("\n📝 Reviewer feedback:", "✅ Approved" if result.get("final_decision") == "APPROVE" else "❌ Rejected")
    print("\n✅ Task completed successfully!")

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


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print('Usage: python -m swarm.cli "Your test task description"')
        sys.exit(1)
    main(sys.argv[1])
