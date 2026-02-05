"""
Simple, focused ACIM lessons importer.

This new script uses the bundled cleaning pipeline implemented in
`scripts/make_clean_acim.py` to build a cleaned text representation of
the PDF (including preserved markdown-style bold/italic markers), then
splits lessons using a compact parser and imports them into the DB.

It intentionally avoids the large, experimental extractor code that
was preserved in `scripts/obsolete_import_lesson.py`.

Usage:
  python scripts/import_acim_lessons.py --pdf src/data/Sparkly\ ACIM\ lessons-extracted.pdf [--clear]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from datetime import datetime, timezone

# Ensure project root is on sys.path so `from src...` works when running
# this script directly (e.g. `python scripts/import_acim_lessons.py`).
# We insert the repo root (parent of `scripts/`) at the front of sys.path.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.models.database import SessionLocal, Lesson, init_db
from scripts import make_clean_acim as mc


def load_cleaner_module() -> object:
    # Prefer the local scripts.make_clean_acim module
    return mc


def build_clean_text(mc: object, pdf_path: str) -> str:
    # Use the cleaner's functions to extract raw text, styled paragraphs,
    # merge styling back into raw and perform final cleaning.
    raw = mc.extract_raw_text(pdf_path)
    paras = mc.extract_preserve_styles(pdf_path)
    extracted = "\n\n".join(paras) if paras else ""
    merged = mc.merge_styles_into_raw(extracted, raw)
    cleaned = mc.clean_merged_text(merged)
    return cleaned


def parse_lessons_simple(text: str) -> list:
    # Very simple splitter: match header-only lines like "Lesson 1" and
    # take everything until the next header as the lesson content. This
    # matches the cleaned text format that uses isolated header lines.
    pattern = re.compile(r"(?im)^\s*lesson\s+(\d+)\s*$", re.M)
    matches = list(pattern.finditer(text))
    lessons = []
    if not matches:
        return lessons

    for i, m in enumerate(matches):
        lesson_num = int(m.group(1))

        # Content starts after the end of the header line
        line_end_idx = text.find('\n', m.end())
        if line_end_idx == -1:
            content_start = m.end()
        else:
            content_start = line_end_idx + 1

        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(text)

        content = text[content_start:end].strip()
        content = re.sub(r"\n{3,}", "\n\n", content).strip()

        title = f"Lesson {lesson_num}"

        lessons.append({
            "lesson_id": lesson_num,
            "title": title,
            "content": content or f"Lesson {lesson_num}: {title}",
            "difficulty_level": "beginner",
            "duration_minutes": 15,
        })

    # Deduplicate by lesson_id, prefer first occurrence
    seen = set()
    out = []
    for l in lessons:
        if l["lesson_id"] in seen:
            continue
        seen.add(l["lesson_id"])
        out.append(l)
    return sorted(out, key=lambda x: x["lesson_id"])


def import_lessons_to_db(lessons: list, clear_existing: bool = False) -> int:
    session = SessionLocal()
    try:
        init_db()
        if clear_existing:
            session.query(Lesson).delete()
            session.commit()

        now = datetime.now(timezone.utc)
        count = 0
        for ld in lessons:
            existing = session.query(Lesson).filter(Lesson.lesson_id == ld["lesson_id"]).first()
            if existing:
                existing.title = ld["title"]
                existing.content = ld["content"]
                existing.difficulty_level = ld.get("difficulty_level")
                existing.duration_minutes = ld.get("duration_minutes")
                session.add(existing)
            else:
                lesson = Lesson(
                    lesson_id=ld["lesson_id"],
                    title=ld["title"],
                    content=ld["content"],
                    difficulty_level=ld.get("difficulty_level"),
                    duration_minutes=ld.get("duration_minutes"),
                    created_at=now,
                )
                session.add(lesson)
            count += 1
            if count % 50 == 0:
                session.commit()
        session.commit()
        return count
    finally:
        session.close()


def verify(expected_count: int):
    session = SessionLocal()
    try:
        c = session.query(Lesson).count()
        print(f"[DB] Database now contains {c} lessons")
        if c == expected_count:
            print(f"[OK] All {expected_count} lessons present")
        else:
            print(f"[WARN] expected {expected_count}, found {c}")
    finally:
        session.close()


def main(argv=None):
    p = argparse.ArgumentParser(description="Clean ACIM PDF and import lessons into DB")
    p.add_argument("--pdf", default="src/data/Sparkly ACIM lessons-extracted.pdf")
    # Clear existing lessons by default; provide `--no-clear` to opt out
    p.add_argument("--no-clear", action="store_false", dest="clear", help="Do not clear existing lessons before import")
    p.set_defaults(clear=True)
    p.add_argument("--verify", action="store_true", help="Verify after import")
    args = p.parse_args(argv)

    pdf = args.pdf
    if not Path(pdf).exists():
        print(f"[ERROR] PDF not found: {pdf}")
        raise SystemExit(1)

    print(f"[PDF] {pdf}")
    mc = load_cleaner_module()
    print("[INFO] Building cleaned text from PDF...")
    cleaned = build_clean_text(mc, pdf)
    with open("clean_lessons.txt", 'w', encoding='utf-8') as f:
        f.write(cleaned)
    
    print("[INFO] Parsing lessons...")
    lessons = parse_lessons_simple(cleaned)
    print(f"Found {len(lessons)} lessons")
    if not lessons:
        raise SystemExit("No lessons extracted")

    print("[DB] Importing lessons...")
    cnt = import_lessons_to_db(lessons, clear_existing=args.clear)
    print(f"Imported {cnt} lessons")

    if args.verify:
        verify(len(lessons))


if __name__ == '__main__':
    main()

