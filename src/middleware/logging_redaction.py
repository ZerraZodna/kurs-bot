from __future__ import annotations

import logging
import re

EMAIL_RE = re.compile(r"([a-zA-Z0-9_.+-]+)@([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")
PHONE_RE = re.compile(r"(\+?\d[\d\s\-()]{6,}\d)")
TOKEN_RE = re.compile(r"(Bearer\s+)?[A-Za-z0-9_\-]{20,}")


def redact_text(value: str) -> str:
    redacted = EMAIL_RE.sub("[redacted-email]", value)
    redacted = PHONE_RE.sub("[redacted-phone]", redacted)
    redacted = TOKEN_RE.sub("[redacted-token]", redacted)
    return redacted


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_text(record.msg)
        if record.args:
            record.args = tuple(redact_text(a) if isinstance(a, str) else a for a in record.args)
        return True


def apply_logging_redaction() -> None:
    root = logging.getLogger()
    for handler in root.handlers:
        handler.addFilter(RedactionFilter())
