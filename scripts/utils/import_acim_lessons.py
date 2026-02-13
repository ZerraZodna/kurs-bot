"""Import ACIM lessons from a PDF into the database.

Usage:
    python scripts/utils/import_acim_lessons.py --pdf src/data/Sparkly\ ACIM\ lessons-extracted.pdf

Flags:
    --pdf PATH       Path to PDF (defaults to src/data/Sparkly ACIM lessons-extracted.pdf)
    --no-clear       Do not clear existing lessons before import
    --verify BOOL    Whether to run a basic verification after import (default: True)
    --limit N        Limit number of lessons to import (for testing)

This is a pragmatic, resilient importer intended to replicate the old
`import_acim_lessons.py` behavior described in docs/ACIM_LESSONS_IMPORT.md.
"""

from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

try:
    from pypdf import PdfReader
except Exception as e:
    print("pypdf is required. Install with: pip install pypdf")
    raise

# Ensure repo root is on sys.path so `import src.*` works when running scripts directly
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.models.database import SessionLocal, Lesson, Base, engine
from sqlalchemy.exc import IntegrityError
import datetime

DEFAULT_PDF = Path("src/data/Sparkly ACIM lessons-extracted.pdf")

LESSON_SPLIT_RE = re.compile(r'(?=Lesson\s+\d{1,3})', re.IGNORECASE)
LESSON_ID_RE = re.compile(r'Lesson\s*(\d{1,3})', re.IGNORECASE)
TITLE_QUOTE_RE = re.compile(r'"([^\"]{5,200})"')


def extract_text_from_pdf(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    pages = []
    for p in reader.pages:
        try:
            text = p.extract_text() or ""
        except Exception:
            text = ""
        pages.append(text)
    return "\n\n".join(pages)


def parse_lessons(full_text: str) -> list[tuple[int,str,str]]:
    # Split into candidate lesson blocks
    blocks = [b.strip() for b in LESSON_SPLIT_RE.split(full_text) if b.strip()]
    lessons: list[tuple[int,str,str]] = []
    for b in blocks:
        m = LESSON_ID_RE.search(b)
        if not m:
            continue
        lesson_id = int(m.group(1))
        # Try to find a quoted title
        tmatch = TITLE_QUOTE_RE.search(b)
        title = tmatch.group(1).strip() if tmatch else f"Lesson {lesson_id}"
        # Content: everything after the first newline following the lesson id/title
        # Trim to reasonable size
        content = b
        if len(content) > 3000:
            content = content[:3000]
        lessons.append((lesson_id, title, content))
    # Deduplicate by lesson_id, keep first seen
    seen = set()
    out = []
    for lid, title, content in lessons:
        if lid in seen:
            continue
        seen.add(lid)
        out.append((lid, title, content))
    return out


def import_to_db(lessons: list[tuple[int,str,str]], clear: bool = True, limit: int | None = None) -> int:
    if limit is not None:
        lessons = lessons[:limit]
    session = SessionLocal()
    try:
        if clear:
            print("Clearing existing lessons table...")
            session.query(Lesson).delete()
            session.commit()
        added = 0
        for lid, title, content in lessons:
            lesson = Lesson(
                lesson_id=lid,
                title=title[:128],
                content=content,
                difficulty_level='beginner',
                duration_minutes=15,
                created_at=datetime.datetime.utcnow(),
            )
            session.add(lesson)
            try:
                session.flush()
                added += 1
            except IntegrityError:
                session.rollback()
                # skip duplicates
                continue
            if added % 50 == 0:
                session.commit()
                print(f"  Imported {added} lessons...")
        session.commit()
        return added
    finally:
        session.close()


def verify_db_count(expected: int) -> bool:
    session = SessionLocal()
    try:
        cnt = session.query(Lesson).count()
        print(f"Database contains {cnt} lessons (expected {expected})")
        return cnt >= expected
    finally:
        session.close()


def main(argv: list | None = None) -> int:
    p = argparse.ArgumentParser(description="Import ACIM lessons from PDF into DB")
    p.add_argument('--pdf', type=Path, default=DEFAULT_PDF)
    p.add_argument('--no-clear', action='store_true', help='Do not clear existing lessons')
    p.add_argument('--verify', default=True, type=lambda v: v.lower() not in ("false","0","no"))
    p.add_argument('--limit', type=int, help='Limit number of lessons to import (testing)')
    ns = p.parse_args(argv)

    pdf = ns.pdf
    if not pdf.exists():
        print(f"PDF not found: {pdf}")
        return 2

    print(f"📖 Reading ACIM lessons from: {pdf}")
    text = extract_text_from_pdf(pdf)
    print("🔍 Extracting lessons from PDF...")
    lessons = parse_lessons(text)
    print(f"Found {len(lessons)} candidate lessons in PDF")
    if not lessons:
        print("No lessons found — check PDF format. See docs/ACIM_LESSONS_IMPORT.md")
        return 3

    # Ensure DB tables exist
    Base.metadata.create_all(bind=engine)

    added = import_to_db(lessons, clear=(not ns.no_clear), limit=ns.limit)
    print(f"✅ Imported {added} lessons")

    if ns.verify:
        expected = len(lessons)
        ok = verify_db_count(expected)
        if not ok:
            print("⚠️  Verification failed: lesson count lower than expected")
            return 4
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
