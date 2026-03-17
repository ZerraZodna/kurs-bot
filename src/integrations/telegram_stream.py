"""Streaming filter for Telegram responses.

This module provides a StreamingFilter class that processes raw LLM tokens
to provide clean text for Telegram streaming, handling:
- Skipping JSON prefix ({"response": ")
- Buffering incomplete HTML tags until complete
- Buffering HTML entities until complete  
- Detecting response end at "functions": boundary
- Returning remaining content for function processing
"""

import logging
import re
from collections.abc import AsyncIterator
from typing import Optional, Tuple

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
    HTML_TAGS = {"b", "strong", "i", "em", "u", "s", "code", "pre", "a", "span"}
    
    # HTML entities that should be buffered until complete
    HTML_ENTITIES: set[str] = {"nbsp", "amp", "lt", "gt", "quot", "apos", "copy", "reg", "trade", "mdash", "ndash", "lsquo", "rsquo", "ldquo", "rdquo"}
    
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
        if re.search(r"<[a-zA-Z][a-zA-Z0-9]*(\s[^>]*)?$", text):
            return True
        # Check for incomplete closing tag: </tag
        if re.search(r"</[a-zA-Z][a-zA-Z0-9]*$", text):
            return True
        return False
    
    def _is_incomplete_entity(self, text: str) -> bool:
        """Check if text ends with an incomplete HTML entity.
        
        Returns True if we're in the middle of an entity like &nbsp
        """
        # Match incomplete entity: &xyz (no semicolon yet)
        if re.search(r"&[a-zA-Z][a-zA-Z0-9]*$", text):
            return True
        # Match partial entity: &#
        if re.search(r"&#$", text):
            return True
        # Match incomplete numeric entity: &#x
        if re.search(r"&#[a-fA-F0-9]*$", text) and not re.search(r"&#x[0-9a-fA-F]+;$", text):
            return True
        return False
    
    def _is_incomplete_json_escape(self, text: str) -> bool:
        """Check if text ends with an incomplete JSON escape sequence.
        
        Returns True if we're in the middle of a JSON escape sequence that
        needs more characters to be complete. This prevents premature
        unescaping when escape sequences are fragmented across tokens.
        """
        if not text:
            return False
            
        # Check if text ends with a backslash that could start an escape
        if text.endswith("\\"):
            # Check for double backslash - could be \\ followed by n
            # In JSON, \\n = literal backslash + n, not newline
            # But we need to see what comes next
            # If we have just \\, buffer in case next char is n, u, x, etc.
            return True
            
        # Check for incomplete \u escape (need \uXXXX - 4 hex digits)
        if re.search(r"\\u[0-9a-fA-F]{0,3}$", text):
            return True
            
        # Check for incomplete \x escape (need \xNN - 2 hex digits)
        if re.search(r"\\x[0-9a-fA-F]{0,1}$", text):
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
        
    def _is_response_string_ended(self, text: str) -> bool:
        """Check if the JSON response string value has ended.
        
        This detects when we've hit the closing quote of the "response" field,
        followed by a comma (which marks the start of the next field like "functions").
        
        Once this is detected, nothing more should go to Telegram - all subsequent
        content (functions, etc.) should be collected for function processing only.
        
        Returns True if text contains pattern like: "...",  (closing quote + comma)
        """
        # Match: " followed by , - this marks end of string value in JSON
        # This is the closing quote of the response field, followed by comma
        if re.search(r'"\s*,', text):
            return True
        return False

    
    def _flush_buffer(self) -> str:
        """Flush the internal buffer and return its contents."""
        result = self._buffer
        self._buffer = ""
        return result
    
    def _unescape_json_string(self, text: str) -> str:
        """Unescape JSON escape sequences in text.
        
        This handles the common JSON escape sequences that may appear
        in the LLM response string content.
        
        Args:
            text: Text that may contain JSON escape sequences
            
        Returns:
            Text with JSON escape sequences converted to actual characters
        """
        if not text:
            return text
            
        result = text
        # Order matters: handle escaped backslashes first
        result = result.replace("\\\\", "\\")  # \\ -> \
        result = result.replace("\\n", "\n")    # \n -> newline
        result = result.replace("\\r", "\r")    # \r -> carriage return
        result = result.replace("\\t", "\t")    # \t -> tab
        result = result.replace('\\"', '"')     # \" -> "
        result = result.replace("\\'", "'")     # \' -> '
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
                elif not re.match(r"^\s*\{", self._buffer):
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
                        
            # Step 2: Buffer incomplete HTML tags
            if self._is_incomplete_tag(self._buffer):
                # Wait for more tokens to complete the tag
                continue
                
            # Step 3: Buffer incomplete HTML entities  
            if self._is_incomplete_entity(self._buffer):
                # Wait for more tokens to complete the entity
                continue
            
            # Step 4: Buffer incomplete JSON escape sequences
            # Escape sequences like \n, \\n, \t can be fragmented across tokens
            # We need to buffer until we have a complete escape sequence
            if self._is_incomplete_json_escape(self._buffer):
                # Wait for more tokens to complete the escape sequence
                continue

            # Step 5: Check if response string has ended
            # Once we detect closing quote + comma (e.g., '?",' or '")'), 
            # nothing more should go to Telegram - collect for functions only
            if self._is_response_string_ended(self._buffer):
                # Response string has ended - collect everything for functions
                self._functions_boundary_reached = True
                self._remaining_for_functions = "{" + self._buffer[3:]

                # Yield what's left in buffer (the actual response text)
                text_part = self._buffer
                # Find where the "," starts and only yield before it
                match = re.search(r'"\s*,', text_part)
                if match:
                    text_part = text_part[:match.start()]
                if text_part:
                    yield self._unescape_json_string(text_part)
                self._buffer = ""
                continue

            # Step 6: Buffer is complete - extract string value and yield (with JSON unescaping)
            if self._buffer:
                yield self._unescape_json_string(self._buffer)
            self._buffer = ""
            
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
                if '"functions"' in self._buffer or '"functions":' in self._buffer:
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

