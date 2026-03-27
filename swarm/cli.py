#!/usr/bin/env python
"""CLI entry-point for the kurs-bot LangGraph coding supervisor."""

import sys

from dotenv import load_dotenv

load_dotenv()

from langgraph.checkpoint.memory import MemorySaver
from .graph import build_supervisor_graph


def main(task: str) -> None:
    memory = MemorySaver()
    supervisor_graph = build_supervisor_graph(memory)

    config = {"configurable": {"thread_id": f"cli-{hash(task) % 10000}"}}

    input_state = {
        "messages": [],
        "current_task": task,
        "subtasks": [],
        "proposed_changes": "",
        "review_feedback": "",
        "final_decision": "",
        "iteration_count": 0,
    }

    print("=" * 60)
    print("  KURS-BOT SWARM CODING SUPERVISOR")
    print("  (Technical code only — no spiritual content)")
    print("=" * 60)
    print(f"\nTask: {task}\n")
    print("Running architect → code_writer → reviewer cycle...\n")

    result = supervisor_graph.invoke(input_state, config)

    decision = result.get("final_decision", "NO DECISION")
    iterations = result.get("iteration_count", 0)

    print("=" * 60)
    print(f"  DECISION: {decision}  (after {iterations} iteration(s))")
    print("=" * 60)

    # --- Review feedback ---
    feedback = result.get("review_feedback", "")
    if feedback:
        print(f"\n--- REVIEWER FEEDBACK ---\n{feedback}")

    # --- Proposed diff ---
    changes = result.get("proposed_changes", "")
    if changes:
        print(f"\n--- PROPOSED DIFF ---\n{changes}")

    # --- Last 3 node messages ---
    messages = result.get("messages", [])
    if messages:
        print("\n--- NODE MESSAGES (last 3) ---")
        for msg in messages[-3:]:
            content = msg.get("content", "")
            # Truncate long messages for readability
            preview = content[:500] + ("..." if len(content) > 500 else "")
            print(f"\n  [{msg.get('role', '?')}]:\n  {preview}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print('Usage: python -m swarm.cli "Your test task description"')
        sys.exit(1)
    main(sys.argv[1])
