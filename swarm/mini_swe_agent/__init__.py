"""
Mini-SWE-Agent integration for swarm/ anti-drift CODE WRITER.

This module wraps the mini-swe-agent (100-line agent) to provide
anti-drift CODE WRITER functionality for the swarm/ supervisor system.
"""

from typing import Optional, Dict, Any
from minisweagent.agents.default import DefaultAgent
from minisweagent.models.litellm_model import LitellmModel
from minisweagent.environments.local import LocalEnvironment

__version__ = "0.1.0"
__all__ = ["DefaultAgentWrapper", "create_agent", "run_task_with_anti_drift"]


class DefaultAgentWrapper(DefaultAgent):
    """
    Wrapped agent with anti-drift rules enforcement.
    
    Enforces swarm/ folder scoping and minimal changes.
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
    
    If you violate any rule, the REVIEWER will reject you.
    """
    
    def __init__(self, model: Optional[LitellmModel] = None, env: Optional[LocalEnvironment] = None):
        super().__init__(
            model=model or LitellmModel(
                model_name="qwen2.5:7b-instruct-q4_K_M",
                base_url="http://localhost:8080/v1",
            ),
            env=env or LocalEnvironment(cwd="/home/steen/kurs-bot/swarm/"),
            config_class=self._get_config()
        )
    
    def _get_config(self):
        """Return config with anti-drift rules in system prompt."""
        from minisweagent.agents.default import AgentConfig
        from jinja2 import Template
        
        # Override system template with anti-drift rules
        anti_drift_template = """
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
        """
        
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
        """
        Run task with anti-drift rules.
        
        Returns the unified git diff output.
        """
        return super().run(task, **kwargs)


def create_agent(cwd: str = "/home/steen/kurs-bot/swarm/", model_name: str = "qwen2.5:7b-instruct-q4_K_M") -> DefaultAgentWrapper:
    """
    Create a configured agent with anti-drift rules.
    
    Args:
        cwd: Working directory (default: swarm/ folder)
        model_name: LLM model name (default: Qwen)
    
    Returns:
        Configured DefaultAgentWrapper instance
    """
    return DefaultAgentWrapper()


def run_task_with_anti_drift(task: str, cwd: str = "/home/steen/kurs-bot/swarm/") -> str:
    """
    Run a coding task with anti-drift rules enforced.
    
    This is the main entry point for using mini-swe-agent as the CODE WRITER
    in the swarm/ supervisor workflow.
    
    Args:
        task: Task description to execute
        cwd: Working directory (default: swarm/ folder)
    
    Returns:
        Unified git diff output
    
    Example:
        >>> diff = run_task_with_anti_drift("Add anti-drift documentation")
        >>> print(diff)
    """
    agent = create_agent(cwd=cwd)
    return agent.run(task)


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
        diff = run_task_with_anti_drift(task)
        print("\n--- OUTPUT ---")
        print(diff)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
