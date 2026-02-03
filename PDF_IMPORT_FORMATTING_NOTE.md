# PDF Import Formatting Note

## Current Status
✅ All 365 lessons are now properly imported with complete content
✅ Lesson boundaries are correctly detected (handling PDF duplicate headers)
❌ Formatting (bold, italic, paragraph breaks) is lost during extraction

## Why Formatting is Lost
The current PDF extraction uses `pypdf` which extracts raw text only. The original PDF formatting information (bold, italic, font changes, paragraph structure) is discarded during this process.

## Solutions to Preserve Formatting

### Option 1: Use `pdfplumber` (Recommended for layout preservation)
```python
import pdfplumber

with pdfplumber.open(pdf_path) as pdf:
    # pdfplumber can extract:
    # - Structured text with better layout
    # - Table detection
    # - Character-level formatting hints
    page = pdf.pages[0]
    text = page.extract_text()
```

### Option 2: Post-Processing with Format Detection
Add simple heuristics to detect formatting patterns:
- **Bold text** → Detect all-caps sections or repeated character patterns
- **Italic text** → Detect slanted text markers (if available)
- **Paragraphs** → Preserve newline breaks instead of converting to single lines

### Option 3: Use PyPDF with Structured Extraction
```python
from pypdf import PdfReader

reader = PdfReader(pdf_path)
for page in reader.pages:
    # Could examine text objects for formatting info
    pass
```

### Option 4: Markdown-based Post-Processing
After extraction, implement AI-based formatting detection:
```python
# Pseudo-code: Apply formatting to extracted text
def add_markdown_formatting(text):
    # Detect likely emphasis words
    # Convert to **bold** and *italic* markdown
    pass
```

## Implementation Priority
1. ✅ **DONE**: Fix lesson boundary detection (currently implemented)
2. **TODO**: Evaluate pdfplumber integration if formatting is critical
3. **TODO**: Add markdown-style formatting hints in content

## Current Workaround
For now, lessons are delivered as plain text. Users can apply custom CSS/styling on the frontend to present lessons in a nice format. The content is complete and accurate; only visual formatting is missing.
