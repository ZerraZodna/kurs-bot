"""
Test to verify that greeting responses with empty functions array
are correctly parsed and only the response text is sent to Telegram.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.functions.intent_parser import IntentParser, ParseResult, get_intent_parser
from src.functions.response_builder import ResponseBuilder, get_response_builder
from src.functions.executor import BatchExecutionResult, ExecutionResult


class TestGreetingResponseParsing:
    """Test that greeting responses with empty functions are correctly handled."""
    
    def test_parse_greeting_with_empty_functions(self):
        """Test parsing a greeting response with empty functions array."""
        parser = IntentParser()
        
        # This is the exact response format from the user's example
        llm_response = '''{
  "response": "Hello Johannes 🌿! It's wonderful to connect with you. How are you feeling today? Would you like to continue with Lesson 20, revisit Lesson 19, or talk about anything else in your practice?",
  "functions": []
}'''
        
        result = parser.parse(llm_response)
        
        # Should successfully parse
        assert result.success is True
        # Should extract just the response text
        expected_text = "Hello Johannes 🌿! It's wonderful to connect with you. How are you feeling today? Would you like to continue with Lesson 20, revisit Lesson 19, or talk about anything else in your practice?"
        assert result.response_text == expected_text
        # Functions should be empty list
        assert result.functions == []
        # Raw response should NOT equal parsed text
        assert llm_response != result.response_text
    
    def test_response_builder_with_empty_functions(self):
        """Test that ResponseBuilder correctly handles empty functions."""
        builder = ResponseBuilder()
        
        ai_text = "Hello Johannes 🌿! It's wonderful to connect with you."
        user_text = "Hi"
        
        # Empty execution result (no functions executed)
        empty_execution = BatchExecutionResult(
            results=[],
            all_succeeded=True,
            total_execution_time_ms=0.0,
        )
        
        result = builder.build(
            user_text=user_text,
            ai_response_text=ai_text,
            execution_result=empty_execution,
            include_function_results=True,
        )
        
        # Should return just the AI text since no functions were executed
        assert result.text == ai_text
        assert result.has_function_results is False
    
    def test_greeting_response_no_json_in_output(self):
        """Verify that the final output contains no JSON markers."""
        parser = IntentParser()
        builder = ResponseBuilder()
        
        llm_response = '''{
  "response": "Hello Johannes 🌿! How are you feeling today?",
  "functions": []
}'''
        
        # Parse the response
        parsed = parser.parse(llm_response)
        
        # Build final response
        empty_execution = BatchExecutionResult(
            results=[],
            all_succeeded=True,
            total_execution_time_ms=0.0,
        )
        
        built = builder.build(
            user_text="Hi",
            ai_response_text=parsed.response_text,
            execution_result=empty_execution,
            include_function_results=True,
        )
        
        # Final text should have no JSON markers
        assert "{" not in built.text
        assert "}" not in built.text
        assert '"response"' not in built.text
        assert '"functions"' not in built.text
        assert built.text == "Hello Johannes 🌿! How are you feeling today?"
    
    @pytest.mark.asyncio
    async def test_dialogue_engine_greeting_with_empty_functions(self):
        """Test that dialogue_engine returns only text for greeting with empty functions."""
        from src.services.dialogue_engine import DialogueEngine
        
        mock_session = MagicMock()
        mock_user = MagicMock()
        mock_user.user_id = 123
        mock_user.is_deleted = False
        mock_user.processing_restricted = False
        mock_user.opted_in = True
        mock_user.channel = "telegram"
        mock_user.first_name = "Johannes"
        
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
                            
                            # Greeting response with empty functions
                            greeting_response = '''{
  "response": "Hello Johannes 🌿! It's wonderful to connect with you. How are you feeling today? Would you like to continue with Lesson 20, revisit Lesson 19, or talk about anything else in your practice?",
  "functions": []
}'''
                            mock_call_ollama.return_value = greeting_response
                            
                            # Mock handle_triggers - no execution result since no functions
                            mock_triggers.return_value = {
                                "structured_intent_used": True,
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
                                text="Hi",
                                session=mock_session,
                                user_lang="en",
                                use_rag=False,
                                include_history=True,
                                history_turns=4,
                                include_lesson=True,
                            )
                            
                            # Should return ONLY the response text, no JSON
                            expected = "Hello Johannes 🌿! It's wonderful to connect with you. How are you feeling today? Would you like to continue with Lesson 20, revisit Lesson 19, or talk about anything else in your practice?"
                            assert result == expected, f"Expected plain text response, got:\n{result}"
                            
                            # Verify no JSON in result
                            assert "{" not in result, f"Result contains JSON braces: {result}"
                            assert "}" not in result, f"Result contains JSON braces: {result}"
                            assert '"functions"' not in result, f"Result contains functions key: {result}"
    
    def test_parse_result_with_whitespace_and_newlines(self):
        """Test that parsing handles responses with extra whitespace."""
        parser = IntentParser()
        
        # Response with extra whitespace and newlines
        llm_response = '''
{
  "response": "  Hello there!  \nHow are you?  ",
  "functions": []
}
'''
        
        result = parser.parse(llm_response)
        
        assert result.success is True
        # Should preserve the text content (whitespace handling depends on implementation)
        assert "Hello there!" in result.response_text
        assert "How are you?" in result.response_text
    
    def test_global_parser_instance(self):
        """Test that the global parser instance works correctly."""
        parser = get_intent_parser()
        
        llm_response = '''{
  "response": "Hello!",
  "functions": []
}'''
        
        result = parser.parse(llm_response)
        assert result.success is True
        assert result.response_text == "Hello!"
        assert result.functions == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
