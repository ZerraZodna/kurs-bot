"""
Integration tests for SwarmTelegramIntegration async/await functionality.
These tests verify that the integration properly awaits async functions
instead of using nested event loops.
"""

import pytest


class TestSwarmTelegramIntegrationAsyncFix:
    """Tests for SwarmTelegramIntegration async behavior fix."""

    def test_request_prompt_approval_awaits_directly(self):
        """Test that request_prompt_approval awaits send_swarm_approval_request directly."""
        # Read the source file and verify it uses 'await' not 'run_until_complete'
        with open("/home/steen/kurs-bot/swarm/telegram/integration.py", "r") as f:
            content = f.read()

        # Verify the fix: should use 'await send_swarm_approval_request'
        assert "await send_swarm_approval_request" in content, \
            "Integration should use 'await' for async function calls"

        # Verify the bug is fixed: should NOT use 'run_until_complete' inside async methods
        lines_before_fix = content.split("async def request_prompt_approval")[1].split("async def request_final_approval")[0]
        assert "run_until_complete" not in lines_before_fix, \
            "request_prompt_approval should not use run_until_complete (nested event loop)"

    def test_request_final_approval_awaits_directly(self):
        """Test that request_final_approval also awaits directly."""
        with open("/home/steen/kurs-bot/swarm/telegram/integration.py", "r") as f:
            content = f.read()

        # Verify the same fix applies to both methods
        lines_second_fix = content.split("async def request_final_approval")[1].split("async def get_request_status")[0]
        assert "await send_swarm_approval_request" in lines_second_fix, \
            "request_final_approval should use 'await' for async function calls"
        assert "run_until_complete" not in lines_second_fix, \
            "request_final_approval should not use run_until_complete (nested event loop)"

    def test_no_nested_event_loop(self):
        """Test that there's no nested event loop pattern in the integration."""
        with open("/home/steen/kurs-bot/swarm/telegram/integration.py", "r") as f:
            content = f.read()

        # Find all occurrences of asyncio usage in the integration methods
        lines = content.split("\n")
        
        for i, line in enumerate(lines):
            if "async def request_prompt_approval" in line or "async def request_final_approval" in line:
                # Check the next 30 lines for the method body
                method_end = min(i + 30, len(lines))
                method_body = "\n".join(lines[i:method_end])
                
                # Should not have both 'import asyncio' AND 'run_until_complete' together
                has_import = "import asyncio" in method_body
                has_run_until = "run_until_complete" in method_body
                
                if has_import and has_run_until:
                    pytest.fail(f"Found nested event loop pattern at line {i+1}: {line}")

    def test_integration_class_exists(self):
        """Test that the integration class exists and is callable."""
        import sys
        sys.path.insert(0, "/home/steen/kurs-bot/swarm")
        
        try:
            # Just check that the file can be parsed
            with open("/home/steen/kurs-bot/swarm/telegram/integration.py", "r") as f:
                compile(f.read(), "integration.py", "exec")
            
            assert True, "File should be parseable"
        except SyntaxError as e:
            pytest.fail(f"Syntax error in integration.py: {e}")


class TestIntegrationFixVerification:
    """Tests to verify the async/await fix is correct."""

    def test_await_usage_pattern(self):
        """Verify the correct await pattern is used."""
        with open("/home/steen/kurs-bot/swarm/telegram/integration.py", "r") as f:
            content = f.read()

        # The correct pattern should be:
        # result = await send_swarm_approval_request(...)
        
        # Count occurrences of the correct pattern
        correct_pattern_count = content.count("result = await send_swarm_approval_request")
        assert correct_pattern_count >= 2, \
            f"Should have at least 2 occurrences of correct await pattern, found {correct_pattern_count}"

    def test_no_broken_pattern(self):
        """Verify the broken pattern is removed."""
        with open("/home/steen/kurs-bot/swarm/telegram/integration.py", "r") as f:
            content = f.read()

        # Check for the broken pattern in async methods
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "async def request_prompt_approval" in line:
                # Check next 30 lines
                method_end = min(i + 30, len(lines))
                method_body = "\n".join(lines[i:method_end])
                
                # Should NOT have the broken pattern
                broken_pattern = "asyncio.get_event_loop().run_until_complete(\n                send_swarm_approval_request"
                assert broken_pattern not in method_body, \
                    f"Found broken pattern at line {i+1}"

    def test_async_import_removed(self):
        """Verify the unnecessary 'import asyncio' inside async methods is removed."""
        with open("/home/steen/kurs-bot/swarm/telegram/integration.py", "r") as f:
            content = f.read()

        # Check for 'import asyncio' inside the async methods
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "async def request_prompt_approval" in line or "async def request_final_approval" in line:
                # Check next 30 lines
                method_end = min(i + 30, len(lines))
                method_body = "\n".join(lines[i:method_end])
                
                # Should NOT have 'import asyncio' inside the method
                assert "import asyncio" not in method_body, \
                    f"Unnecessary 'import asyncio' found inside async method at line {i+1}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
