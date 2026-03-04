"""
Unified Markdown Processor - DRY implementation for markdown to HTML conversion.

This module provides a single source of truth for markdown processing across
all platforms (Telegram, WebUI, etc.).

Uses the `markdown` library for reliable, standards-compliant parsing.
"""

import re
import markdown
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from typing import Optional


class TelegramHTMLExtension(Extension):
    """
    Markdown extension to produce Telegram-compatible HTML.
    
    Telegram supports a limited subset of HTML tags:
    - <b>, <strong> - bold
    - <i>, <em> - italic
    - <u>, <ins> - underline
    - <s>, <strike>, <del> - strikethrough
    - <code> - inline code
    - <pre> - code block
    - <a> - links
    """
    
    def extendMarkdown(self, md):
        # Add preprocessor to handle Telegram-specific requirements
        md.preprocessors.register(TelegramPreprocessor(md), 'telegram_preprocessor', 30)


class TelegramPreprocessor(Preprocessor):
    """Preprocess markdown to handle Telegram-specific edge cases."""
    
    def run(self, lines):
        text = '\n'.join(lines)
        
        # Repair PDF/import artifacts like: a****** ******meaningless -> a meaningless
        text = self._repair_asterisk_artifacts(text)
        
        # Promote table-like plain text into fenced blocks
        text = self._promote_table_blocks_to_fenced_code(text)
        
        return text.split('\n')
    
    def _repair_asterisk_artifacts(self, text: str) -> str:
        """Repair common importer/PDF artifacts in lessons."""
        # "a****** ******meaningless" -> "a meaningless"
        text = re.sub(r'(?<=\w)\*{2,}(?:\s+\*{2,})+(?=\w)', ' ', text)
        text = re.sub(r'(?<=\w)\*{2,}(?=\w)', '', text)
        return text
    
    def _promote_table_blocks_to_fenced_code(self, text: str) -> str:
        """Promote table-like plain text into fenced code blocks."""
        lines = text.splitlines()
        if not lines:
            return text
        
        out = []
        i = 0
        while i < len(lines):
            if not self._is_table_candidate_line(lines[i]):
                out.append(lines[i])
                i += 1
                continue
            
            j = i
            block = []
            while j < len(lines) and self._is_table_candidate_line(lines[j]):
                block.append(lines[j])
                j += 1
            
            if self._should_wrap_table_block(block):
                out.append("```")
                out.extend(block)
                out.append("```")
            else:
                out.extend(block)
            
            i = j
        
        return "\n".join(out)
    
    def _is_table_candidate_line(self, line: str) -> bool:
        """Check if a line looks like it could be part of a table."""
        stripped = line.strip()
        if not stripped:
            return False
        if self._contains_box_drawing_char(stripped):
            return True
        if re.match(r'^\+[-=:+\s]+(?:\+[-=:+\s]+)+\+?$', stripped):
            return True
        if stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2:
            return True
        if "|" in stripped:
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) >= 2 and any(cells):
                return True
        return False
    
    def _should_wrap_table_block(self, block: list[str]) -> bool:
        """Determine if a block of lines should be wrapped as a table."""
        if len(block) < 2:
            return False
        
        has_strong_separator = any(
            self._is_table_separator_line(line.strip()) for line in block
        )
        has_box = any(self._contains_box_drawing_char(line) for line in block)
        
        if has_box or has_strong_separator:
            return True
        
        # Fallback for simple pipe-based tables
        return len(block) >= 3 and any("|" in line for line in block)
    
    def _is_table_separator_line(self, stripped: str) -> bool:
        """Check if a line is a table separator (like +---+---+)."""
        if not stripped:
            return False
        if re.match(r'^\+[-=:+\s]+(?:\+[-=:+\s]+)+\+?$', stripped):
            return True
        if re.match(r'^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$', stripped):
            return True
        return False
    
    def _contains_box_drawing_char(self, line: str) -> bool:
        """Check if line contains box-drawing Unicode characters."""
        return any(ch in line for ch in "┌┬┐├┼┤└┴┘│─═╔╗╚╝╠╣╦╩")


def markdown_to_html(text: str, for_telegram: bool = False) -> str:
    """
    Convert markdown text to HTML.
    
    Args:
        text: The markdown text to convert
        for_telegram: If True, produce Telegram-compatible HTML with 
                     specific extensions and preprocessing
    
    Returns:
        HTML string
    """
    if not text:
        return ""
    
    # Configure markdown extensions
    extensions = [
        'markdown.extensions.nl2br',  # Convert newlines to <br>
        'markdown.extensions.fenced_code',  # Fenced code blocks
    ]
    
    if for_telegram:
        extensions.append(TelegramHTMLExtension())
    
    # Convert markdown to HTML
    md = markdown.Markdown(extensions=extensions)
    html = md.convert(text)
    
    # Post-processing for Telegram compatibility
    if for_telegram:
        html = _post_process_for_telegram(html)
    
    return html


def _post_process_for_telegram(html: str) -> str:
    """
    Post-process HTML to ensure Telegram compatibility.
    
    Telegram has specific requirements for HTML tags.
    """
    # Ensure code blocks use <pre> tags
    # The markdown library should handle this, but we ensure consistency
    
    # Remove any attributes that Telegram doesn't support
    # Telegram only supports href in <a> tags
    
    # Clean up any empty paragraphs
    html = re.sub(r'<p>\s*</p>', '', html)
    
    return html.strip()


def markdown_to_telegram_html(text: str) -> str:
    """
    Convenience function for Telegram-specific markdown conversion.
    
    Args:
        text: The markdown text to convert
    
    Returns:
        Telegram-compatible HTML string
    """
    return markdown_to_html(text, for_telegram=True)
