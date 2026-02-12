import pytest

from src.services.language.keyword_detector import detect_language


def test_keyword_detector_basic_english():
    code, conf, meta = detect_language("Hello, please do a search for me")
    assert code == "en"
    assert conf is not None and conf > 0.5


def test_keyword_detector_ambiguous_returns_none_low_confidence():
    code, conf, meta = detect_language("Ok")
    assert code is None
