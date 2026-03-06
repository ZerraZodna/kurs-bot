# TODO: Fix Split Italic Markers by Storing HTML in Database

## Problem

The markdown parser gets confused when italic markers (`*`) span across lines:

```
*"Text*
*more text."*
```

This produces broken HTML:
```html
<em>"Text*</em>
more text."*
```

The asterisks start on one line and end on the next, causing the parser to split the italic formatting incorrectly.

## Root Cause

The current flow stores **markdown** in the database (`Lesson.content`), which is then converted to HTML at runtime via `markdown_to_telegram_html()`. The markdown parser can't handle split italic markers across lines.

## Solution

Store **HTML tags directly** in the existing `content` column during import, instead of markdown. This fixes the problem at the root.

## Implementation Plan

### Step 1: Update Lesson Importer to Generate HTML
**File:** `scripts/utils/import_acim_lessons.py`

- Import `markdown_to_telegram_html` from `src.core.markdown_processor`
- During import, convert `content` (markdown) to HTML using the function
- Store the HTML directly in the existing `content` column (replacing markdown)

### Step 2: Update Delivery Code to Use HTML Directly
**Files:** 
- `src/integrations/telegram.py` - Use content directly, skip markdown conversion
- `src/api/app.py` - Similar update for API endpoints
- `src/core/markdown_processor.py` - May need to adjust or the code paths that call it
- **WebUI** (`src/api/dev_web_client.py` or similar) - Update to use HTML directly

The delivery code should use the content as-is since it's now already HTML.

### Step 3: Remove Markdown Code and Dependencies
- **Remove `src/core/markdown_processor.py`** - no longer needed since content is pre-converted to HTML
- **Update imports** - remove any imports of `markdown_to_telegram_html` or `markdown_to_html` from:
  - `src/integrations/telegram.py`
  - `src/api/app.py`
  - Any other files that use it
- **Remove from `requirements.txt`** - remove the `markdown` package
- **Delete related tests** - remove `tests/unit/test_lesson_23_markdown.py` since markdown conversion is no longer used

### Step 4: Re-import Lessons
- Run the import script to populate the `content` column with HTML
- Verify lesson delivery works correctly with split italic markers

## Benefits

1. **Fixes the bug at root**: No more markdown parsing issues with split markers
2. **Better performance**: HTML is pre-computed, no conversion needed at runtime
3. **No schema changes**: Uses existing `content` column

## Testing

After implementation:
- Rewrite `tests/unit/test_lesson_23_markdown.py` to test HTML content directly instead of markdown conversion
- Manually test lesson delivery in Telegram with the affected lessons
- Verify lessons with italic formatting work correctly

