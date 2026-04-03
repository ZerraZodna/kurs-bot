"""
Tests to verify CLI properly handles async graph execution.
"""

import pytest


class TestCLIAsyncBehavior:
    """Tests for CLI async behavior."""

    def test_main_function_is_async(self):
        """Test that main function is async."""
        with open("/home/steen/kurs-bot/swarm/cli.py", "r") as f:
            content = f.read()

        assert "async def main" in content, \
            "main function should be async to support async graph execution"

    def test_request_swarm_approval_is_async(self):
        """Test that request_swarm_approval is async."""
        with open("/home/steen/kurs-bot/swarm/cli.py", "r") as f:
            content = f.read()

        assert "async def request_swarm_approval" in content, \
            "request_swarm_approval should be async"

    def test_ainvoke_used(self):
        """Test that ainvoke is used instead of invoke."""
        with open("/home/steen/kurs-bot/swarm/cli.py", "r") as f:
            content = f.read()

        assert "await graph.ainvoke" in content, \
            "Should use await graph.ainvoke for async graph execution"
        
        # Make sure sync invoke is not used in actual code (not comments)
        assert 'result = graph.invoke(' not in content, \
            "Should not use sync graph.invoke()"

    def test_asyncio_import_exists(self):
        """Test that asyncio is imported."""
        with open("/home/steen/kurs-bot/swarm/cli.py", "r") as f:
            content = f.read()

        assert "import asyncio" in content, \
            "Should import asyncio for async support"

    def test_asyncio_run_entry_point(self):
        """Test that entry point uses asyncio.run."""
        with open("/home/steen/kurs-bot/swarm/cli.py", "r") as f:
            content = f.read()

        assert "asyncio.run(main" in content, \
            "Entry point should use asyncio.run(main(...))"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
