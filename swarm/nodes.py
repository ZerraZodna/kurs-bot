from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
import os
import logging
from typing import Any


def read_file_content(file_path: str) -> str:
    """Read file content from the swarm directory using subprocess."""
    try:
        import subprocess
        result = subprocess.run(
            [f"cat {file_path}"],
            cwd=SWARM_CWD,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return result.stdout
        else:
            return f"Error reading file: {result.stderr}"
    except subprocess.TimeoutExpired:
        return "Error: File read timed out"
    except Exception as e:
        return f"Error reading file: {e}"

# Get working directory from environment or default
SWARM_CWD = os.getenv("SWARM_CWD", "/home/steen/kurs-bot/swarm/")

from swarm.mini_swe_agent import run_task_with_anti_drift

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
    """Get the strong LLM for architect and reviewer nodes."""
    return ChatOpenAI(
        base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:8080/v1"),
        api_key=os.getenv("OPENAI_API_KEY", "local"),
        model=os.getenv("OPENAI_MODEL", "Qwen3.5-9B-UD-Q4_K_XL"),
        temperature=0.0,
        streaming=False,
    )


def get_cheap_llm():
    """Get the cheap LLM for code writer fallback."""
    return ChatOpenAI(
        base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:8080/v1"),
        api_key=os.getenv("OPENAI_API_KEY", "local"),
        model=os.getenv("OPENAI_MODEL", "Qwen3.5-9B-UD-Q4_K_XL"),
        temperature=0.1,
        streaming=False,
    )


def architect_node(state: dict[str, Any]) -> dict[str, Any]:
    print("=" * 80)
    print("[DEBUG] ARCHITECT NODE STARTED")
    print(f"[DEBUG] State keys: {state.keys()}")
    print(f"[DEBUG] Current task: {state.get('current_task')}")
    
    # Try to read existing files if task mentions specific files
    task = state.get("current_task", "")
    print("[DEBUG] Trying to read existing files...")
    files_to_read = []
    if "/help" in task.lower():
        print("[DEBUG] Task mentions /help, looking for help-related files...")
        files_to_read = ["swarm/swarm/help.py"]
    
    # Read files if needed
    for file_path in files_to_read:
        print(f"[DEBUG] Executing: cat {file_path}")
        try:
            file_content = read_file_content(file_path)
            print(f"[DEBUG] File read successfully ({len(file_content)} chars)")
            print(f"[DEBUG] File preview: {file_content[:500]}...")
        except Exception as e:
            print(f"[DEBUG] File read error: {e}")
    
    llm = get_strong_llm()
    print("[DEBUG] LLM retrieved")
    prompt = SystemMessage(
        content=SYSTEM_PROMPT + "\n\nYou are the Architect. Break the task into 1-3 minimal subtasks. Be very concise."
    )
    print("[DEBUG] System prompt created")
    response = llm.invoke([prompt] + state.get("messages", []))
    print("[DEBUG] LLM response received")
    
    # Show ENTIRE response
    full_response = str(response.content)
    print(f"[DEBUG] FULL RESPONSE ({len(full_response)} chars):")
    print(full_response)
    
    return {
        "subtasks": [full_response],
        "messages": state.get("messages", []) + [response],
        "current_task": state.get("current_task"),
    }


def code_writer_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    Use mini-swe-agent as CODE WRITER.
    Replaces LLM-based code writer with battle-tested mini-swe-agent.
    """
    print("[DEBUG] CODE_WRITER NODE STARTED")
    task = state.get("current_task", "Write code changes")
    print(f"[DEBUG] Task: {task}")

    # Use mini-swe-agent to generate code changes
    print("[DEBUG] Calling run_task_with_anti_drift()...")
    import time
    start_time = time.time()
    diff = run_task_with_anti_drift(task, cwd=SWARM_CWD)
    elapsed = time.time() - start_time
    print(f"[DEBUG] run_task_with_anti_drift() completed in {elapsed:.2f}s")
    print(f"[DEBUG] Diff length: {len(diff)} chars")
    print(f"[DEBUG] Diff preview: {diff[:200]}...")

    return {
        "proposed_changes": diff,
        "messages": state.get("messages", []) + [f"mini-swe-agent generated: {diff[:100]}..."],
        "source": "mini-swe-agent",
    }

def pre_commit_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    Run pre-commit checks after Code Writer.
    Auto-runs tests to verify changes don't break anything.
    """
    print("[DEBUG] PRE_COMMIT NODE STARTED")
    current_task = state.get("current_task", "Run pre-commit checks")
    _ = current_task  # Keep variable for reference
    print(f"[DEBUG] Current task: {current_task}")

    try:
        # Run pre-commit checks
        import subprocess

        print("[DEBUG] Running npm test...")
        result = subprocess.run(["npm", "test"], cwd=SWARM_CWD, capture_output=True, text=True, timeout=60)
        print(f"[DEBUG] npm test return code: {result.returncode}")
        print(f"[DEBUG] npm test stdout length: {len(result.stdout)}")
        print(f"[DEBUG] npm test stderr length: {len(result.stderr)}")

        success = result.returncode == 0
        feedback = result.stdout if success else result.stderr

        print(f"[DEBUG] Pre-commit result: {'PASS' if success else 'FAIL'}")
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
    print("[DEBUG] REVIEWER NODE STARTED")
    print(f"[DEBUG] State keys: {state.keys()}")
    print(f"[DEBUG] Proposed changes length: {len(state.get('proposed_changes', ''))}")
    print(f"[DEBUG] Proposed changes preview: {state.get('proposed_changes', '')[:200]}...")
    
    llm = get_strong_llm()
    print("[DEBUG] LLM retrieved")
    prompt = SystemMessage(
        content=SYSTEM_PROMPT
        + "\n\nYou are the Reviewer. Be strict. Reply with APPROVE if the change is minimal, technical, and only inside swarm/. Otherwise reply with REJECT and list violations."
    )
    print("[DEBUG] System prompt created")
    response = llm.invoke([prompt] + state.get("messages", []))
    print("[DEBUG] LLM response received")
    print(f"[DEBUG] Decision: {response.content}")
    decision = "APPROVE" if "APPROVE" in response.content.upper() else "REJECT"
    print(f"[DEBUG] Normalized decision: {decision}")
    return {
        "review_feedback": response.content,
        "final_decision": decision,
        "iteration_count": state.get("iteration_count", 0) + 1,
        "messages": state.get("messages", []) + [response],
    }
