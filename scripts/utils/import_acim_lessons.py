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
    # Only collapse spaced letters that spell "lesson" (case-insensitive),
    # optionally followed by spaced digits. Examples:
    #   "L E S S O N" -> "LESSON"
    #   "L E S S O N  1 0" -> "LESSON 10"
    if not text or ' ' not in text:
        return text

    def _collapse_lesson(m):
        letters = m.group(1)
        digits = m.group(2) or ''
        letters_collapsed = letters.replace(' ', '')
        if digits:
            digits_collapsed = re.sub(r"\s+", "", digits)
            return letters_collapsed + ' ' + digits_collapsed
        return letters_collapsed

    pattern = r'(?:\b|^)((?:l\s+e\s+s\s+s\s+o\s+n))((?:\s+\d){1,3})?(?:\b|$)'
    return re.sub(pattern, _collapse_lesson, text, flags=re.I)


def _span_styles_from_font(font_name: str) -> Tuple[bool, bool, bool]:
    n = (font_name or '').lower()
    bold = bool(re.search(r'bold|black|heavy|bd', n))
    italic = bool(re.search(r'italic|oblique|it|slanted', n))
    underline = bool(re.search(r'underline|ul', n))
    return bold, italic, underline


def extract_formatted_text(pdf_path: Path) -> str:
    """Return formatted text extracted from PDF using PyMuPDF (fitz).

    Text will use Markdown-like markers: **bold**, *italic*, __underline__.
    """
    if fitz is None:
        raise RuntimeError('PyMuPDF (fitz) is not installed')

    doc = fitz.open(str(pdf_path))
    text_runs = []

    for page_num, page in enumerate(doc, start=1):
        page_text_runs = []
        blocks = page.get_text('dict').get('blocks', [])
        for b in blocks:
            if b.get('type', 0) != 0:
                continue
            for line in b.get('lines', []):
                raw_parts = []
                styled_parts = []
                for span in line.get('spans', []):
                    raw = span.get('text', '')
                    if not raw:
                        continue
                    # normalize odd inter-letter spacing often introduced by PDF fonts
                    raw_norm = _normalize_spaced_letters(raw)
                    raw_parts.append(raw_norm)

                    font = span.get('font', '')
                    bold, italic, underline = _span_styles_from_font(font)
                    plain = raw_norm
                    if underline:
                        plain = f'__{plain}__'
                    if italic:
                        plain = f'*{plain}*'
                    if bold:
                        plain = f'**{plain}**'
                    styled_parts.append(plain)

                if raw_parts:
                    raw_line = ''.join(raw_parts).strip()
                    styled_line = ''.join(styled_parts).strip()
                    # store tuple (raw, styled) so we can detect headers/page numbers
                    page_text_runs.append((raw_line, styled_line))

        if page_text_runs:
            # page_text_runs is list of (raw, styled) tuples. Drop leading
            # page headers like "PART 1" or "WORKBOOK" using raw text.
            first_raw = page_text_runs[0][0].strip()
            compact = re.sub(r'[^A-Za-z0-9]', '', first_raw).lower()
            if re.match(r'^(?:part\d{1,3}|workbook\d{0,3})$', compact):
                page_text_runs.pop(0)
                if not page_text_runs:
                    continue

            # If the last visible line on the page is just a page number
            # drop it so page numbers don't appear in the combined text.
            last_raw = page_text_runs[-1][0].strip()
            if re.sub(r'[^0-9]', '', last_raw) == last_raw:
                digits_only = re.sub(r'\D', '', last_raw)
                if 1 <= len(digits_only) <= 3:
                    page_text_runs.pop()
                    if not page_text_runs:
                        continue

            # remove inline page-header tokens (e.g. PART I, PART 1, WORKBOOK)
            pattern_str = r"(?:\b(?:p\s*a\s*r\s*t(?:\s+(?:\d{1,3}|[ivxlcdm]+))?)\b|\bworkbook\b)"
            header_tok = re.compile(pattern_str, flags=re.IGNORECASE)
            styled_header_re = re.compile(r"[*_\"']*" + pattern_str + r"[*_\"']*", flags=re.IGNORECASE)
            cleaned_runs = []
            for raw, styled in page_text_runs:
                raw2 = header_tok.sub('', raw)
                # remove styled variants that may include asterisks/underscores
                styled2 = styled_header_re.sub('', styled)
                raw2 = raw2.strip()
                styled2 = styled2.strip()
                # skip lines that become empty after header removal
                if not raw2:
                    continue
                cleaned_runs.append((raw2, styled2))

            if not cleaned_runs:
                continue
            # append styled lines to text_runs
            text_runs.append('\n'.join(s for (_, s) in cleaned_runs))

    # Join page blocks intelligently: avoid inserting an extra blank
    # line when the next page continues the same paragraph. Preserve
    # raw newlines otherwise for debugging.
    if not text_runs:
        return ''
    joined = text_runs[0].rstrip()
    for blk in text_runs[1:]:
        curr = blk.rstrip()
        # get last visible token of joined and first token of curr
        prev_last = (joined.splitlines()[-1] if joined.splitlines() else '').strip()
        next_first = (curr.splitlines()[0] if curr.splitlines() else '').strip()

        # handle trailing hyphenation: join words directly
        if prev_last.endswith('-'):
            joined = joined.rstrip()[:-1] + next_first
            rest = '\n'.join(curr.splitlines()[1:])
            if rest:
                joined += '\n' + rest
            continue

        # If previous line ends with sentence-ending punctuation, keep a
        # paragraph break. If next line starts lowercase, treat as a
        # continuation and use a single newline.
        if re.search(r'[\.\!\?\:\;\"\)\]]$', prev_last):
            sep = '\n\n'
        elif re.match(r'^[a-z]', next_first):
            sep = '\n'
        else:
            sep = '\n\n'

        joined = joined + sep + curr

    # Normalize any excessive blank lines (3 or more) down to two.
    plain_text = re.sub(r'\n{3,}', '\n\n', joined)
    # Recompose paragraphs from lines using heuristics so each paragraph
    # ends with a single blank line. Heuristics used:
    # - hyphenation at line end joins words directly
    # - a blank line always separates paragraphs
    # - a following 'lesson' header starts a new paragraph
    # - if a line ends with sentence punctuation and the next line
    #   starts with a capital letter and looks like a new paragraph,
    #   treat it as a paragraph break
    lines = plain_text.splitlines()
    paragraphs = []
    current = []
    def flush_current():
        if not current:
            return
        para = ' '.join(current).strip()
        para = re.sub(r' {2,}', ' ', para)
        paragraphs.append(para)

    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s:
            flush_current()
            current = []
            continue

        # If current is empty, start new paragraph
        if not current:
            current.append(s)
            continue

        prev = current[-1]

        # hyphenation: join directly
        if prev.endswith('-'):
            current[-1] = prev[:-1] + s
            continue

        # If the next line is a lesson header, flush current paragraph
        if re.match(r'(?i)^lesson\b', s) or re.match(r'(?i)^lesson\s+\d', s):
            flush_current()
            current = [s]
            continue

        # Lookahead to decide paragraph break
        next_line = lines[i + 1].strip() if i + 1 < len(lines) else ''
        ends_sentence = bool(re.search(r'[\.\!\?\:\;\"\)\]]$', s))
        next_starts_cap = bool(re.match(r'^[A-Z0-9\"\(\[]', next_line))
        next_len = len(next_line)

        # Tightened rule: only treat as paragraph break when previous
        # line ends a sentence AND the next line looks like a true
        # paragraph start (long enough) or is an explicit header.
        is_header = bool(re.match(r'(?i)^(lesson\b|lesson\s+\d|intro|introduction|part\b|workbook\b)', next_line))
        if ends_sentence and next_starts_cap and (is_header or next_len > 60):
            current.append(s)
            flush_current()
            current = []
            continue

        # default: continuation of paragraph
        current.append(s)

    flush_current()
    # Merge paragraphs that are likely continuations introduced by
    # page breaks: if a paragraph starts with lowercase or the
    # previous paragraph doesn't end with sentence-ending punctuation,
    # merge it into the previous paragraph.
    merged = []
    for p in paragraphs:
        if not merged:
            merged.append(p)
            continue
        prev = merged[-1]
        p_strip = p.lstrip()
        if not p_strip:
            continue
        starts_lower = p_strip[0].islower()
        prev_ends_sentence = bool(re.search(r'[\.\!\?\"]$', prev.strip()))
        is_header = bool(re.match(r'(?i)^(lesson\b|lesson\s+\d|intro|introduction|part\b|workbook\b)', p_strip))
        # Never merge if the paragraph is an explicit header
        if is_header:
            merged.append(p)
            continue
        if starts_lower or not prev_ends_sentence:
            # merge into previous paragraph
            merged[-1] = prev.rstrip() + ' ' + p_strip
        else:
            merged.append(p)

    plain_text = '\n\n'.join(merged)

    # Final normalization: preserve paragraph separators but collapse
    # any remaining single newlines into spaces to avoid line-per-line breaks.
    marker = '<<PARA_BREAK>>'
    plain_text = plain_text.replace('\r\n', '\n')
    plain_text = plain_text.replace('\n\n', marker)
    plain_text = plain_text.replace('\n', ' ')
    plain_text = plain_text.replace(marker, '\n\n')
    return plain_text.strip()


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
        # Only treat a line as a lesson header if it is either the word
        # 'lesson' optionally followed by a number/roman numerals, or a
        # spaced-letter variant like 'L E S S O N'. This avoids false
        # positives such as lines that begin "lesson a day".
        if re.match(r'(?i)^(?:l\s*e\s*s\s*s\s*o\s*n\b|lesson(?:\s*(?:\d{1,3}|[ivxlcdm]+)\b)?$)', s_norm) or compact == 'lesson':
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
        # If the header returned a range (tuple), use the starting id
        # as the lesson id for DB import to avoid binding tuple params.
        if isinstance(lid, tuple):
            lid = lid[0]

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
    p.add_argument('--dump-text', type=Path, help='Write extracted text to this file for inspection')
    p.add_argument('--verify', default=True, type=lambda v: v.lower() not in ("false","0","no"))
    p.add_argument('--limit', type=int, help='Limit number of lessons to import (for testing)')
    ns = p.parse_args(argv)

    pdf = ns.pdf
    if not pdf.exists():
        print(f"PDF not found: {pdf}")
        return 2

    print(f"📖 Reading ACIM lessons from: {pdf}")
    text = extract_formatted_text(pdf)

    if getattr(ns, 'dump_text', None):
        try:
            out_path = ns.dump_text
            out_path.parent.mkdir(parents=True, exist_ok=True)
            # Normalize paragraphs: collapse intra-paragraph newlines and
            # ensure paragraphs are separated by exactly two newlines.
            t = text.replace('\r\n', '\n')
            # Split on double-newline; for safety collapse any 3+ newlines first
            t = re.sub(r'\n{3,}', '\n\n', t)
            parts = [p.strip() for p in t.split('\n\n') if p.strip()]
            normalized_parts = []
            for p in parts:
                # Preserve lines that begin with indentation or list markers
                # (these should remain on their own line), but collapse other
                # internal newlines into spaces so paragraphs are single blocks.
                # Keep: newline when followed by space/tab, asterisk, or opening
                # quote characters used in the source.
                pclean = re.sub(r'\r?\n(?=[ \t\*\"\u201c\u2018])', '\n', p)
                # collapse any other newlines into spaces
                pclean = re.sub(r'\r?\n+', ' ', pclean)
                pclean = re.sub(r'\s+', ' ', pclean).strip()
                normalized_parts.append(pclean)

            # Merge-pass: if a paragraph ends with a very short trailing token
            # (likely a page-break fragment) and the next paragraph starts
            # lowercase (continuation), merge them. Preserve explicit headers.
            merged_parts = []
            i = 0
            while i < len(normalized_parts):
                cur = normalized_parts[i]
                if i + 1 < len(normalized_parts):
                    nxt = normalized_parts[i + 1]
                    # guards
                    nxt_strip = nxt.lstrip()
                    is_header = bool(re.match(r'(?i)^(lesson\b|lesson\s+\d|intro|introduction|part\b|workbook\b)', nxt_strip))
                    # last token length (ignore punctuation)
                    last_tok = re.sub(r'[\W_]+$', '', (cur.split()[-1] if cur.split() else ''))
                    last_tok_len = len(last_tok)
                    cur_ends_sentence = bool(re.search(r'[\.\!\?\:\;\"\)\]]$', cur.strip()))
                    # if current does not end a sentence, last token is short, and next starts lowercase, merge
                    if (not cur_ends_sentence and last_tok_len > 0 and last_tok_len <= 4
                            and nxt_strip and nxt_strip[0].islower() and not is_header):
                        cur = cur.rstrip() + ' ' + nxt_strip
                        merged_parts.append(cur)
                        i += 2
                        continue
                merged_parts.append(cur)
                i += 1

            out_text = '\n\n'.join(merged_parts) + '\n'
            # Specific fix: join very short trailing fragments (likely page-break
            # leftovers) directly to a following 'lesson' continuation.
            short_join_re = re.compile(r'(?<![\.\!\?])\b(\w{1,4})\n\n(lesson\b)', flags=re.I)
            out_text = short_join_re.sub(r'\1 \2', out_text)

            # Targeted Lesson 1 formatting fixes: insert paragraph breaks
            # around the epigraph and before/after quoted lists so Lesson 1
            # appears as the expected set of paragraphs for inspection.
            try:
                low = out_text.lower().find('lesson 1')
                if low != -1:
                    hi = out_text.lower().find('\n\nlesson 2', low+1)
                    if hi == -1:
                        hi = out_text.lower().find('lesson 2', low+1)
                    block = out_text[low:hi] if hi != -1 else out_text[low:]
                    b = block
                    # break after the epigraph closing marker if present
                    b = re.sub(r'(”\*\*\*|"\*\*\*)\s*Now', r'\1\n\nNow', b)
                    # ensure a blank line before the first quoted example list
                    b = b.replace(': *"', ':\n\n*"')
                    b = b.replace(': *“', ':\n\n*“')
                    # separate the 'Then look farther away' sentence into its own paragraph
                    b = b.replace('*Then look farther away', '\n\nThen look farther away')
                    # write back if changed
                    if b != block:
                        out_text = out_text[:low] + b + (out_text[hi:] if hi != -1 else '')
            except Exception:
                pass
            # Ensure each adjacent italic quoted item appears on its own line
            # Example: *“This table does not mean anything.”* *“This chair...”* -> separate lines
            try:
                out_text = re.sub(r'(\*\u201c[^\u201d]+\u201d\*)\s+(?=\*\u201c)', r"\1\n", out_text)
            except Exception:
                # fallback for ASCII quotes
                out_text = re.sub(r'("\*[^\"]+\"\*)\s+(?=\")', r"\1\n", out_text)

            # Split consecutive bold-italic blocks (***...***) onto separate lines
            try:
                bold_italic_re = re.compile(r'(\*\*\*.*?\*\*\*)\s*(?=\*\*\*)', flags=re.DOTALL)
                out_text = bold_italic_re.sub(r'\1\n', out_text)
            except Exception:
                pass

            # Ensure each lesson header 'lesson N' starts on its own paragraph
            try:
                # Ensure each lesson header (e.g. 'lesson 1') is its own paragraph
                # Insert exactly one blank line before and after the header line.
                out_text = re.sub(
                    r"(?mi)(?<!\n\n)\n*\s*(lesson\s+\d{1,3}\b[^\n]*)",
                    r"\n\n\1\n\n",
                    out_text,
                )
                # Also normalize cases where multiple blank lines may now exist
                out_text = re.sub(r'\n{3,}', '\n\n', out_text)
                # If the header line contains additional content (e.g. 'lesson 1 ***...'),
                # split so the header stands alone and the rest starts after a blank line.
                out_text = re.sub(
                    r"(?mi)^(lesson\s+\d{1,3}\b)\s+([^\n\r]+)",
                    r"\1\n\n\2",
                    out_text,
                )
            except Exception:
                pass
            # Collapse any accidental double-blank-lines between consecutive
            # bold-italic blocks so they are separated by a single newline.
            try:
                out_text = re.sub(r'(?m)(\*\*\*.*?\*\*\*)\r?\n\s*\r?\n\s*(\*\*\*.*?\*\*\*)', r'\1\n\2', out_text, flags=re.DOTALL)
            except Exception:
                pass
            # Special-case: some PDFs produce a spaced-out 'to 365' after
            # the lesson header like "t o 3 6 5" on the next line. Normalize
            # that into a proper range on the header line so parsing picks
            # up the intended 'lesson 361 to 365'.
            try:
                out_text = re.sub(
                    r'(?mi)(lesson\s+361)\s*\n\s*\n\s*t\s*o\s*3\s*6\s*5',
                    r'\1 to 365\n\n',
                    out_text,
                )
            except Exception:
                pass
            out_path.write_text(out_text, encoding='utf8')
            print(f"🔧 Extracted text written to: {out_path}")
        except Exception as e:
            print(f"⚠️  Failed to write extracted text to {ns.dump_text}: {e}")

    # If we produced a normalized dump (`out_text`), use it as the
    # canonical source for parsing so the DB content matches the dump.
    if 'out_text' in locals():
        text = out_text

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
