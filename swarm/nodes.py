from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
import os
import logging
from typing import Any, Dict, Optional

from swarm.mini_swe_agent import run_task_with_anti_drift, create_agent

# Configure logger
logger = logging.getLogger(__name__)

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
    """
    Use mini-swe-agent as CODE WRITER.
    Replaces LLM-based code writer with battle-tested mini-swe-agent.
    """
    task = state.get("current_task", "Write code changes")
    
    try:
        # Use mini-swe-agent to generate code changes
        diff = run_task_with_anti_drift(task, cwd="/home/steen/kurs-bot/swarm/")
        
        return {
            "proposed_changes": diff,
            "messages": state.get("messages", []) + [f"mini-swe-agent generated: {diff[:100]}..."],
            "source": "mini-swe-agent",
        }
    except Exception as e:
        # Fallback to LLM if mini-swe-agent fails
        logger.warning(f"mini-swe-agent failed, falling back to LLM: {e}")
        llm = get_cheap_llm()
        prompt = SystemMessage(
            content=SYSTEM_PROMPT + "\n\nYou are the Code Writer. Output ONLY a clean unified git diff for files inside swarm/. Do not add extra functions."
        )
        response = llm.invoke([prompt] + state.get("messages", []))
        return {
            "proposed_changes": response.content,
            "messages": state.get("messages", []) + [response],
            "source": "llm-fallback",
        }


def pre_commit_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    Run pre-commit checks after Code Writer.
    Auto-runs tests to verify changes don't break anything.
    """
    task = state.get("current_task", "Run pre-commit checks")
    
    try:
        # Run pre-commit checks
        import subprocess
        result = subprocess.run(
            ["npm", "test"],
            cwd="/home/steen/kurs-bot/swarm/",
            capture_output=True,
            text=True,
            timeout=60
        )
        
        success = result.returncode == 0
        
        feedback = result.stdout if success else result.stderr
        
        return {
            "pre_commit_result": "PASS" if success else "FAIL",
            "pre_commit_feedback": feedback[:500],  # Truncate for state
            "pre_commit_success": success,
            "iteration_count": state.get("iteration_count", 0) + 1,
            "messages": state.get("messages", []) + [f"Pre-commit: {result.returncode}"],
        }
    except subprocess.TimeoutExpired:
        return {
            "pre_commit_result": "TIMEOUT",
            "pre_commit_feedback": "Test timeout after 60s",
            "pre_commit_success": False,
            "iteration_count": state.get("iteration_count", 0) + 1,
            "messages": state.get("messages", []) + ["Pre-commit: TIMEOUT"],
        }
    except Exception as e:
        return {
            "pre_commit_result": "ERROR",
            "pre_commit_feedback": str(e)[:500],
            "pre_commit_success": False,
            "iteration_count": state.get("iteration_count", 0) + 1,
            "messages": state.get("messages", []) + [f"Pre-commit: ERROR - {e}"],
        }


def run_pre_commit_with_retry(state: dict[str, Any], max_retries: int = 3) -> dict[str, Any]:
    """
    Run pre-commit with automatic retry on failure.
    Loops back to Code Writer if tests fail.
    """
    iteration_count = state.get("iteration_count", 0)
    
    for attempt in range(max_retries):
        logger.info(f"Pre-commit attempt {attempt + 1}/{max_retries}")
        
        result = pre_commit_node(state)
        
        if result["pre_commit_success"]:
            logger.info("Pre-commit passed on attempt 1")
            return result
        
        logger.warning(f"Pre-commit failed on attempt {attempt + 1}, will retry...")
        
        # If we have retries left, loop back to Code Writer
        if attempt < max_retries - 1:
            # Update state with retry attempt
            state["iteration_count"] = iteration_count + 1
            state["pre_commit_attempts"] = attempt + 1
            state["messages"].append(f"Pre-commit attempt {attempt + 1} failed, retrying...")
    
    # All retries exhausted
    logger.error(f"All {max_retries} pre-commit attempts failed")
    return {
        "pre_commit_result": "FAILED_ALL_RETRIES",
        "pre_commit_feedback": "All retries exhausted",
        "pre_commit_success": False,
        "iteration_count": iteration_count,
        "pre_commit_attempts": max_retries,
        "messages": state.get("messages", []) + ["Pre-commit: FAILED_ALL_RETRIES"],
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
