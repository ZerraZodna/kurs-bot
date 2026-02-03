"""
Test pdfplumber for better formatting preservation.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

def test_pdfplumber_formatting(pdf_path: str) -> None:
    """Test pdfplumber extraction."""
    try:
        import pdfplumber
        
        print("Testing pdfplumber extraction...\n")
        
        with pdfplumber.open(pdf_path) as pdf:
            # Check first few pages
            for page_num in range(min(3, len(pdf.pages))):
                page = pdf.pages[page_num]
                text = page.extract_text()
                
                print(f"\n{'='*60}")
                print(f"PAGE {page_num + 1}")
                print(f"{'='*60}")
                print(f"Text length: {len(text) if text else 0} chars")
                
                if text:
                    print(f"First 500 chars:\n{text[:500]}")
                
                # Try to extract formatted text
                try:
                    # Some versions of pdfplumber have text_flow or other methods
                    if hasattr(page, 'get_text'):
                        formatted = page.get_text()
                        print(f"\nFormatted text (if available): {len(formatted)} chars")
                except:
                    pass
    
    except ImportError:
        print("pdfplumber not installed")
        return

def main():
    pdf_path = "src/data/Sparkly ACIM lessons-extracted.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"PDF not found: {pdf_path}")
        sys.exit(1)
    
    test_pdfplumber_formatting(pdf_path)

if __name__ == "__main__":
    main()
