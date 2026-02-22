"""Clean language detection + storage utilities.

This module provides a minimal, testable implementation that:
- Uses the detector wrapper (`simple_detector.detect_language`) to get a language code and confidence
- Stores two-letter language codes (e.g. `en`, `no`) in memories
- Implements a tiny N=3 on-demand voting rule by querying the last 2 inbound messages from the DB
- Provides a single entrypoint `detect_and_store_language` used by higher-level code

The implementation intentionally avoids old ad-hoc mappings and string conversions.
"""

from typing import Optional
from collections import Counter
import re

from langdetect import detect_langs
from src.services.language.keyword_detector import detect_language as keyword_detect
from src.config import settings
from src.memories.constants import MemoryCategory, MemoryKey

# Comprehensive supported ISO-639-1 two-letter codes.
# This whitelist is used to validate LLM outputs before accepting
# them as a canonical `user_language` value. Keeping the set here
# prevents accidentally storing unsupported or spuriously matched
# two-letter tokens (e.g. English words like "in"/"on").
SUPPORTED_ISO = {
	"aa", "ab", "af", "ak", "sq", "am", "ar", "an", "hy", "as", "av", "ae", "ay", "az",
	"ba", "bm", "eu", "be", "bn", "bh", "bi", "bs", "br", "bg", "my", "ca", "ch", "ce",
	"ny", "zh", "cv", "kw", "co", "cr", "hr", "cs", "da", "dv", "nl", "dz", "en", "eo",
	"et", "ee", "fo", "fi", "fj", "fr", "ff", "gl", "ka", "de", "el", "gn", "gu", "ht",
	"ha", "he", "hz", "hi", "ho", "hu", "is", "io", "ig", "id", "ia", "ie", "iu", "ik",
	"ga", "it", "ja", "jv", "kl", "kn", "kr", "ks", "kk", "km", "ki", "rw", "ky", "kv",
	"kg", "ko", "ku", "kj", "la", "lb", "lg", "li", "ln", "lo", "lt", "lu", "lv", "gv",
	"mk", "mg", "ms", "ml", "mt", "mi", "mr", "mh", "mn", "na", "nv", "nd", "ne", "ng",
	"nb", "nn", "no", "ii", "nr", "oc", "oj", "cu", "or", "om", "os", "pa", "pi", "fa",
	"pl", "ps", "pt", "qu", "rm", "ro", "rn", "ru", "sa", "sc", "sd", "se", "sm", "sg",
	"sr", "gd", "sn", "si", "sk", "sl", "so", "st", "es", "su", "sw", "ss", "sv", "ta",
	"te", "tg", "th", "ti", "bo", "tk", "tl", "tn", "to", "tr", "ts", "tt", "tw", "ty",
	"ug", "uk", "ur", "uz", "ve", "vi", "vo", "wa", "cy", "wo", "xh", "yi", "yo", "za",
	"zu",
}


async def detect_language(text: str):
	"""Composite detection: keyword detector -> optional LLM confirm -> langdetect fallback.

	Returns (code, confidence, meta)
	"""
	# 1) keyword detector first (deterministic, fast)
	kw_code, kw_conf, kw_meta = keyword_detect(text)
	if kw_code and (kw_conf or 0.0) >= 0.75:
		return kw_code, kw_conf, kw_meta

	# 2) if keyword detected but moderate confidence, ask Ollama for confirmation
	if kw_code and (kw_conf or 0.0) >= 0.5:
		prompt = (
			"You are a language classifier. Determine the PRIMARY language of the text below and "
			"RETURN ONLY the two-letter ISO 639-1 code (for example: en, no, de, fr). "
			"Do NOT include any extra text or explanation — place the two-letter code on a single line.\n\n"
			"Examples:\nHello -> en\nHei -> no\nDanke -> de\nMerci -> fr\n\n"
			"Text:\n\n" + text + "\n\nReturn only the ISO code:"
		)
		try:
			# Import lazily to avoid circular package import at module import time
			from src.services.dialogue.ollama_client import call_ollama

			resp = await call_ollama(prompt, model=settings.OLLAMA_CHAT_RAG_MODEL, language="en")
		except Exception:
			resp = ""
		if resp:
			resp_lower = resp.strip().lower()
			# Accept only recognized ISO-639-1 two-letter codes to avoid
			# accidental matches on common English words (e.g. 'in', 'on').
			# Prefer an exact two-letter code on its own line (strict)
			for line in resp_lower.splitlines():
				line = line.strip()
				if re.fullmatch(r"[a-z]{2}", line) and line in SUPPORTED_ISO:
					return line, 0.92, {"method": "ollama_confirm", "raw": resp}
			# Do not accept inline tokens (e.g. 'No language...') as valid codes.

	# 3) final fallback to langdetect
	try:
		res = detect_langs(text)
		if not res:
			return None, None, {"method": "langdetect"}
		top = res[0]
		return top.lang, float(top.prob), {"method": "langdetect"}
	except Exception:
		return None, None, {"method": "langdetect"}


from src.memories import MemoryManager
from src.models.database import MessageLog


async def detect_and_store_language(
    memory_manager: MemoryManager,
    user_id: int,
    user_message: str,
) -> Optional[str]:
    """Detect language for `user_message` and store `user_language` memory."""

    # Keep only Norwegian/English support. If user has an existing preference,
    # return it. If not, run the lightweight `keyword_detect` and store only
    # `en` or `no` (map `nb`/`nn` -> `no`). If detection fails, default to `en`.
    try:
        existing = memory_manager.get_memory(user_id, MemoryKey.USER_LANGUAGE)
        existing_value = existing[0].get("value") if existing else None
    except Exception:
        existing_value = None

    if existing_value:
        # If the user explicitly requests a language change (e.g. "Set language to English"),
        # allow overwriting the existing preference.
        low = (user_message or "").strip().lower()
        import re as _re

        m = _re.search(r"(?:set|change) (?:my )?language to\s+([a-zA-Z]+)", low)
        if m:
            target = m.group(1).strip().lower()
            if target in ("english", "en"):
                chosen = "en"
            elif target in ("norwegian", "norsk", "no", "nb", "nn"):
                chosen = "no"
            else:
                chosen = None
            if chosen:
                try:
                    memory_manager.store_memory(
                        user_id=user_id,
                        key=MemoryKey.USER_LANGUAGE,
                        value=chosen,
                        confidence=1.0,
                        source="user_override",
                        category=MemoryCategory.PREFERENCE.value,
                    )
                except Exception:
                    pass
                return chosen
        return existing_value

    # No existing preference -> use the keyword detector (fast, deterministic)
    try:
        code, conf, meta = keyword_detect(user_message)
    except Exception:
        code, conf, meta = None, 0.0, {}

    if code:
        code = code.lower()
        if code in ("nb", "nn", "no"):
            chosen = "no"
        elif code == "en":
            chosen = "en"
        else:
            chosen = "en"
    else:
        chosen = "en"

    try:
        memory_manager.store_memory(
            user_id=user_id,
            key=MemoryKey.USER_LANGUAGE,
            value=chosen,
            confidence=float(conf or 1.0),
            source="dialogue_engine_language_detection",
            category=MemoryCategory.PREFERENCE.value,
        )
    except Exception:
        pass

    return chosen
