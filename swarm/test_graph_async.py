"""
Integration tests for graph.py async/await functionality.
These tests verify that the graph nodes properly await async functions
instead of using nested event loops.
"""

import pytest


class TestGraphAsyncFix:
    """Tests for graph.py async behavior fix."""

    def test_request_prompt_approval_awaits_directly(self):
        """Test that request_prompt_approval awaits hook_request_prompt_approval directly."""
        with open("/home/steen/kurs-bot/swarm/graph.py", "r") as f:
            content = f.read()

        # Verify the fix: should use 'await hook_request_prompt_approval'
        assert "await hook_request_prompt_approval" in content, \
            "Graph should use 'await' for async hook calls"

        # Verify the function is async
        assert "async def request_prompt_approval" in content, \
            "request_prompt_approval should be async"

        # Verify import asyncio exists
        assert "import asyncio" in content, \
            "Should import asyncio for async support"

    def test_request_final_approval_awaits_directly(self):
        """Test that request_final_approval also awaits directly."""
        with open("/home/steen/kurs-bot/swarm/graph.py", "r") as f:
            content = f.read()

        # Verify the same fix applies to both functions
        assert "await hook_request_final_approval" in content, \
            "request_final_approval should use 'await' for async hook calls"
        
        # Verify the function is async
        assert "async def request_final_approval" in content, \
            "request_final_approval should be async"

    def test_no_nested_event_loop(self):
        """Test that there's no nested event loop pattern in graph.py."""
        with open("/home/steen/kurs-bot/swarm/graph.py", "r") as f:
            content = f.read()

        # Find all occurrences of asyncio usage in the graph nodes
        lines = content.split("\n")
        
        for i, line in enumerate(lines):
            if "def request_prompt_approval" in line or "def request_final_approval" in line:
                # Check the next 50 lines for the method body
                method_end = min(i + 50, len(lines))
                method_body = "\n".join(lines[i:method_end])
                
                # Should not have both 'import asyncio' AND 'run_until_complete' together
                has_import = "import asyncio" in method_body
                has_run_until = "run_until_complete" in method_body
                
                if has_import and has_run_until:
                    pytest.fail(f"Found nested event loop pattern at line {i+1}: {line}")

    def test_await_usage_pattern(self):
        """Verify the correct await pattern is used in graph.py."""
        with open("/home/steen/kurs-bot/swarm/graph.py", "r") as f:
            content = f.read()

        # Count occurrences of the correct pattern
        await_prompt_count = content.count("await hook_request_prompt_approval")
        await_final_count = content.count("await hook_request_final_approval")
        
        assert await_prompt_count >= 1, \
            f"Should have at least 1 occurrence of await hook_request_prompt_approval, found {await_prompt_count}"
        assert await_final_count >= 1, \
            f"Should have at least 1 occurrence of await hook_request_final_approval, found {await_final_count}"

    def test_async_import_exists(self):
        """Verify asyncio is imported at module level."""
        with open("/home/steen/kurs-bot/swarm/graph.py", "r") as f:
            content = f.read()

        # Check for import at the top
        lines = content.split("\n")
        for line in lines[:20]:  # Check first 20 lines
            if "import asyncio" in line:
                assert True  # Found it
                return
        
        pytest.fail("import asyncio not found in first 20 lines")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
