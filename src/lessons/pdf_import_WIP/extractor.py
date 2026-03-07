"""Text extraction from PDF pages.

Extracts text from PDF pages with styling information preserved,
and handles common PDF artifacts like page headers and footers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from .reader import PDFReader, PDFPage, TextSpan


@dataclass
class ExtractedLine:
    """A single line of extracted text with styling."""
    raw: str           # Plain text without styling
    styled: str         # Text with HTML-style markup (<b>, <em>, <u>)
    x0: float          # Left indentation
    is_header: bool    # Whether this line is a section header
    is_indented: bool  # Whether this line is notably indented


@dataclass
class ExtractedPage:
    """A page worth of extracted text."""
    page_number: int
    lines: list[ExtractedLine]
    full_text: str     # All styled text joined


class PageHeaderDetector:
    """Detects and removes common page headers/footers.
    
    Common patterns:
    - "PART 1", "PART I", "WORKBOOK"
    - Page numbers (single digits, 1-3 digits)
    - Section markers
    """
    
    # Regex patterns for common page headers
    PART_PATTERN = re.compile(
        r'^(?:p\s*a\s*r\s*t(?:\s+(?:\d{1,3}|[ivxlcdm]+))?)$',
        re.IGNORECASE
    )
    WORKBOOK_PATTERN = re.compile(r'^workbook$', re.IGNORECASE)
    PAGE_NUMBER_PATTERN = re.compile(r'^\d{1,3}$')
    
    # Minimum y-position that might contain a footer
    # (expressed as ratio of page height, e.g., 0.9 = bottom 10%)
    
    def is_header_line(self, text: str) -> bool:
        """Check if a line is a page header."""
        cleaned = re.sub(r'[^A-Za-z0-9]', '', text).lower()
        if self.PART_PATTERN.match(cleaned):
            return True
        if self.WORKBOOK_PATTERN.match(cleaned):
            return True
        return False
    
    def is_footer_page_number(self, text: str, page_height: float, y_position: float) -> bool:
        """Check if text is a page number in the footer.
        
        Args:
            text: The text to check.
            page_height: Total height of the page.
            y_position: Y position of the text.
            
        Returns:
            True if this looks like a page number in the footer.
        """
        if not self.PAGE_NUMBER_PATTERN.match(text.strip()):
            return False
        
        # Check if it's in the bottom portion of the page
        position_ratio = y_position / page_height if page_height > 0 else 0
        return position_ratio > 0.85


class SpacedLetterFixer:
    """Fixes spaced letters commonly introduced by PDF fonts.
    
    Example: "L E S S O N" -> "LESSON"
    """
    
    # Pattern for spaced "lesson" followed by optional digits
    SPACED_LESSON_PATTERN = re.compile(
        r'(?i)(?<!\w)(l\s+e\s+s\s+s\s+o\s+n)((?:\s+\d){1,3})?(?!\w)'
    )
    
    def fix(self, text: str) -> str:
        """Fix spaced letters in text.
        
        Args:
            text: Input text.
            
        Returns:
            Text with spaced letters collapsed.
        """
        if not text or ' ' not in text:
            return text
        
        def _collapse(m):
            letters = m.group(1)
            digits = m.group(2) or ''
            
            letters_collapsed = letters.replace(' ', '')
            if digits:
                digits_collapsed = re.sub(r'\s+', '', digits)
                return letters_collapsed + ' ' + digits_collapsed
            return letters_collapsed
        
        return self.SPACED_LESSON_PATTERN.sub(_collapse, text)


class PDFExtractor:
    """Extracts styled text from PDFs.
    
    This class handles the full pipeline from PDF pages to structured
    text output with HTML-style markup for bold, italic, etc.
    """
    
    def __init__(self):
        self.header_detector = PageHeaderDetector()
        self.spaced_fixer = SpacedLetterFixer()
    
    def extract_page(self, page: PDFPage) -> ExtractedPage:
        """Extract styled text from a single PDF page.
        
        Args:
            page: PDFPage from the reader.
            
        Returns:
            ExtractedPage with lines and full text.
        """
        lines: list[ExtractedLine] = []
        
        for block in page.blocks:
            # Get base x position for indentation detection
            x_candidates = [span.x0 for span in block.spans if span.x0 > 0]
            base_x = min(x_candidates) if x_candidates else 0.0
            
            for span in block.spans:
                raw_text = span.text
                if not raw_text or not raw_text.strip():
                    continue
                
                # Fix spaced letters
                raw_text = self.spaced_fixer.fix(raw_text)
                
                # Build styled version
                styled_text = self._style_text(raw_text, span)
                
                # Determine indentation
                x0 = span.x0
                is_indented = (x0 - base_x) >= 12 if base_x > 0 else False
                
                # Check if it's a header
                is_header = self._is_likely_header(raw_text)
                
                lines.append(ExtractedLine(
                    raw=raw_text.strip(),
                    styled=styled_text,
                    x0=x0,
                    is_header=is_header,
                    is_indented=is_indented,
                ))
        
        # Remove page headers
        lines = self._remove_headers(lines)
        
        # Remove trailing page numbers
        lines = self._remove_trailing_page_numbers(lines, page.height)
        
        full_text = '\n'.join(line.styled for line in lines)
        
        return ExtractedPage(
            page_number=page.page_number,
            lines=lines,
            full_text=full_text,
        )
    
    def _style_text(self, text: str, span: TextSpan) -> str:
        """Apply HTML-style markup to text based on span styling.
        
        Args:
            text: The text to style.
            span: The TextSpan with styling info.
            
        Returns:
            Styled text with <b>, <em>, <u> tags.
        """
        result = text
        
        # Apply underline first (inner-most)
        if span.is_underline:
            result = f'<u>{result}</u>'
        
        # Apply italic
        if span.is_italic:
            result = f'<em>{result}</em>'
        
        # Apply bold (outer-most)
        if span.is_bold:
            result = f'<b>{result}</b>'
        
        return result
    
    def _is_likely_header(self, text: str) -> bool:
        """Check if text looks like a section header."""
        # Check for lesson header pattern
        cleaned = re.sub(r'\s+', '', text).lower()
        
        # Lesson header patterns
        if re.match(r'^lesson\d{1,3}$', cleaned):
            return True
        
        # Part/Workbook patterns
        if re.match(r'^(part\d?|workbook)$', cleaned):
            return True
        
        return False
    
    def _remove_headers(self, lines: list[ExtractedLine]) -> list[ExtractedLine]:
        """Remove page headers from lines.
        
        Args:
            lines: List of extracted lines.
            
        Returns:
            Lines with headers removed.
        """
        if not lines:
            return lines
        
        # Check first line for header
        first_line = lines[0]
        if self.header_detector.is_header_line(first_line.raw):
            return lines[1:]
        
        return lines
    
    def _remove_trailing_page_numbers(
        self, 
        lines: list[ExtractedLine], 
        page_height: float
    ) -> list[ExtractedLine]:
        """Remove trailing page numbers from lines.
        
        Args:
            lines: List of extracted lines.
            page_height: Height of the page for position detection.
            
        Returns:
            Lines with trailing page numbers removed.
        """
        if not lines:
            return lines
        
        # Check last line
        last_line = lines[-1]
        
        # Check if it's just digits
        if re.sub(r'[^0-9]', '', last_line.raw) == last_line.raw:
            digits = re.sub(r'\D', '', last_line.raw)
            if 1 <= len(digits) <= 3:
                return lines[:-1]
        
        return lines
    
    def extract_from_file(self, pdf_path: Path) -> Iterator[ExtractedPage]:
        """Extract styled text from a PDF file.
        
        Args:
            pdf_path: Path to the PDF file.
            
        Yields:
            ExtractedPage objects for each page.
        """
        with PDFReader(pdf_path) as reader:
            for page in reader.iter_pages():
                yield self.extract_page(page)


def extract_pdf_text(pdf_path: Path) -> str:
    """Convenience function to extract all text from a PDF.
    
    Args:
        pdf_path: Path to the PDF file.
        
    Returns:
        All styled text from the PDF, joined by double newlines between pages.
    """
    extractor = PDFExtractor()
    pages = list(extractor.extract_from_file(pdf_path))
    
    # Join pages with paragraph breaks
    page_texts = [page.full_text for page in pages]
    return '\n\n'.join(page_texts)

