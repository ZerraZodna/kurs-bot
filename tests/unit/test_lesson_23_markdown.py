"""Unit tests for Lesson 23 markdown formatting for Telegram.

These tests verify that Lesson 23 content is correctly converted to
Telegram-compatible HTML with proper italic formatting.
"""

import pytest
from src.core.markdown_processor import markdown_to_telegram_html


class TestLesson23Formatting:
    """Test Lesson 23 content is properly formatted for Telegram."""

    def test_italic_text_renders_as_em_tag(self):
        """Test that single asterisk markdown renders as <em> tag for italics."""
        text = '*This is italic text*'
        html = markdown_to_telegram_html(text)
        
        assert '<em>' in html or '<i>' in html, f"Expected italic tag in: {html}"
        assert '</em>' in html or '</i>' in html, f"Expected closing italic tag in: {html}"

    def test_lesson_23_quote_appears_in_italics(self):
        """Test that the key quote from Lesson 23 appears in italics.
        
        The quote "I can escape from the world by giving up attack thoughts about _____."
        should be wrapped in italic HTML tags (<em> or <i>).
        """
        # This is the quote from Lesson 23 that should appear in italics
        # The original in the PDF has *** which produces bold+italic
        # For this test, we verify single asterisk produces proper italics
        text = '*"I can escape from the world by giving up attack thoughts about _____."*'
        
        html = markdown_to_telegram_html(text)
        
        # Verify the quote text appears in the output
        assert "I can escape from the world by giving up attack thoughts about _____." in html
        
        # Verify it appears in italic tags
        assert '<em>' in html or '<i>' in html, f"Expected italic tag in HTML output: {html}"

    def test_lesson_23_exercise_text_italic(self):
        """Test the specific exercise text from Lesson 23 appears in italics.
        
        This is the exact exercise instruction from the database that students use:
        *"I can escape from the world by giving *
        *up attack thoughts about _____."*
        
        It should appear in italics when formatted for Telegram.
        """
        # The exact text from lesson 23 in the database (two separate lines)
        text = '*"I can escape from the world by giving *\n*up attack thoughts about _____."*'
        
        html = markdown_to_telegram_html(text)
        
        # The complete quote should appear in the output
        assert "I can escape from the world by giving" in html
        assert "up attack thoughts about _____." in html
        
        # The text should be wrapped in italic tags
        assert '<em>' in html or '<i>' in html, f"Expected italic tag in HTML output: {html}"

    def test_bold_italic_renders_strong_and_em(self):
        """Test that triple asterisk markdown renders as both bold and italic."""
        text = '***"I can escape from the world I see by giving up attack thoughts."***'
        
        html = markdown_to_telegram_html(text)
        
        # Should contain both strong (bold) and em (italic) tags
        assert '<strong>' in html or '<b>' in html, f"Expected bold tag in: {html}"
        assert '<em>' in html or '<i>' in html, f"Expected italic tag in: {html}"

    def test_full_lesson_23_content_contains_italic_quote(self):
        """Test the actual Lesson 23 content includes italic formatting for the key quote.
        
        This tests the real lesson 23 content from the database would render correctly.
        """
        # The actual Lesson 23 content (first few lines from the database)
        text = '''Lesson 23

***"I can escape from the world I see by giving up attack thoughts."***

The idea for today contains the only way out of fear that will succeed.'''
        
        html = markdown_to_telegram_html(text)
        
        # The quote should be in the HTML
        assert "I can escape from the world I see by giving up attack thoughts" in html
        
        # Since it's wrapped in ***, it should have both bold and italic
        assert ('<strong>' in html or '<b>' in html), f"Expected bold tag in: {html}"
        assert ('<em>' in html or '<i>' in html), f"Expected italic tag in: {html}"

    def test_telegram_html_uses_compatible_tags(self):
        """Verify the output uses Telegram-compatible HTML tags."""
        text = '*This is italic for Telegram*'
        
        html = markdown_to_telegram_html(text)
        
        # Telegram supports <i> and <em> for italics
        # The markdown library typically uses <em>
        assert '<em>' in html or '<i>' in html, f"Expected Telegram-compatible italic tag: {html}"

