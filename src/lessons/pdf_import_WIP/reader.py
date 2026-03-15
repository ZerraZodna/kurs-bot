"""PDF Reader abstraction layer.

Provides a unified interface for reading PDFs, abstracting away the
underlying library (fitz/PyMuPDF, pypdf, etc.).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

import fitz


@dataclass
class TextSpan:
    """A span of text with associated styling information."""
    text: str
    font_name: str
    font_size: float
    is_bold: bool
    is_italic: bool
    is_underline: bool
    x0: float  # Left position on page
    x1: float  # Right position on page


@dataclass
class TextBlock:
    """A block of text from the PDF (typically a paragraph or similar)."""
    spans: list[TextSpan]
    y0: float  # Top position on page
    y1: float  # Bottom position on page


@dataclass
class PDFPage:
    """Represents a single page from the PDF."""
    page_number: int
    blocks: list[TextBlock]
    width: float
    height: float


class PDFReader:
    """Abstract PDF reader interface.
    
    Provides a clean API for extracting text and metadata from PDFs,
    with font styling information preserved.
    """
    
    def __init__(self, pdf_path: Path):
        """Initialize reader with PDF path.
        
        Args:
            pdf_path: Path to the PDF file.
            
        Raises:
            FileNotFoundError: If PDF doesn't exist.
            ValueError: If PDF is invalid.
        """
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        
        self._pdf_path = pdf_path
        self._doc: Optional[fitz.Document] = None
    
    def _ensure_open(self) -> fitz.Document:
        """Lazy open the PDF document."""
        if self._doc is None:
            self._doc = fitz.open(str(self._pdf_path))
        return self._doc
    
    @property
    def page_count(self) -> int:
        """Return the number of pages in the PDF."""
        return len(self._ensure_open())
    
    def read_page(self, page_num: int) -> PDFPage:
        """Read a single page from the PDF.
        
        Args:
            page_num: Page number (1-indexed).
            
        Returns:
            PDFPage object with extracted text and styling.
        """
        doc = self._ensure_open()
        if page_num < 1 or page_num > len(doc):
            raise ValueError(f"Page {page_num} out of range (1-{len(doc)})")
        
        page = doc[page_num - 1]  # fitz uses 0-indexed
        return self._extract_page(page, page_num)
    
    def _extract_page(self, page: fitz.Page, page_num: int) -> PDFPage:
        """Extract text and styling from a fitz page."""
        blocks: list[TextBlock] = []
        
        # Get page dimensions
        rect = page.rect
        width = rect.width
        height = rect.height
        
        # Get text as dictionary with styling info
        text_dict = page.get_text('dict')
        
        for block in text_dict.get('blocks', []):
            if block.get('type', 0) != 0:  # Only text blocks
                continue
            
            spans: list[TextSpan] = []
            block_y0 = float('inf')
            block_y1 = 0.0
            
            for line in block.get('lines', []):
                line_bbox = line.get('bbox', [0, 0, 0, 0])
                y0 = float(line_bbox[1])
                y1 = float(line_bbox[3])
                
                block_y0 = min(block_y0, y0)
                block_y1 = max(block_y1, y1)
                
                for span in line.get('spans', []):
                    text = span.get('text', '')
                    if not text:
                        continue
                    
                    font = span.get('font', '')
                    size = span.get('size', 0)
                    bbox = span.get('bbox', [0, 0, 0, 0])
                    
                    # Determine styling from font name
                    bold = self._is_bold_font(font)
                    italic = self._is_italic_font(font)
                    underline = self._is_underline_font(font)
                    
                    span_obj = TextSpan(
                        text=text,
                        font_name=font,
                        font_size=size,
                        is_bold=bold,
                        is_italic=italic,
                        is_underline=underline,
                        x0=float(bbox[0]),
                        x1=float(bbox[2]),
                    )
                    spans.append(span_obj)
            
            if spans:
                blocks.append(TextBlock(
                    spans=spans,
                    y0=block_y0,
                    y1=block_y1,
                ))
        
        return PDFPage(
            page_number=page_num,
            blocks=blocks,
            width=width,
            height=height,
        )
    
    def _is_bold_font(self, font_name: str) -> bool:
        """Check if font name indicates bold styling."""
        name_lower = font_name.lower()
        return any(term in name_lower for term in ('bold', 'black', 'heavy', 'bd'))
    
    def _is_italic_font(self, font_name: str) -> bool:
        """Check if font name indicates italic styling."""
        name_lower = font_name.lower()
        return any(term in name_lower for term in ('italic', 'oblique', 'it', 'slanted'))
    
    def _is_underline_font(self, font_name: str) -> bool:
        """Check if font name indicates underline styling."""
        name_lower = font_name.lower()
        return any(term in name_lower for term in ('underline', 'ul'))
    
    def iter_pages(self) -> Iterator[PDFPage]:
        """Iterate over all pages in the PDF.
        
        Yields:
            PDFPage objects for each page.
        """
        doc = self._ensure_open()
        for page_num in range(1, len(doc) + 1):
            yield self.read_page(page_num)
    
    def close(self) -> None:
        """Close the PDF document."""
        if self._doc is not None:
            self._doc.close()
            self._doc = None
    
    def __enter__(self) -> 'PDFReader':
        return self
    
    def __exit__(self, exc_type, exc_val, exec_err) -> None:
        self.close()


def open_pdf(pdf_path: Path) -> PDFReader:
    """Convenience function to open a PDF.
    
    Args:
        pdf_path: Path to the PDF file.
        
    Returns:
        PDFReader instance.
        
    Example:
        with open_pdf(Path('lessons.pdf')) as reader:
            for page in reader.iter_pages():
                print(f"Page {page.page_number}")
    """
    return PDFReader(pdf_path)

