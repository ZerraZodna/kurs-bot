# ACIM Lessons Database Import Guide

## Overview

The `import_acim_lessons.py` script extracts all 365 ACIM (A Course in Miracles) lessons from a PDF file and populates the database with them. This eliminates the hallucination problem where the AI would generate lessons without proper source material.

## Prerequisites

- PDF file: `src/data/Sparkly ACIM lessons-extracted.pdf`
- Python packages: `pypdf` (will be installed by the script)

## Usage

### Basic Import (Clears existing lessons)

```bash
python scripts/import_acim_lessons.py
```

### Import with Custom PDF Path

```bash
python scripts/import_acim_lessons.py --pdf path/to/your/acim-lessons.pdf
```

### Preserve Existing Lessons

```bash
python scripts/import_acim_lessons.py --no-clear
```

### Skip Verification After Import

```bash
python scripts/import_acim_lessons.py --verify False
```

## How It Works

1. **PDF Extraction**: Reads the PDF file and extracts all text using `pypdf`
2. **Lesson Parsing**: Identifies individual lessons using regex pattern matching (Lesson 1, Lesson 2, etc.)
3. **Deduplication**: Ensures each lesson number is only imported once
4. **Database Import**: Stores lessons in the `lessons` table with:
   - `lesson_id`: Sequential number (1-361)
   - `title`: Lesson title/heading
   - `content`: Full lesson text (up to 3000 characters)
   - `difficulty_level`: Set to "beginner"
   - `duration_minutes`: Set to 15 minutes
   - `created_at`: Timestamp

## Database Schema

```sql
CREATE TABLE lessons (
    lesson_id INTEGER PRIMARY KEY,
    title VARCHAR(128) NOT NULL,
    content TEXT NOT NULL,
    difficulty_level VARCHAR(32),
    duration_minutes INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## Example Output

```
📖 Reading ACIM lessons from: src/data/Sparkly ACIM lessons-extracted.pdf
File size: 12.29 MB

🔍 Extracting lessons from PDF...
Found 361 lessons in PDF

First 3 lessons found:
  - Lesson 1: "Nothing I see in this room [on this street,
  - Lesson 2: "I have given everything I see in this room [on this street, from this
  - Lesson 3: "I do not understand anything I see in this room

💾 Importing lessons to database...
Cleared existing lessons
  Imported 50 lessons...
  Imported 100 lessons...
  ...

✅ Successfully imported 361 lessons

📊 Database now contains 361 lessons
✅ All 361 ACIM lessons successfully imported!
```

## Using Lessons in the Application

### In Dialogue Engine

The DialogueEngine can now fetch actual ACIM lessons instead of generating them:

```python
from src.models.database import SessionLocal, Lesson
from src.services.dialogue_engine import DialogueEngine

session = SessionLocal()
engine = DialogueEngine(db=session)

# Get a specific lesson
lesson = session.query(Lesson).filter(Lesson.lesson_id == 1).first()
print(lesson.title)
print(lesson.content)

# Get today's lesson (day 1-365)
day = 42
today_lesson = session.query(Lesson).filter(Lesson.lesson_id == day).first()
```

### In Telegram Bot

When users request a lesson:

```python
@router.get("/lesson/{day}")
async def get_lesson(day: int, session: Session = Depends(get_db)):
    lesson = session.query(Lesson).filter(Lesson.lesson_id == day).first()
    if not lesson:
        return {"error": "Lesson not found"}
    return {"title": lesson.title, "content": lesson.content}
```

### In Scheduling

Schedule daily lessons by linking schedules to lessons:

```python
from src.services.scheduler import SchedulerService

scheduler = SchedulerService()

# Schedule lesson delivery for user
for day in range(1, 362):
    scheduler.schedule_lesson(
        user_id=user_id,
        lesson_id=day,
        schedule_type="daily",
        cron_expr=f"0 9 * * *"  # 9 AM every day
    )
```

## Troubleshooting

### Issue: "No lessons found in PDF"

- Ensure the PDF is in the correct format
- Try installing: `pip install pdfplumber` as a fallback
- Check that the PDF actually contains lesson text

### Issue: "UNIQUE constraint failed: lessons.lesson_id"

- Use `--clear` flag to remove existing lessons first
- Or use `--no-clear` to skip clearing

### Issue: pypdf not found

- Install manually: `pip install pypdf`
- The script will suggest this if it detects the issue

## Performance

- **Import time**: ~30 seconds for 361 lessons
- **Database size**: SQLite adds ~5-10 MB (lessons table)
- **Query time**: <10ms to retrieve a single lesson

## Maintenance

To re-import lessons after updating the PDF:

```bash
# Clear old lessons and import new ones
python scripts/import_acim_lessons.py --clear

# Or keep both versions by using --no-clear
python scripts/import_acim_lessons.py --no-clear
```

## Next Steps

1. Update the DialogueEngine to fetch lessons from the database
2. Integrate lesson delivery into the scheduling system
3. Add lesson progress tracking (which lessons users have completed)
4. Create a lesson search endpoint for users to browse lessons
