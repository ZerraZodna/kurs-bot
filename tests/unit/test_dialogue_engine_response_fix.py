"""
Test that verifies the fix for the response parsing bug in dialogue_engine.py.
This test ensures that only the response_text is returned, not the full JSON.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.functions.executor import BatchExecutionResult, ExecutionResult


class TestDialogueEngineResponseFix:
    """Test that dialogue_engine returns parsed response text, not raw JSON."""
    
    @pytest.mark.asyncio
    async def test_generate_llm_response_returns_parsed_text(self):
        """Test that _generate_llm_response returns only the response text."""
        from src.services.dialogue_engine import DialogueEngine
        
        # Mock the database session
        mock_session = MagicMock()
        mock_user = MagicMock()
        mock_user.user_id = 123
        mock_user.is_deleted = False
        mock_user.processing_restricted = False
        mock_user.opted_in = True
        mock_user.channel = "telegram"
        
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_user
        
        # Create engine with mocked dependencies
        with patch('src.services.dialogue_engine.MemoryManager') as mock_mm:
            with patch('src.services.dialogue_engine.PromptBuilder') as mock_pb:
                with patch('src.services.dialogue_engine.get_semantic_search_service') as mock_ss:
                    with patch('src.services.dialogue_engine.call_ollama') as mock_call_ollama:
                        with patch('src.triggers.triggering.handle_triggers') as mock_triggers:
                            # Setup mocks
                            mock_mm_instance = MagicMock()
                            mock_mm.return_value = mock_mm_instance
                            mock_mm_instance.get_memory.return_value = []
                            
                            mock_pb_instance = MagicMock()
                            mock_pb.return_value = mock_pb_instance
                            mock_pb_instance.build_prompt.return_value = "test prompt"
                            
                            mock_ss_instance = MagicMock()
                            mock_ss.return_value = mock_ss_instance
                            mock_ss_instance.search_memories.return_value = []
                            
                            # This is the key: LLM returns JSON with response and functions
                            raw_llm_response = '''{
  "response": "Your goal, Dev, is to remember that your thoughts are images you've made.",
  "functions": [
    {"name": "extract_memory", "parameters": {"key": "goal", "value": "spiritual growth"}}
  ]
}'''
                            mock_call_ollama.return_value = raw_llm_response
                            
                            # Mock handle_triggers to return proper diagnostics with execution_result
                            mock_execution_result = BatchExecutionResult(
                                results=[
                                    ExecutionResult(
                                        function_name="extract_memory",
                                        success=True,
                                        result={"key": "goal", "value": "spiritual growth", "ok": True},
                                    )
                                ],
                                all_succeeded=True,
                                total_execution_time_ms=10.0,
                            )
                            mock_triggers.return_value = {
                                "structured_intent_used": True,
                                "dispatched_actions": ["extract_memory"],
                                "execution_result": mock_execution_result,
                            }
                            
                            # Create engine and call the method
                            engine = DialogueEngine(mock_session)
                            engine.memory_manager = mock_mm_instance
                            engine.prompt_builder = mock_pb_instance
                            
                            # Mock the onboarding service
                            engine.onboarding = MagicMock()
                            engine.onboarding.should_show_onboarding.return_value = False
                            
                            result = await engine._generate_llm_response(
                                user_id=123,
                                text="What is my goal?",
                                session=mock_session,
                                user_lang="en",
                                use_rag=False,
                                include_history=True,
                                history_turns=4,
                                include_lesson=True,
                            )
                            
                            # The result should combine AI response with function results
                            expected_text = "Your goal, Dev, is to remember that your thoughts are images you've made.\n\n✓ Remembered: goal"
                            assert result == expected_text, f"Expected: {expected_text}\nGot: {result}"
                            
                            # Verify handle_triggers was called with the raw response (for function processing)
                            mock_triggers.assert_called_once()
                            call_args = mock_triggers.call_args
                            assert call_args[1]['response'] == raw_llm_response
    
    @pytest.mark.asyncio
    async def test_generate_llm_response_handles_plain_text(self):
        """Test that _generate_llm_response handles plain text responses (no JSON)."""
        from src.services.dialogue_engine import DialogueEngine
        
        mock_session = MagicMock()
        mock_user = MagicMock()
        mock_user.user_id = 123
        mock_user.is_deleted = False
        mock_user.processing_restricted = False
        mock_user.opted_in = True
        mock_user.channel = "telegram"
        
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_user
        
        with patch('src.services.dialogue_engine.MemoryManager') as mock_mm:
            with patch('src.services.dialogue_engine.PromptBuilder') as mock_pb:
                with patch('src.services.dialogue_engine.get_semantic_search_service') as mock_ss:
                    with patch('src.services.dialogue_engine.call_ollama') as mock_call_ollama:
                        with patch('src.triggers.triggering.handle_triggers') as mock_triggers:
                            # Setup mocks
                            mock_mm_instance = MagicMock()
                            mock_mm.return_value = mock_mm_instance
                            mock_mm_instance.get_memory.return_value = []
                            
                            mock_pb_instance = MagicMock()
                            mock_pb.return_value = mock_pb_instance
                            mock_pb_instance.build_prompt.return_value = "test prompt"
                            
                            mock_ss_instance = MagicMock()
                            mock_ss.return_value = mock_ss_instance
                            mock_ss_instance.search_memories.return_value = []
                            
                            # Plain text response (no JSON)
                            plain_response = "This is a plain text response without any JSON."
                            mock_call_ollama.return_value = plain_response
                            
                            # Mock handle_triggers to return empty execution result (no functions executed)
                            mock_triggers.return_value = {
                                "structured_intent_used": False,
                                "dispatched_actions": [],
                            }
                            
                            # Create engine
                            engine = DialogueEngine(mock_session)
                            engine.memory_manager = mock_mm_instance
                            engine.prompt_builder = mock_pb_instance
                            engine.onboarding = MagicMock()
                            engine.onboarding.should_show_onboarding.return_value = False
                            
                            result = await engine._generate_llm_response(
                                user_id=123,
                                text="Hello",
                                session=mock_session,
                                user_lang="en",
                                use_rag=False,
                                include_history=True,
                                history_turns=4,
                                include_lesson=True,
                            )
                            
                            # Should return the plain text as-is
                            assert result == plain_response
    
    @pytest.mark.asyncio
    async def test_generate_llm_response_handles_empty_response(self):
        """Test that _generate_llm_response handles empty/None responses gracefully."""
        from src.services.dialogue_engine import DialogueEngine
        
        mock_session = MagicMock()
        mock_user = MagicMock()
        mock_user.user_id = 123
        mock_user.is_deleted = False
        mock_user.processing_restricted = False
        mock_user.opted_in = True
        mock_user.channel = "telegram"
        
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_user
        
        with patch('src.services.dialogue_engine.MemoryManager') as mock_mm:
            with patch('src.services.dialogue_engine.PromptBuilder') as mock_pb:
                with patch('src.services.dialogue_engine.get_semantic_search_service') as mock_ss:
                    with patch('src.services.dialogue_engine.call_ollama') as mock_call_ollama:
                        with patch('src.triggers.triggering.handle_triggers') as mock_triggers:
                            # Setup mocks
                            mock_mm_instance = MagicMock()
                            mock_mm.return_value = mock_mm_instance
                            mock_mm_instance.get_memory.return_value = []
                            
                            mock_pb_instance = MagicMock()
                            mock_pb.return_value = mock_pb_instance
                            mock_pb_instance.build_prompt.return_value = "test prompt"
                            
                            mock_ss_instance = MagicMock()
                            mock_ss.return_value = mock_ss_instance
                            mock_ss_instance.search_memories.return_value = []
                            
                            # None response from LLM
                            mock_call_ollama.return_value = None
                            
                            # Mock handle_triggers to return empty execution result
                            mock_triggers.return_value = {
                                "structured_intent_used": False,
                                "dispatched_actions": [],
                            }
                            
                            # Create engine
                            engine = DialogueEngine(mock_session)
                            engine.memory_manager = mock_mm_instance
                            engine.prompt_builder = mock_pb_instance
                            engine.onboarding = MagicMock()
                            engine.onboarding.should_show_onboarding.return_value = False
                            
                            result = await engine._generate_llm_response(
                                user_id=123,
                                text="Hello",
                                session=mock_session,
                                user_lang="en",
                                use_rag=False,
                                include_history=True,
                                history_turns=4,
                                include_lesson=True,
                            )
                            
                            # Should return the placeholder text
                            assert result == "[No response from LLM]"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
