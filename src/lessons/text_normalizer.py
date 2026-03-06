"""Text normalization functions for ACIM lessons."""
from __future__ import annotations

import re
from typing import Optional


def _normalize_sentence_spacing(text: str) -> str:
    """Repair common PDF/OCR spacing artifacts after sentence punctuation."""
    s = text or ""
    # Add missing space after punctuation when next token starts a new word/quote.
    s = re.sub(r'([\.,!?])(?=[A-Za-z""])', r'\1 ', s)
    # Add missing space after closing quotes before a letter.
    s = re.sub(r'([''"])(?=[A-Za-z])', r'\1 ', s)
    # Collapse accidental multi-spaces introduced during repair.
    s = re.sub(r' {2,}', ' ', s)
    return s


def _normalize_lesson_content_header(content: str, lesson_id: int) -> str:
    """Ensure lesson content starts with canonical `Lesson <id>` header."""
    txt = (content or '').strip()
    if not txt:
        return txt

    # Convert leading variants like `lesson 14`, `LESSON 14`, `lesson 14 to 20`
    # into `Lesson 14` to enforce a stable canonical prefix.
    txt = re.sub(
        r'(?is)^\s*lesson\s+\d{1,3}(?:\s*(?:to|-|–)\s*\d{1,3})?\b',
        f'Lesson {lesson_id}',
        txt,
        count=1,
    )

    # If no leading lesson header exists, prepend one.
    if not re.match(rf'(?i)^\s*Lesson\s+{lesson_id}\b', txt):
        txt = f'Lesson {lesson_id}\n\n{txt}'

    # Lesson 1 formatting preference: keep this sentence attached to the prior paragraph.
    txt = re.sub(
        r'\n\n(One thing is like another as far as the application of the idea is concerned\.)',
        r' \1',
        txt,
        flags=re.I,
    )

    return txt


def _normalize_extracted_text_for_dump(text: str) -> str:
    """Normalize extracted text into paragraph blocks for parsing.

    This preserves the original dump-processing heuristics and targeted
    fixes while returning the normalized text so parsing is consistent
    whether or not the user requests a dump file.
    """
    try:
        t = text.replace('\r\n', '\n')
        t = re.sub(r'\n{3,}', '\n\n', t)
        parts = [p.strip() for p in t.split('\n\n') if p.strip()]
        normalized_parts = []
        for p in parts:
            pclean = re.sub(r'\r?\n(?=[ \t\*\"\u201c\u2018])', '\n', p)
            pclean = re.sub(r'\r?\n+', ' ', pclean)
            pclean = re.sub(r'\s+', ' ', pclean).strip()
            normalized_parts.append(pclean)

        merged_parts = []
        i = 0
        while i < len(normalized_parts):
            cur = normalized_parts[i]
            if i + 1 < len(normalized_parts):
                nxt = normalized_parts[i + 1]
                nxt_strip = nxt.lstrip()
                is_header = bool(re.match(r'(?i)^(lesson\b|lesson\s+\d|intro|introduction|part\b|workbook\b)', nxt_strip))
                last_tok = re.sub(r'[\W_]+$', '', (cur.split()[-1] if cur.split() else ''))
                last_tok_len = len(last_tok)
                cur_ends_sentence = bool(re.search(r'[\.\!\?\:\;"\)\]]$', cur.strip()))
                if (not cur_ends_sentence and last_tok_len > 0 and last_tok_len <= 4
                        and nxt_strip and nxt_strip[0].islower() and not is_header):
                    cur = cur.rstrip() + ' ' + nxt_strip
                    merged_parts.append(cur)
                    i += 2
                    continue
            merged_parts.append(cur)
            i += 1

        out_text = '\n\n'.join(merged_parts) + '\n'

        short_join_re = re.compile(r'(?<![\.\!\?])\b(\w{1,4})\n\n(lesson\b)', flags=re.I)
        out_text = short_join_re.sub(r'\1 \2', out_text)

        try:
            low = out_text.lower().find('lesson 1')
            if low != -1:
                hi = out_text.lower().find('\n\nlesson 2', low+1)
                if hi == -1:
                    hi = out_text.lower().find('lesson 2', low+1)
                block = out_text[low:hi] if hi != -1 else out_text[low:]
                b = block
                b = re.sub(r'(''\*\*\*|"\*\*\*)\s*Now', r'\1\n\nNow', b)
                b = b.replace(': *"', ':\n\n*"')
                b = b.replace(': *"', ':\n\n*"')
                b = b.replace(': *"', ':\n\n*"')
                b = b.replace('*Then look farther away', '\n\nThen look farther away')
                if b != block:
                    out_text = out_text[:low] + b + (out_text[hi:] if hi != -1 else '')
        except Exception:
            pass

        try:
            out_text = re.sub(r'(\*\u201c[^\u201d]+\u201d\*)\s+(?=\*\u201c)', r"\1\n", out_text)
        except Exception:
            out_text = re.sub(r'("\*[^\"]+"\*)\s+(?=")', r"\1\n", out_text)

        try:
            bold_italic_re = re.compile(r'(\*\*\*.*?\*\*\*)\s*(?=\*\*\*)', flags=re.DOTALL)
            out_text = bold_italic_re.sub(r'\1\n', out_text)
        except Exception:
            pass

        try:
            out_text = re.sub(
                r"(?mi)(?<!\n\n)\n*\s*(lesson\s+\d{1,3}\b[^\n]*)",
                r"\n\n\1\n\n",
                out_text,
            )
            out_text = re.sub(r'\n{3,}', '\n\n', out_text)
            out_text = re.sub(r"(?mi)^(lesson\s+\d{1,3}\b)\s+([^\n\r]+)", r"\1\n\n\2", out_text)
        except Exception:
            pass

        try:
            out_text = re.sub(r'(?m)(\*\*\*.*?\*\*\*)\r?\n\s*\r?\n\s*(\*\*\*.*?\*\*\*)', r'\1\n\2', out_text, flags=re.DOTALL)
        except Exception:
            pass

        try:
            out_text = re.sub(
                r'(?mi)(lesson\s+361)\s*\n\s*\n\s*t\s*o\s*3\s*6\s*5',
                r'\1 to 365\n\n',
                out_text,
            )
        except Exception:
            pass

        return out_text
    except Exception:
        return text


def normalize_dump_text(text: str) -> str:
    """Normalize extracted text for dump file output.

    This applies the same paragraph normalization as used in the original
    script's dump-text functionality.
    """
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

    # Apply same newline substitutions as extract_formatted_text()
    # to preserve </em></b> -> newline transformations
    out_text = re.sub(r'</em></b> ', r'</em></b>\n', out_text)
    out_text = re.sub(r'</em> ', r'</em>\n', out_text)

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

    return out_text

