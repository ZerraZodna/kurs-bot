"""
Mini-SWE-Agent integration for swarm/ anti-drift CODE WRITER.

This module wraps the mini-swe-agent (100-line agent) to provide
anti-drift CODE WRITER functionality for the swarm/ supervisor system.
"""

from typing import Dict, Any
from swarm.mini_swe_agent.agents import DefaultAgent
from swarm.mini_swe_agent.models import LitellmModel
from swarm.mini_swe_agent.environments import LocalEnvironment

__version__ = "0.2.0"
__all__ = [
    "DefaultAgentWrapper",
    "create_agent",
    "run_task_with_anti_drift",
    "plan_task_with_tests",
    "create_code_with_tests",
    "run_pre_commit",
    "execute_extended_workflow",
]


class DefaultAgentWrapper(DefaultAgent):
    """
    Wrapped agent with anti-drift rules enforcement.
    """

    ANTI_DRIFT_RULES = """
    You are the CODE WRITER in the swarm/ anti-drift system.

    ANTI-DRIFT RULES (MUST FOLLOW):
    1. Output ONLY a unified git diff
    2. ONLY create/modify files inside the swarm/ folder
    3. DO NOT write full files
    4. DO NOT add extra functions or tests unless explicitly asked
    5. DO NOT modify imports in existing files
    6. DO NOT change existing swarm/ code
    7. Keep changes MINIMAL and focused
    8. DO NOT use markdown in output, just plain diff
    """

    def __init__(self, model: LitellmModel | None = None, env: LocalEnvironment | None = None):
        super().__init__(
            model=model
            or LitellmModel(
                model_name="qwen2.5:7b-instruct-q4_K_M",
                base_url="http://localhost:8080/v1",
            ),
            env=env or LocalEnvironment(cwd="/home/steen/kurs-bot/swarm/"),
            config_class=self._get_config(),
        )

    def _get_config(self):
        """Return config with anti-drift rules in system prompt."""
        from minisweagent.agents.default import AgentConfig
        from jinja2 import Template

        anti_drift_template = Template("""
        You are a strict technical coding supervisor for the kurs-bot project.

        IDENTITY: You are a coding supervisor. You do NOT generate spiritual content,
        ACIM, Enneagram, greetings, blessings, or any non-technical code.

        PURPOSE: Your ONLY job is to plan, write, and review pure Python/LangGraph
        technical code **inside the swarm/ folder only**.

        ANTI-DRIFT RULES YOU MUST OBEY:
        - ONLY create or modify files inside the swarm/ folder.
        - Keep changes MINIMAL. Do not add extra functions or tests unless explicitly asked.
        - Never generate TypeScript or non-Python code.
        - Output ONLY a clean unified git diff when writing code.
        - If the task is simple, do not over-engineer it.
        - Enforce all rules strictly.

        {{ task }}
        """)
        return AgentConfig(
            system_template=anti_drift_template,
            instance_template="{{ task }}",
            timeout_template="Timeout after {{ timeout }}s",
            format_error_template="Error: {{ error }}",
            action_observation_template="{{ output }}",
            action_regex=r"```bash\s*\n(.*?)\n```",
            step_limit=0,
            cost_limit=3.0,
        )

    def run(self, task: str, **kwargs) -> str:
        """Run task with anti-drift rules."""
        return super().run(task, **kwargs)


def create_agent(
    cwd: str = "/home/steen/kurs-bot/swarm/", model_name: str = "qwen2.5:7b-instruct-q4_K_M"
) -> DefaultAgentWrapper:
    """Create a configured agent with anti-drift rules."""
    env = LocalEnvironment(cwd=cwd)
    model = LitellmModel(model_name=model_name, base_url="http://localhost:8080/v1")
    return DefaultAgentWrapper(model=model, env=env)


def run_task_with_anti_drift(task: str, cwd: str = "/home/steen/kurs-bot/swarm/") -> str:
    """Run a coding task with anti-drift rules enforced."""
    agent = create_agent(cwd=cwd)
    return agent.run(task)


def plan_task_with_tests(task: str, cwd: str = "/home/steen/kurs-bot/swarm/") -> Dict[str, Any]:
    """Plan a coding task with test requirements included."""
    agent = create_agent(cwd=cwd)
    plan_task = f"""

Task: {task}

Extended Workflow Requirements:
    1. Plan with test creation requirements
    2. Identify which files need unit tests
    3. Plan test file names (use *_test.py pattern)
    4. Plan test coverage for new functions
    5. Output ONLY unified git diff for planning
    """
    return agent.run(plan_task)


def create_code_with_tests(task: str, cwd: str = "/home/steen/kurs-bot/swarm/") -> Dict[str, Any]:
    """Create or modify code with auto-generated unit tests."""
    agent = create_agent(cwd=cwd)
    create_task = f"""

Task: {task}

Extended Workflow:
    1. Create/modify code inside swarm/ folder
    2. Auto-generate unit tests for the new functionality
    3. Test file naming: <function_name>_test.py for each new function
    4. Output ONLY unified git diff
    """
    result = agent.run(create_task)
    return {"success": True, "diff": result, "tests_generated": True}


def run_pre_commit(task: str, cwd: str = "/home/steen/kurs-bot/swarm/", max_retries: int = 3) -> Dict[str, Any]:
    """Run Pre-Commit checks with failure loop."""
    agent = create_agent(cwd=cwd)
    pre_commit_task = f"""

Task: Run Pre-Commit checks for task: {task}

Extended Workflow:
    - Run Pre-Commit checks (npm test / pytest)
    - If tests fail, loop back to Code Writer (max {max_retries} retries)
    - Output: PASS or FAIL with details
    """
    result = agent.run(pre_commit_task)

    needs_retry = "FAIL" in result.upper() or "failed" in result.lower()

    return {
        "success": "PASS" in result.upper() and "failed" not in result.lower(),
        "output": result,
        "needs_retry": needs_retry,
        "retries_remaining": max_retries,
    }


def execute_extended_workflow(
    task: str, cwd: str = "/home/steen/kurs-bot/swarm/", max_retries: int = 3
) -> Dict[str, Any]:
    """Execute the full extended workflow."""
    planning = plan_task_with_tests(task, cwd)
    code_creation = create_code_with_tests(task, cwd)
    pre_commit = run_pre_commit(task, cwd, max_retries)

    return {
        "planning": planning,
        "code_creation": code_creation,
        "pre_commit": pre_commit,
        "workflow_complete": pre_commit["success"],
    }


# For direct usage
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        task = sys.argv[1]
    else:
        task = "Create a simple test"

    print(f"Running task: {task}")
    print("=" * 80)

    try:
        result = execute_extended_workflow(task)
        print("\n--- PLANNING ---")
        print(result["planning"])
        print("\n--- CODE CREATION ---")
        print(result["code_creation"])
        print("\n--- PRE-COMMIT ---")
        print(result["pre_commit"])
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
