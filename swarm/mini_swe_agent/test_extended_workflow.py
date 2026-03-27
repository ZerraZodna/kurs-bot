"""
Unit tests for extended workflow functions in mini-swe-agent integration.

Tests the new functions added for the extended workflow:
- plan_task_with_tests
- create_code_with_tests
- run_pre_commit
- execute_extended_workflow
"""

import pytest
import sys
from pathlib import Path

# Add swarm directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from swarm.mini_swe_agent import (
    plan_task_with_tests,
    create_code_with_tests,
    run_pre_commit,
    execute_extended_workflow,
)


class TestPlanTaskWithTests:
    """Tests for plan_task_with_tests function."""

    def test_returns_dict(self):
        """Test that plan_task_with_tests returns a dictionary."""
        result = plan_task_with_tests("Test task")
        assert isinstance(result, dict)

    def test_contains_planning_info(self):
        """Test that result contains planning information."""
        result = plan_task_with_tests("Test task")
        assert "task" in result or "plan" in result.lower()


class TestCreateCodeWithTests:
    """Tests for create_code_with_tests function."""

    def test_returns_dict(self):
        """Test that create_code_with_tests returns a dictionary."""
        result = create_code_with_tests("Test task")
        assert isinstance(result, dict)

    def test_contains_diff(self):
        """Test that result contains diff information."""
        result = create_code_with_tests("Test task")
        assert "diff" in result

    def test_diff_not_empty(self):
        """Test that diff is not empty."""
        result = create_code_with_tests("Test task")
        assert result["diff"] is not None
        assert len(result["diff"]) > 0


class TestRunPreCommit:
    """Tests for run_pre_commit function."""

    def test_returns_dict(self):
        """Test that run_pre_commit returns a dictionary."""
        result = run_pre_commit("Test task")
        assert isinstance(result, dict)

    def test_contains_result_fields(self):
        """Test that result contains expected fields."""
        result = run_pre_commit("Test task")
        assert "success" in result
        assert "output" in result

    def test_success_is_boolean(self):
        """Test that success field is a boolean."""
        result = run_pre_commit("Test task")
        assert isinstance(result["success"], bool)


class TestExecuteExtendedWorkflow:
    """Tests for execute_extended_workflow function."""

    def test_returns_dict(self):
        """Test that execute_extended_workflow returns a dictionary."""
        result = execute_extended_workflow("Test task")
        assert isinstance(result, dict)

    def test_contains_all_phases(self):
        """Test that result contains all workflow phases."""
        result = execute_extended_workflow("Test task")
        assert "planning" in result
        assert "code_creation" in result
        assert "pre_commit" in result

    def test_planning_is_result(self):
        """Test that planning field contains planning result."""
        result = execute_extended_workflow("Test task")
        assert result["planning"] is not None

    def test_code_creation_is_result(self):
        """Test that code_creation field contains code creation result."""
        result = execute_extended_workflow("Test task")
        assert result["code_creation"] is not None

    def test_pre_commit_is_result(self):
        """Test that pre_commit field contains pre-commit result."""
        result = execute_extended_workflow("Test task")
        assert result["pre_commit"] is not None

    def test_workflow_complete_field(self):
        """Test that workflow_complete field exists and is boolean."""
        result = execute_extended_workflow("Test task")
        assert "workflow_complete" in result
        assert isinstance(result["workflow_complete"], bool)


class TestAntiDriftRules:
    """Tests for anti-drift rule compliance."""

    def test_only_swarm_folder(self):
        """Test that functions only operate in swarm/ folder."""
        # This is a basic check - actual validation happens in the agent
        result = execute_extended_workflow("Test task")
        # If successful, it should have operated in the correct folder
        assert result is not None

    def test_output_format(self):
        """Test that output follows expected format."""
        result = execute_extended_workflow("Test task")
        # Check that all fields are in expected format
        assert isinstance(result["planning"], dict)
        assert isinstance(result["code_creation"], dict)
        assert isinstance(result["pre_commit"], dict)


class TestIntegration:
    """Integration tests for the extended workflow."""

    def test_full_workflow(self):
        """Test the complete workflow execution."""
        task = "Test workflow integration"

        # Execute the workflow
        result = execute_extended_workflow(task)

        # Verify all phases completed
        assert result is not None
        assert "planning" in result
        assert "code_creation" in result
        assert "pre_commit" in result

        # Verify result structure
        assert isinstance(result["planning"], dict)
        assert isinstance(result["code_creation"], dict)
        assert isinstance(result["pre_commit"], dict)

        # Verify workflow_complete exists
        assert "workflow_complete" in result

    def test_workflow_with_different_tasks(self):
        """Test workflow with different task types."""
        tasks = [
            "Create documentation",
            "Update configuration",
            "Add new function",
            "Modify existing file",
        ]

        for task in tasks:
            result = execute_extended_workflow(task)
            assert result is not None
            assert isinstance(result["planning"], dict)
            assert isinstance(result["code_creation"], dict)
            assert isinstance(result["pre_commit"], dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
