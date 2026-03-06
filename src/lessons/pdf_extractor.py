"""PDF extraction for ACIM lessons using PyMuPDF (fitz)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Tuple

import fitz


def _normalize_spaced_letters(text: str) -> str:
    """Collapse spaced letters that spell 'lesson' into normal text.

    Only collapses spaced letters that spell "lesson" (case-insensitive),
    optionally followed by spaced digits. Examples:
      "L E S S O N" -> "LESSON"
      "L E S S O N  1 0" -> "LESSON 10"
    """
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
    """Determine bold, italic, underline from font name."""
    n = (font_name or '').lower()
    bold = bool(re.search(r'bold|black|heavy|bd', n))
    italic = bool(re.search(r'italic|oblique|it|slanted', n))
    underline = bool(re.search(r'underline|ul', n))
    return bold, italic, underline


def extract_formatted_text(pdf_path: Path) -> str:
    """Return formatted text extracted from PDF using PyMuPDF (fitz).

    Text will use HTML-like markers: <b>, <em>, <u>
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
                line_bbox = line.get('bbox', [0, 0, 0, 0])
                line_x0 = float(line_bbox[0]) if line_bbox else 0.0
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
                        plain = f'<u>{plain}</u>'
                    if italic:
                        plain = f'<em>{plain}</em>'
                    if bold:
                        plain = f'<b>{plain}</b>'
                    styled_parts.append(plain)

                if raw_parts:
                    raw_line = ''.join(raw_parts).strip()
                    styled_line = ''.join(styled_parts).strip()
                    # store tuple (raw, styled, x0) so we can detect headers/page numbers and indentation
                    page_text_runs.append((raw_line, styled_line, line_x0))

        if page_text_runs:
            # page_text_runs is list of (raw, styled, x0) tuples. Drop leading
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
            # Estimate left margin per page and mark strongly-indented lines.
            x_candidates = [x0 for (raw, _styled, x0) in page_text_runs if (raw or '').strip()]
            base_x = min(x_candidates) if x_candidates else 0.0

            for raw, styled, x0 in page_text_runs:
                raw2 = header_tok.sub('', raw)
                # remove styled variants that may include asterisks/underscores
                styled2 = styled_header_re.sub('', styled)
                raw2 = raw2.strip()
                styled2 = styled2.strip()
                # skip lines that become empty after header removal
                if not raw2:
                    continue

                # Preserve visual structure: lines with notable indentation should
                # remain line-broken later instead of being merged into prior text.
                # Avoid tagging lesson headers themselves.
                is_lesson_header = bool(re.match(r'(?i)^lesson\s+\d{1,3}(?:\s*(?:to|-|–)\s*\d{1,3})?\b', raw2))
                if (x0 - base_x) >= 12 and not is_lesson_header:
                    styled2 = f'<<INDENT>> {styled2}'

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

        is_indented_marker = s.startswith('<<INDENT>>')
        if is_indented_marker:
            s = s.replace('<<INDENT>>', '', 1).strip()
            # Keep indented visual lines as their own line/paragraph unit.
            flush_current()
            current = [s]
            flush_current()
            current = []
            continue

        # Keep standalone quoted exercise lines on their own line/paragraph.
        # This preserves structures like:
        # "This table does not mean anything."
        is_quoted_line = bool(re.match(r'^(?:<[biuems]+>|</?[biuems]+>)*["][^\n]{3,220}["][.!?]?(?:</[biuems]+>)*$', s))
        if is_quoted_line:
            flush_current()
            current = [s]
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
        is_quoted_para = bool(re.match(r'^[*]*[""].+[""][.!?]?[*]*$', p_strip))
        prev_is_colon_intro = prev.strip().endswith(':')
        # Never merge if the paragraph is an explicit header or a quoted exercise line
        if is_header or is_quoted_para:
            merged.append(p)
            continue
        # If previous paragraph introduces a list (colon), keep the next paragraph separate
        if prev_is_colon_intro:
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

    # Replace bold italcs start/stop "space" bold italic with a new line break
    # Example:  <b><em>"Nothing I see in this room [on this street,</em></b> <b><em>from this window, in this place] means anything."</em></b> Now look slowly around 
    # Here we want a NewLine after "</em></b> " -> "</em>>/b>\n" 
    # New:  <b><em>"Nothing I see in this room [on this street,</em></b>\n<b><em>from this window, in this place] means anything."</em></b>\nNow look slowly around 
    plain_text = re.sub(
        '</em></b> ',
        '</em></b>\n',
        plain_text,
    )

    # <em>"I can escape from the world by giving </em> <em>up attack thoughts about _____."</em> Hold each attack thought in m
    # <em>"I can escape from the world by giving </em>\n<em>up attack thoughts about _____."</em>\nHold each attack thought in m
    plain_text = re.sub('</em> ', '</em>\n', plain_text)

    # PDF keystone thinks we dont need " " between ".T" -> ". T"
    plain_text = re.sub(r'\.T', '. T', plain_text)

    return plain_text.strip()

