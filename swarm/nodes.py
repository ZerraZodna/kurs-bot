from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
import os
from typing import Any

# === STRONG RULES (anti-drift) ===
SYSTEM_PROMPT = """You are a strict technical coding supervisor for the kurs-bot project.

IDENTITY: You are a coding supervisor. You do NOT generate spiritual content, ACIM, Enneagram, greetings, blessings, or any non-technical code.

PURPOSE: Your ONLY job is to plan, write, and review pure Python/LangGraph technical code **inside the swarm/ folder only**.

RULES YOU MUST OBEY:
- ONLY create or modify files inside the swarm/ folder.
- Keep changes MINIMAL. Do not add extra functions or tests unless explicitly asked.
- Never generate TypeScript or non-Python code.
- Output ONLY a clean unified git diff when writing code.
- If the task is simple, do not over-engineer it.
- Enforce all rules strictly."""


def get_strong_llm():
    return ChatOpenAI(
        base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:8080/v1"),
        api_key=os.getenv("OPENAI_API_KEY", "local"),
        model=os.getenv("OPENAI_MODEL", "qwen2.5:7b-instruct-q4_K_M"),  # ← your choice
        temperature=0.0,
    )


def get_cheap_llm():
    return ChatOpenAI(
        base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:8080/v1"),
        api_key=os.getenv("OPENAI_API_KEY", "local"),
        model=os.getenv("OPENAI_MODEL", "qwen2.5:7b-instruct-q4_K_M"),  # ← your choice
        temperature=0.1,
    )


def architect_node(state: dict[str, Any]) -> dict[str, Any]:
    llm = get_strong_llm()
    prompt = SystemMessage(
        content=SYSTEM_PROMPT + "\n\nYou are the Architect. Break the task into 1-3 minimal subtasks. Be very concise."
    )
    response = llm.invoke([prompt] + state.get("messages", []))
    return {
        "subtasks": [response.content],
        "messages": state.get("messages", []) + [response],
        "current_task": state.get("current_task"),
    }


def code_writer_node(state: dict[str, Any]) -> dict[str, Any]:
    llm = get_cheap_llm()
    prompt = SystemMessage(
        content=SYSTEM_PROMPT
        + "\n\nYou are the Code Writer. Output ONLY a clean unified git diff for files inside swarm/. Do not add extra functions."
    )
    response = llm.invoke([prompt] + state.get("messages", []))
    return {
        "proposed_changes": response.content,
        "messages": state.get("messages", []) + [response],
    }


def reviewer_node(state: dict[str, Any]) -> dict[str, Any]:
    llm = get_strong_llm()
    prompt = SystemMessage(
        content=SYSTEM_PROMPT
        + "\n\nYou are the Reviewer. Be strict. Reply with APPROVE if the change is minimal, technical, and only inside swarm/. Otherwise reply with REJECT and list violations."
    )
    response = llm.invoke([prompt] + state.get("messages", []))
    decision = "APPROVE" if "APPROVE" in response.content.upper() else "REJECT"
    return {
        "review_feedback": response.content,
        "final_decision": decision,
        "iteration_count": state.get("iteration_count", 0) + 1,
        "messages": state.get("messages", []) + [response],
    }
