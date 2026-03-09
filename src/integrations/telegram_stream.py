"""Streaming filter for Telegram responses.

This module provides a StreamingFilter class that processes raw LLM tokens
to provide clean text for Telegram streaming, handling:
- Skipping JSON prefix ({"response": ")
- Buffering incomplete HTML tags until complete
- Buffering HTML entities until complete  
- Detecting response end at "functions": boundary
- Returning remaining content for function processing
"""

import re
import logging
from typing import AsyncIterator, Tuple, Optional

logger = logging.getLogger(__name__)


class StreamingFilter:
    """Filter LLM tokens to provide clean text for Telegram streaming.
    
    This filter wraps a raw token generator and:
    - Skips the initial JSON prefix: {"response": "
    - Buffers incomplete HTML tags (<b>, <em>, etc.) until complete
    - Buffers HTML entities (&nbsp;, &amp;, etc.) until complete
    - Stops at "functions": boundary (end of text response)
    - Returns remaining content for function processing
    - Properly unescapes JSON strings including Unicode sequences
    """
    
    # HTML tags that Telegram supports and should be buffered
    HTML_TAGS = {'b', 'strong', 'i', 'em', 'u', 's', 'code', 'pre', 'a', 'span'}
    
    # HTML entities that should be buffered until complete
    HTML_ENTITIES = {'nbsp', 'amp', 'lt', 'gt', 'quot', 'apos', 'copy', 'reg', 'trade', 'mdash', 'ndash', 'lsquo', 'rsquo', 'ldquo', 'rdquo'}
    
    def __init__(self, token_generator: AsyncIterator[str]):
        """Initialize the filter with a raw token generator.
        
        Args:
            token_generator: Async iterator yielding raw tokens from LLM
        """
        self._generator = token_generator
        self._buffer = ""
        self._json_prefix_skipped = False
        self._functions_boundary_reached = False
        self._remaining_for_functions: Optional[str] = None
        
    def _is_incomplete_tag(self, text: str) -> bool:
        """Check if text ends with an incomplete HTML tag.
        
        Returns True if we're in the middle of an opening or closing tag.
        """
        # Check for incomplete opening tag: <tag or <tag attr
        if re.search(r'<[a-zA-Z][a-zA-Z0-9]*(\s[^>]*)?$', text):
            return True
        # Check for incomplete closing tag: </tag
        if re.search(r'</[a-zA-Z][a-zA-Z0-9]*$', text):
            return True
        return False
    
    def _is_incomplete_entity(self, text: str) -> bool:
        """Check if text ends with an incomplete HTML entity.
        
        Returns True if we're in the middle of an entity like &nbsp
        """
        # Match incomplete entity: &xyz (no semicolon yet)
        if re.search(r'&[a-zA-Z][a-zA-Z0-9]*$', text):
            return True
        # Match partial entity: &#
        if re.search(r'&#$', text):
            return True
        # Match incomplete numeric entity: &#x
        if re.search(r'&#[a-fA-F0-9]*$', text) and not re.search(r'&#x[0-9a-fA-F]+;$', text):
            return True
        return False
    
    def _find_functions_boundary(self, text: str) -> int:
        """Find the position of "functions": boundary in text.
        
        Returns the position of the opening quote of "functions", or -1 if not found.
        We look for "functions": pattern which marks the end of the response text.
        """
        # Look for "functions": after the response text
        # The pattern is typically: "response": "...", "functions": [...]
        match = re.search(r'"\s*functions\s*"\s*:', text)
        if match:
            return match.start()
        return -1
    
    def _flush_buffer(self) -> str:
        """Flush the internal buffer and return its contents."""
        result = self._buffer
        self._buffer = ""
        return result
    
    async def filter_stream(self) -> AsyncIterator[str]:
        """Process tokens and yield clean text for Telegram.
        
        Yields:
            Clean text chunks suitable for Telegram display
        """
        async for token in self._generator:
            # If we've already hit the functions boundary, collect remaining
            if self._functions_boundary_reached:
                self._remaining_for_functions = (self._remaining_for_functions or "") + token
                continue
                
            # Append token to buffer
            self._buffer += token
            
            # Step 1: Skip JSON prefix {"response": "
            if not self._json_prefix_skipped:
                # Try to match {"response": " with flexible whitespace
                # Match: {"response": " or {  "response"  :  " etc.
                prefix_match = re.match(r'^\s*\{\s*"response"\s*:\s*"', self._buffer)
                if prefix_match:
                    # Remove the prefix from buffer
                    self._buffer = self._buffer[prefix_match.end():]
                    self._json_prefix_skipped = True
                    
                    # If buffer is now empty after removing prefix, continue
                    if not self._buffer:
                        continue
                elif not self._buffer.strip():
                    # Buffer is only whitespace, skip
                    self._buffer = ""
                    continue
                elif not re.match(r'^\s*\{', self._buffer):
                    # Buffer doesn't start with {, might be plain text response
                    self._json_prefix_skipped = True
                else:
                    # Still waiting for complete prefix - check if we have a partial match
                    # If we have something like {"response": but missing the opening quote
                    if re.match(r'^\s*\{\s*"response"\s*:\s*$', self._buffer):
                        # Wait for the opening quote
                        continue
                    # If we have {"response":" (no space after colon) try simpler match
                    prefix_match_simple = re.match(r'^\s*\{\s*"response"\s*:\s*"', self._buffer)
                    if prefix_match_simple:
                        self._buffer = self._buffer[prefix_match_simple.end():]
                        self._json_prefix_skipped = True
                        if not self._buffer:
                            continue
                    # Otherwise keep waiting for more
                    continue
            
            # Step 2: Check for functions boundary
            func_pos = self._find_functions_boundary(self._buffer)
            if func_pos != -1:
                # Found functions boundary - everything before it is text
                text_part = self._buffer[:func_pos]
                # Keep for functions processing
                self._remaining_for_functions = self._buffer[func_pos:]
                self._functions_boundary_reached = False  # Actually we've reached it
                
                if text_part:
                    # Clean up the text part - remove trailing comma, quote, and whitespace
                    # This handles cases like: "...text", 
                    text_part = text_part.strip()
                    if text_part.endswith('",'):
                        text_part = text_part[:-1]  # Remove trailing comma
                    elif text_part.endswith(','):
                        text_part = text_part[:-1]  # Remove trailing comma
                    
                    # Yield the text part (might need to flush buffer)
                    self._buffer = ""
                    # Try to extract just the string value (remove surrounding quotes)
                    clean_text = self._extract_string_value(text_part)
                    if clean_text:
                        yield clean_text
                continue
            
            # Step 3: Buffer incomplete HTML tags
            if self._is_incomplete_tag(self._buffer):
                # Wait for more tokens to complete the tag
                continue
                
            # Step 4: Buffer incomplete HTML entities  
            if self._is_incomplete_entity(self._buffer):
                # Wait for more tokens to complete the entity
                continue
            
            # Step 5: Buffer is complete - extract string value and yield
            clean_text = self._extract_string_value(self._buffer)
            if clean_text:
                yield clean_text
            self._buffer = ""
    
    def _unescape_json_string(self, text: str) -> str:
        """Unescape a JSON string value.
        
        Handles all common escape sequences including:
        - \\n -> newline
        - \\t -> tab
        - \\r -> carriage return
        - \\uXXXX -> Unicode characters
        - \\" -> quote
        - \\\\ -> backslash
        """
        if not text:
            return ""
        
        # First, handle Unicode escape sequences (\\uXXXX)
        # This must be done first, before other escape sequences
        def replace_unicode(match):
            try:
                return chr(int(match.group(1), 16))
            except (ValueError, OverflowError):
                return match.group(0)  # Return original if invalid
        
        text = re.sub(r'\\u([0-9a-fA-F]{4})', replace_unicode, text)
        
        # Handle extended Unicode (\\uXXXXXXXX) if present
        text = re.sub(r'\\u([0-9a-fA-F]{8})', replace_unicode, text)
        
        # Unescape common escape sequences FIRST (before handling backslashes)
        # This order is important: \\\\ -> \\ must happen AFTER \n -> newline
        # Otherwise \\n gets incorrectly converted to newline when it should
        # remain as \n (escaped backslash followed by letter n)
        text = text.replace('\\n', '\n')
        text = text.replace('\\t', '\t')
        text = text.replace('\\r', '\r')
        text = text.replace('\\"', '"')
        
        # Finally, handle escaped backslashes (must be last!)
        text = text.replace('\\\\', '\\')
        
        return text
    
    def _extract_string_value(self, text: str) -> str:
        """Extract the string value from a JSON string value.

        Handles escaped characters and returns the unescaped content.
        """
        if not text:
            return ""

        # Try to match a quoted string: "content"
        match = re.match(r'^"(.*)"$', text, re.DOTALL)
        if match:
            # Get the raw content and unescape it
            raw_content = match.group(1)
            # Unescape JSON string (including Unicode)
            content = self._unescape_json_string(raw_content)
            return content

        # If no quotes, return as-is (might be plain text)
        return text
    
    def get_remaining_for_functions(self) -> Optional[str]:
        """Get any remaining content that should be used for function processing.
        
        This includes the "functions": [...] part and anything after it.
        
        Returns:
            Remaining text for function processing, or None if nothing remaining
        """
        # Also include any remaining buffer content
        if self._buffer:
            # Check if buffer contains functions boundary
            func_pos = self._find_functions_boundary(self._buffer)
            if func_pos != -1:
                # Functions boundary found in remaining buffer
                self._remaining_for_functions = self._buffer[func_pos:]
            else:
                # No functions boundary - this might be incomplete text or empty
                # Try to extract as string and check if it's valid
                extracted = self._extract_string_value(self._buffer)
                if extracted and extracted.strip():
                    # This is valid text, not functions - don't include in functions
                    pass
                elif '"functions"' in self._buffer or '"functions":' in self._buffer:
                    # Buffer contains functions-related content
                    self._remaining_for_functions = (self._remaining_for_functions or "") + self._buffer
            self._buffer = ""
            
        return self._remaining_for_functions


async def create_filtered_stream(
    token_generator: AsyncIterator[str],
) -> Tuple[AsyncIterator[str], StreamingFilter]:
    """Create a filtered stream and return both the filtered iterator and the filter.
    
    This allows the caller to access the filter later to get remaining content
    for function processing.
    
    Args:
        token_generator: Raw token generator from LLM
        
    Returns:
        Tuple of (filtered async iterator, StreamingFilter instance)
    """
    filter_instance = StreamingFilter(token_generator)
    return filter_instance.filter_stream(), filter_instance

