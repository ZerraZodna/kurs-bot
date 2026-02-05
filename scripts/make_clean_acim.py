#!/usr/bin/env python3
"""
Consolidated pipeline moved into scripts so import is self-contained.
- extract raw text from PDF (PyMuPDF or pdfplumber)
- extract styled paragraphs preserving bold/italic as Markdown markers
- merge styled markers back into the raw text where they best match
- apply small cleaning rules and return final text

"""
import re
from typing import List, Tuple


def extract_raw_text(pdf_path: str) -> str:
    try:
        import fitz
    except Exception:
        fitz = None

    if fitz is not None:
        doc = fitz.open(pdf_path)
        parts = []
        for page in doc:
            text = page.get_text("text") or ""
            parts.append(text)
            if not text.endswith("\n"):
                parts.append("\n")
        return "".join(parts)

    # fallback to pdfplumber
    try:
        import pdfplumber
    except Exception:
        raise RuntimeError("Install pymupdf or pdfplumber to extract PDF text")
    with pdfplumber.open(pdf_path) as doc:
        parts = []
        for page in doc.pages:
            text = page.extract_text() or ""
            parts.append(text)
            if not text.endswith("\n"):
                parts.append("\n")
    return "".join(parts)


def detect_style(fontname: str) -> Tuple[bool, bool]:
    n = (fontname or "").lower()
    is_bold = bool(re.search(r"bold|black|heavy|bd", n))
    is_italic = bool(re.search(r"italic|oblique|it|slanted", n))
    return is_bold, is_italic


def wrap_text(txt: str, bold: bool, italic: bool) -> str:
    if not txt:
        return txt
    if bold and italic:
        return f"***{txt}***"
    if bold:
        return f"**{txt}**"
    if italic:
        return f"*{txt}*"
    return txt


def extract_preserve_styles(pdf_path: str) -> List[str]:
    # Try pdfplumber first (character-level info)
    try:
        import pdfplumber
    except Exception:
        pdfplumber = None

    if pdfplumber is not None:
        paras = []
        with pdfplumber.open(pdf_path) as doc:
            for page in doc.pages:
                chars = page.chars
                if not chars:
                    continue
                lines = {}
                for c in chars:
                    top = int(round(c.get("top", 0)))
                    lines.setdefault(top, []).append(c)
                for top in sorted(lines.keys()):
                    row = lines[top]
                    row.sort(key=lambda x: x.get("x0", 0))
                    parts = []
                    cur_style = None
                    buf = ""
                    for ch in row:
                        ch_text = ch.get("text", "")
                        font = ch.get("fontname", "")
                        style = detect_style(font)
                        if cur_style is None:
                            cur_style = style
                            buf = ch_text
                        elif style == cur_style:
                            buf += ch_text
                        else:
                            parts.append(wrap_text(buf, *cur_style))
                            buf = ch_text
                            cur_style = style
                    if buf:
                        parts.append(wrap_text(buf, *cur_style))
                    line_text = "".join(parts).strip()
                    if line_text:
                        paras.append(line_text)
        if paras:
            return paras

    # fallback to pymupdf spans
    try:
        import fitz
    except Exception:
        fitz = None
    if fitz is None:
        raise RuntimeError("No PDF backend available. Install pdfplumber or pymupdf.")

    paras = []
    doc = fitz.open(pdf_path)
    for page in doc:
        blocks = page.get_text("dict").get("blocks", [])
        for b in blocks:
            if b.get("type", 0) != 0:
                continue
            lines = []
            for line in b.get("lines", []):
                parts = []
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    font = span.get("font", "")
                    bold, italic = detect_style(font)
                    parts.append(wrap_text(text, bold, italic))
                line_text = "".join(parts)
                lines.append(line_text)
            para = " ".join(l.strip() for l in lines if l.strip() != "")
            if para:
                paras.append(para)
    return paras


def find_next(raw, snippet, start=0, _cache={}) -> int:
    import bisect

    key = id(raw)
    if key not in _cache:
        norm_chars = []
        mapping = []
        i = 0
        L = len(raw)
        while i < L:
            if raw[i].isspace():
                j = i + 1
                while j < L and raw[j].isspace():
                    j += 1
                norm_chars.append(' ')
                mapping.append(i)
                i = j
            else:
                norm_chars.append(raw[i])
                mapping.append(i)
                i += 1
        norm_raw = ''.join(norm_chars)
        _cache[key] = (norm_raw, mapping)

    norm_raw, mapping = _cache[key]
    ni = bisect.bisect_left(mapping, start)
    if ni >= len(mapping):
        return -1
    snip_norm = re.sub(r"\s+", " ", snippet)
    idx_norm = norm_raw.find(snip_norm, ni)
    if idx_norm != -1:
        return mapping[idx_norm]
    pat = re.escape(snip_norm).replace('\\ ', r'\\s+')
    m = re.search(pat, norm_raw[ni:], flags=re.S)
    if m:
        return mapping[ni + m.start()]
    return -1


def merge_styles_into_raw(extracted_text: str, raw_text: str) -> str:
    spans = []
    for m in re.finditer(r"(\*{1,3})(.+?)\1", extracted_text, flags=re.S):
        stars = len(m.group(1))
        inner = m.group(2)
        spans.append((inner, stars))

    candidates = []
    for i, (inner, stars) in enumerate(spans):
        idx = find_next(raw_text, inner, 0)
        if idx != -1:
            candidates.append((idx, i, inner, stars))

    candidates.sort(key=lambda x: x[0])
    out_parts = []
    pos = 0
    for idx, _, inner, stars in candidates:
        if idx < pos:
            continue
        out_parts.append(raw_text[pos:idx])
        marker = '*' * stars
        out_parts.append(marker + inner + marker)
        pos = idx + len(inner)

    out_parts.append(raw_text[pos:])
    return ''.join(out_parts)


def clean_merged_text(merged: str) -> str:
    lines = merged.splitlines(keepends=True)
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.upper() == 'WORKBOOK':
            next_idx = i + 1
            if next_idx < len(lines) and lines[next_idx].strip().isdigit():
                i = next_idx + 1
                continue
        if re.match(r'^\*PART\s+I\*$', stripped):
            next_idx = i + 1
            if next_idx < len(lines) and lines[next_idx].strip().isdigit():
                i = next_idx + 1
                continue
        if re.match(r'^\*PART\s+2\*$', stripped):
            next_idx = i + 1
            if next_idx < len(lines) and lines[next_idx].strip().isdigit():
                i = next_idx + 1
                continue
        if re.match(r'^PART\b', stripped.upper()):
            next_idx = i + 1
            if next_idx < len(lines) and lines[next_idx].strip().isdigit():
                i = next_idx + 1
                continue
        line = re.sub(r'l\s+e\s+s\s+s\s+o\s+n', '\nLesson', line, flags=re.I)
        line = re.sub(r'(Lesson)(\s+)(\d(?:\s+\d)+)',
                      lambda m: m.group(1) + ' ' + re.sub(r'\s+', '', m.group(3)),
                      line)
        out.append(line)
        i += 1
    return ''.join(out)


def main_cli_extract(pdf_path: str, out_path: str | None = None) -> None:
    raw = extract_raw_text(pdf_path)
    paras = extract_preserve_styles(pdf_path)
    extracted_text = "\n\n".join(paras)
    merged = merge_styles_into_raw(extracted_text, raw)
    cleaned = clean_merged_text(merged)
    if out_path:
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(cleaned)
    return cleaned


if __name__ == '__main__':
    print('This module is intended to be imported by the importer script.')
