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

			resp = await call_ollama(prompt, model=None, language="en")
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


from src.services.memory_manager import MemoryManager
from src.models.database import MessageLog


async def detect_and_store_language(memory_manager: MemoryManager, user_id: int, user_message: str) -> Optional[str]:
	"""Detect language for `user_message` and store `user_language` memory when appropriate.

	Stores two-letter language codes (e.g., 'en', 'no'). Returns the stored
	or existing language code.
	"""

	existing = memory_manager.get_memory(user_id, "user_language")
	existing_value = existing[0].get("value") if existing else None
	existing_conf = existing[0].get("confidence", 0.0) if existing else 0.0

	# 3) run detector
	code, conf, meta = await detect_language(user_message)
	if not code:
		return existing_value

	# Normalize code to short form
	code = code.lower()

	# 4) if no existing language -> accept with conservative threshold
	if not existing_value:
		threshold = 0.6 if len(user_message.split()) <= 3 else 0.7
		if (conf or 0.0) >= threshold:
			try:
				memory_manager.store_memory(
					user_id=user_id,
					key="user_language",
					value=code,
					confidence=max(threshold, float(conf or 0.0)),
					source="dialogue_engine_language_detection",
					category="preference",
				)
			except Exception:
				pass
			return code
		# if not confident, prefer en/no if detected
		if code in ("en", "no", "nb", "nn"):
			try:
				memory_manager.store_memory(
					user_id=user_id,
					key="user_language",
					value=code,
					confidence=0.7,
					source="dialogue_engine_language_detection",
					category="preference",
				)
			except Exception:
				pass
			return code
		return None

	# 5) if same as existing, nothing to do
	if existing_value and existing_value.lower() == code.lower():
		return existing_value

	# 6) Tiny N=3 voting: query last 2 inbound user messages (exclude current)
	db = memory_manager.db
	prev_rows = (
		db.query(MessageLog)
		.filter(MessageLog.user_id == user_id)
		.order_by(MessageLog.created_at.desc())
		.limit(2)
		.all()
	)
	prev_texts = [r.content for r in prev_rows if r.content]

	votes = [code]
	for t in prev_texts:
		c, cf, m = await detect_language(t)
		if c:
			votes.append(c.lower())

	counts = Counter(votes)
	most_common, most_count = counts.most_common(1)[0]
	if most_count >= 2:
		# accept majority
		try:
			memory_manager.store_memory(
				user_id=user_id,
				key="user_language",
				value=most_common,
				confidence=max(0.75, float(conf or 0.75)),
				source="dialogue_engine_language_detection",
				category="preference",
			)
		except Exception:
			pass
		return most_common

	# 7) require confidence threshold; protect strong existing preference.
	# For short replies, normally do not overwrite based on a single short
	# message's confidence alone; only majority voting may accept. We allow
	# overwrites when there is no existing preference or when the message
	# is reasonably long.
	det_conf = float(conf or 0.0)
	word_count = len(user_message.split())
	required_conf = 0.7 if (not existing_value or word_count >= 4) else 1.1

	if det_conf >= required_conf:
		# Protect a very strong existing preference only when the new
		# detection is meaningfully weaker. This uses a small delta rather
		# than an absolute hard cutoff so reasonable detections can overwrite.
		# Relax protection: only protect very high-confidence existing preferences
		# (>= 0.95). This lets reasonable detections (~0.7+) overwrite older
		# preferences that were not extremely certain.
		if existing_conf >= 0.95 and det_conf < (existing_conf - 0.05):
			return existing_value
		try:
			memory_manager.store_memory(
				user_id=user_id,
				key="user_language",
				value=code,
				confidence=det_conf,
				source="dialogue_engine_language_detection",
				category="preference",
			)
		except Exception:
			pass
		return code

	return existing_value
