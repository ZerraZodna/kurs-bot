import asyncio

async def consume_stream_response(response):
    """
    Consume stream response simulating full Telegram streaming + post-processing flow.
    
    This simulates:
    1. Streaming raw generator through StreamingFilter (JSON prefix skip, clean text)
    2. post_hook with remaining_functions content for trigger parsing/execution
    3. response_builder.build to combine stream text + function results
    4. Return final combined text matching production Telegram behavior.
    """
    if not isinstance(response, dict) or response.get('type') != 'stream':
        return str(response), None
    
    import asyncio
    from src.integrations.telegram_stream import StreamingFilter
    from src.functions.intent_parser import get_intent_parser
    from src.functions.response_builder import get_response_builder
    
    # Step 1: Simulate StreamingFilter processing (production telegram.py)
    raw_generator = response['generator']
    stream_filter = StreamingFilter(raw_generator)
    filtered_generator = stream_filter.filter_stream()
    
    # Step 2: Consume filtered stream (what Telegram displays)
    stream_text = ''
    async for chunk in filtered_generator:
        stream_text += chunk
    
    # Step 3: Run post_hook with full stream text (production)
    diagnostics = await response['post_hook'](stream_text)
    
    # Step 4: Get remaining JSON/functions content (production)
    remaining_json = stream_filter.get_remaining_for_functions()
    
    # Step 5: Simulate function processing on remaining JSON (production post_hook path)
    function_response_text = None
    if remaining_json or diagnostics:
        # Use remaining JSON or diagnostics full text for parsing
        parse_text = remaining_json or stream_text
        parser = get_intent_parser()
        parse_result = parser.parse(parse_text)
        
        if diagnostics and diagnostics.get("execution_result"):
            response_builder = get_response_builder()
            built_response = response_builder.build(
                user_text="test",  # dummy
                ai_response_text=parse_result.response_text or "",
                execution_result=diagnostics["execution_result"],
                include_function_results=True,
            )
            function_response_text = built_response.text
    
    # Step 6: Return COMBINED text (stream + functions) matching Telegram final display
    combined_text = stream_text
    if function_response_text and function_response_text.strip():
        if combined_text.strip():
            combined_text += "\n\n"
        combined_text += function_response_text
    
    return combined_text, diagnostics

