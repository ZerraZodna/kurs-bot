#!/usr/bin/env python3
"""Importer: extract lessons from PDF and insert into DB.

This is the canonical importer (moved from single-file variant).
It uses the project extractor when available and will attach per-lesson
HTML snippets into `content_html` when possible.
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path
from typing import Tuple
import datetime
import fitz

# ensure repo root on path for imports
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.models.database import SessionLocal, Lesson, Base, engine

def _normalize_spaced_letters(text: str) -> str:
    # collapse sequences like "L E S S O N" or "l e s s o n" into "LESSON"/"lesson"
    if not text or ' ' not in text:
        return text
    def _collapse(m):
        return m.group(0).replace(' ', '')
    return re.sub(r'(?:\b|^)(?:[A-Za-z]\s){2,}[A-Za-z](?:\b|$)', _collapse, text)


def _span_styles_from_font(font_name: str) -> Tuple[bool, bool, bool]:
    n = (font_name or '').lower()
    bold = bool(re.search(r'bold|black|heavy|bd', n))
    italic = bool(re.search(r'italic|oblique|it|slanted', n))
    underline = bool(re.search(r'underline|ul', n))
    return bold, italic, underline


def extract_html_and_text(pdf_path: Path) -> str:
    """Return (html, plain_text) extracted from PDF using PyMuPDF (fitz).

    HTML will contain only simple tags: <b>, <i>, <u> and <div class="line"> wrappers.
    Plain text will use Markdown-like markers: **bold**, *italic*, __underline__.
    """
    if fitz is None:
        raise RuntimeError('PyMuPDF (fitz) is not installed')

    doc = fitz.open(str(pdf_path))
    text_runs = []

    for page_num, page in enumerate(doc, start=1):
        page_html_lines = []
        page_text_runs = []
        blocks = page.get_text('dict').get('blocks', [])
        for b in blocks:
            if b.get('type', 0) != 0:
                continue
            for line in b.get('lines', []):
                span_html_parts = []
                span_text_parts = []
                for span in line.get('spans', []):
                    text = span.get('text', '')
                    if not text:
                        continue
                    # normalize odd inter-letter spacing often introduced by PDF fonts
                    text = _normalize_spaced_letters(text)
                    font = span.get('font', '')
                    bold, italic, underline = _span_styles_from_font(font)
                    safe = (text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))
                    # build plain text with lightweight markdown
                    plain = text
                    if underline:
                        plain = f'__{plain}__'
                    if italic:
                        plain = f'*{plain}*'
                    if bold:
                        plain = f'**{plain}**'
                    span_text_parts.append(plain)
                if span_text_parts:
                    page_text_runs.append(''.join(span_text_parts))

        if page_text_runs:
            text_runs.append('\n'.join(page_text_runs))

    plain_text = '\n\n'.join(text_runs)
    # normalize excessive newlines
    plain_text = re.sub(r'\n{3,}', '\n\n', plain_text)
    return  plain_text


def parse_lessons_from_text(full_text: str) -> list[tuple[int, str, str]]:
    lines = full_text.splitlines()

    def _normalize_header_line(s: str) -> str:
        s = (s or '').strip()
        s = re.sub(r'^[^A-Za-z0-9]+', '', s)
        s = s.replace('*', '').replace('_', '').replace('`', '')
        s = s.replace('“', '"').replace('”', '"').replace('\u2019', "'")
        return s

    def extract_id_from_line(s: str):
        s2 = _normalize_header_line(s)
        s_digits = re.sub(r'(?<=\d)\s+(?=\d)', '', s2)
        mrange = re.search(r"(\d{1,3})\s*(?:to|-|–)\s*(\d{1,3})", s_digits, flags=re.I)
        if mrange:
            return (int(mrange.group(1)), int(mrange.group(2)))
        m = re.search(r'Lesson\s*(\d{1,3})', s_digits, flags=re.I)
        if m:
            return int(m.group(1))
        m2 = re.match(r"^\s*(\d{1,3})\b", s_digits)
        if m2:
            return int(m2.group(1))
        return None

    headers = []
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s:
            continue
        s_norm = _normalize_header_line(s)
        compact = re.sub(r"\s+", "", s_norm).lower()
        if re.match(r'^(?:l\s*e\s*s\s*s\s*o\s*n|lesson)\b', s_norm, flags=re.I) or compact.startswith('lesson'):
            lid = extract_id_from_line(s_norm)
            if lid is None:
                for j in range(i + 1, min(i + 6, len(lines))):
                    mnum_line = _normalize_header_line(lines[j])
                    mnum_line_digits = re.sub(r'(?<=\d)\s+(?=\d)', '', mnum_line)
                    mnum = re.match(r"^\s*(\d{1,3})\b", mnum_line_digits)
                    if mnum:
                        lid = int(mnum.group(1))
                        break
            headers.append((i, lid))

    if not headers:
        return []

    lessons_raw = []
    for idx in range(len(headers)):
        start_line, lid = headers[idx]
        end_line = headers[idx + 1][0] if idx + 1 < len(headers) else len(lines)
        block_lines = lines[start_line:end_line]
        block = "\n".join(block_lines).strip()
        if len(block) < 60:
            continue
        block = re.sub(r"(\d(?:\s+\d){1,3})\s*(?:t\s*o|-|–)\s*(\d(?:\s+\d){1,3})",
                       lambda m: re.sub(r"\s+", "", m.group(1)) + ' to ' + re.sub(r"\s+", "", m.group(2)),
                       block,
                       flags=re.I)
        block = re.sub(r'(?mi)(lesson)\s+((?:\d\s+){1,3}\d)', lambda m: m.group(1) + ' ' + re.sub(r'\s+', '', m.group(2)), block)
        first_line = block.splitlines()[0].strip()
        if re.match(r'(?i)^(part\b|workbook\b|page\b)', first_line):
            continue
        tmatch = re.search(r'"([^"]{5,200})"', block)
        if tmatch:
            title = tmatch.group(1).strip()
        else:
            blines = [l.strip() for l in block.splitlines() if l.strip()]
            title = blines[1][:128] if len(blines) > 1 else (f'Lesson {lid}' if lid else 'Lesson')
        lessons_raw.append((lid, title, block))

    out = []
    if lessons_raw:
        first_header_line = headers[0][0]
        for idx, (hl, lid) in enumerate(headers):
            val = lid[0] if isinstance(lid, tuple) else lid
            if val == 1:
                first_header_line = hl
                break
        if first_header_line > 0:
            intro_lines = lines[:first_header_line]
            intro_block = "\n".join(l.strip() for l in intro_lines if l.strip()).strip()
            if len(intro_block) > 80:
                out.append((0, 'Introduction', intro_block))

    seen = set()
    seq = 1
    for lid, title, content in lessons_raw:
        if lid is None:
            lid = seq
            seq += 1
        if lid in seen:
            for i, (ol, ot, oc) in enumerate(out):
                if ol == lid:
                    out[i] = (ol, ot, oc + "\n\n" + content)
                    break
            continue
        seen.add(lid)
        out.append((lid, title, content))
    return out


def import_to_db(lessons, clear=False, limit=None, full_html=None):
    if limit is not None:
        lessons = lessons[:limit]
    session = SessionLocal()
    try:
        if clear:
            session.query(Lesson).delete()
            session.commit()
        added = 0
        for lid, title, content in lessons:
            exists = session.query(Lesson).filter(Lesson.lesson_id == lid).first()
            if exists:
                continue
            lesson = Lesson(
                lesson_id=lid,
                title=(title or '')[:128],
                content=content,
                difficulty_level='beginner',
                duration_minutes=15,
                created_at=datetime.datetime.utcnow(),
            )
            session.add(lesson)
            try:
                session.flush()
                added += 1
            except Exception:
                session.rollback()
                continue
            if added % 50 == 0:
                session.commit()
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


def main(argv=None):
    p = argparse.ArgumentParser(description="Import ACIM lessons from PDF into DB")
    p.add_argument('--pdf', type=Path, default=Path('src/data/Sparkly ACIM lessons-extracted.pdf'))
    p.add_argument('--no-clear', action='store_true', help='Do not clear existing lessons')
    p.add_argument('--verify', default=True, type=lambda v: v.lower() not in ("false","0","no"))
    p.add_argument('--limit', type=int, help='Limit number of lessons to import (for testing)')
    ns = p.parse_args(argv)

    pdf = ns.pdf
    if not pdf.exists():
        print(f"PDF not found: {pdf}")
        return 2

    print(f"📖 Reading ACIM lessons from: {pdf}")
    text = extract_html_and_text(pdf)

    print("🔍 Extracting lessons from PDF...")
    lessons = parse_lessons_from_text(text)
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
