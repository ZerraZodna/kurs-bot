"""
Tests to verify that the approval workflow properly blocks and waits for user response.
"""

import pytest


class TestApprovalBlockingBehavior:
    """Tests for approval blocking behavior."""

    def test_workflow_blocks_on_approval(self):
        """Test that the workflow properly blocks when awaiting approval."""
        with open("/home/steen/kurs-bot/swarm/graph.py", "r") as f:
            content = f.read()

        # The workflow should await the approval hook
        # This means it will BLOCK until the user responds
        assert "await hook_request_prompt_approval" in content, \
            "Workflow should await approval to block until user responds"

        # Verify functions are async
        assert "async def request_prompt_approval" in content, \
            "request_prompt_approval should be async to use await"

    def test_workflow_blocks_on_final_approval(self):
        """Test that final approval also blocks."""
        with open("/home/steen/kurs-bot/swarm/graph.py", "r") as f:
            content = f.read()

        assert "await hook_request_final_approval" in content, \
            "Final approval workflow should also await to block until user responds"
        
        assert "async def request_final_approval" in content, \
            "request_final_approval should be async to use await"

    def test_integration_blocks_on_approval(self):
        """Test that integration.py also blocks on approval."""
        with open("/home/steen/kurs-bot/swarm/telegram/integration.py", "r") as f:
            content = f.read()

        # The integration should await the coordinator.wait_for_approval
        assert "await coordinator.wait_for_approval" in content, \
            "Integration should await coordinator to block until approval received"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
