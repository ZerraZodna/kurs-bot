"""
Direct tests against `langdetect.detect` for problematic messages.

These tests exercise the underlying library to see whether the
misclassification originates in `langdetect` itself.
"""

from langdetect import detect


def test_detect_yea_do_a_search_is_portuguese():
    msg = "Yea do a search"
    lang = detect(msg)
    assert lang == "pt", f"Expected 'pt' for message '{msg}', got '{lang}'"
