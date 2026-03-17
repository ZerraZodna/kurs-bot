"""A tiny rule-based keyword language detector.

This detector is intentionally simple and deterministic so it can run
without native dependencies. It returns a tuple (code, confidence, meta).
"""
from __future__ import annotations

import re
from typing import Dict, Optional, Tuple

_LANG_KEYWORDS = {
    "en": {"the", "and", "is", "you", "do", "search", "please", "hello", "hi", "hey", "thanks", "thank"},
    "no": {"og", "det", "ikke", "jeg", "hei", "takk", "venn"},
}


def _tokens(text: str):
    return [t for t in re.split(r"\W+", text.lower()) if t]


def detect_language(text: str) -> Tuple[Optional[str], Optional[float], Dict]:
    """Detect language using keyword matches.

    Returns (iso_code, confidence [0-1], meta)
    """
    if not text or not text.strip():
        return None, None, {"method": "keyword"}

    tokens = _tokens(text)
    if not tokens:
        return None, None, {"method": "keyword"}

    scores = {}
    for code, kws in _LANG_KEYWORDS.items():
        matches = sum(1 for t in tokens if t in kws)
        if matches:
            coverage = matches / len(tokens)
            # Strong deterministic signal if coverage is high (e.g., single-token greeting)
            if coverage >= 0.8 or matches >= 2:
                conf = 0.95
            else:
                # Moderate confidence for partial keyword matches
                conf = min(0.9, 0.6 + 0.25 * coverage + 0.05 * matches)
            scores[code] = (matches, conf)

    if not scores:
        return None, None, {"method": "keyword"}

    # pick best by (matches, conf)
    best = max(scores.items(), key=lambda kv: (kv[1][0], kv[1][1]))
    code, (matches, conf) = best[0], best[1]

    # tie detection: if another language has equal matches, treat as ambiguous
    ties = [c for c, v in scores.items() if v[0] == matches and c != code]
    if ties:
        return None, float(conf) * 0.5, {"method": "keyword", "ambiguous_with": ties}

    return code, float(conf), {"method": "keyword", "matches": matches}
