"""Lesson parsing from extracted text."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from .text_normalizer import (
    _normalize_lesson_content_header,
    _normalize_sentence_spacing,
)


def extract_title(block: str) -> str:
    """Extract title - just get first sentence after lesson header."""

    # Join lines with spaces first (so multi-line quotes become one line)
    text = " ".join(block.split("\n"))

    # Strip all HTML tags
    text = re.sub(r"</?[a-z]+>", "", text, flags=re.IGNORECASE)

    # Find first sentence - everything up to first .! or ?
    match = re.match(r"^([^.!?]+[.!?])", text)
    if match:
        title = match.group(1).strip()
        if len(title) > 5:
            # Remove "lesson N " prefix if present
            title = re.sub(r"^lesson\s+\d+\s+", "", title, flags=re.I)
            # Strip leading quotes (ASCII ", curly " and ")
            title = re.sub(r"^[\u0022\u201c\u201d]+", "", title)
            return title[:128]

    return "Lesson"


def _normalize_header_line(s: str) -> str:
    """Normalize a header line for matching."""
    s = (s or "").strip()
    s = re.sub(r"^[^A-Za-z0-9]+", "", s)
    s = s.replace("*", "").replace("_", "").replace("`", "")
    s = s.replace('"', '"').replace('"', '"').replace("\u2019", "'")
    return s


def _extract_id_from_line(s: str) -> Optional[int | Tuple[int, int]]:
    """Extract lesson ID(s) from a normalized header line.

    Returns:
        - int: single lesson ID
        - tuple of (start, end): range of lesson IDs
        - None: if no ID could be extracted
    """
    s2 = _normalize_header_line(s)
    s_digits = re.sub(r"(?<=\d)\s+(?=\d)", "", s2)
    mrange = re.search(r"(\d{1,3})\s*(?:to|-|–)\s*(\d{1,3})", s_digits, flags=re.I)
    if mrange:
        return (int(mrange.group(1)), int(mrange.group(2)))
    m = re.search(r"Lesson\s*(\d{1,3})", s_digits, flags=re.I)
    if m:
        return int(m.group(1))
    m2 = re.match(r"^\s*(\d{1,3})\b", s_digits)
    if m2:
        return int(m2.group(1))
    return None


def parse_lessons_from_text(full_text: str) -> List[Tuple[int, str, str]]:
    """Parse lessons from extracted text.

    Returns:
        List of (lesson_id, title, content) tuples.
    """
    lines = full_text.splitlines()

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
        if (
            re.match(r"(?i)^(?:l\s*e\s*s\s*s\s*o\s*n\b|lesson(?:\s*(?:\d{1,3}|[ivxlcdm]+)\b)?$)", s_norm)
            or compact == "lesson"
        ):
            lid = _extract_id_from_line(s_norm)
            if lid is None:
                for j in range(i + 1, min(i + 6, len(lines))):
                    mnum_line = _normalize_header_line(lines[j])
                    mnum_line_digits = re.sub(r"(?<=\d)\s+(?=\d)", "", mnum_line)
                    mnum = re.match(r"^\s*(\d{1,3})\b", mnum_line_digits)
                    if mnum:
                        lid = int(mnum.group(1))
                        break
            # Only keep headers with a resolvable numeric lesson id.
            # This avoids false positives like "lesson a day".
            if lid is not None:
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
        block = re.sub(
            r"(\d(?:\s+\d){1,3})\s*(?:t\s*o|-|–)\s*(\d(?:\s+\d){1,3})",
            lambda m: re.sub(r"\s+", "", m.group(1)) + " to " + re.sub(r"\s+", "", m.group(2)),
            block,
            flags=re.I,
        )
        block = re.sub(
            r"(?mi)(lesson)\s+((?:\d\s+){1,3}\d)", lambda m: m.group(1) + " " + re.sub(r"\s+", "", m.group(2)), block
        )
        first_line = block.splitlines()[0].strip()
        if re.match(r"(?i)^(part\b|workbook\b|page\b)", first_line):
            continue

        # Title extraction priority:
        # 1) Quoted lesson title (ASCII or curly quotes)
        # 2) First sentence after the lesson header line
        # 3) Fallback lesson label
        title = extract_title(block)
        lessons_raw.append((lid, title, block))

    out = []
    if lessons_raw:
        first_header_line = headers[0][0]
        for _idx, (hl, lid) in enumerate(headers):
            val = lid[0] if isinstance(lid, tuple) else lid
            if val == 1:
                first_header_line = hl
                break
        if first_header_line > 0:
            intro_lines = lines[:first_header_line]
            intro_block = "\n".join(line.strip() for line in intro_lines if line.strip()).strip()
            if len(intro_block) > 80:
                out.append((0, "Introduction", intro_block))

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
        content = _normalize_sentence_spacing(content)
        content = _normalize_lesson_content_header(content, lid)
        out.append((lid, title, content))
    return out
