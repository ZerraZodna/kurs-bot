from pathlib import Path

import pytest

from src.lessons.lesson_parser import (
    _normalize_sentence_spacing,
    parse_lessons_from_text,
)
from src.lessons.pdf_extractor import extract_formatted_text


@pytest.fixture(scope="session")
def acim_pdf_text():
    """Cache full ACIM PDF extraction once per test session (all tests in file)."""
    pdf_path = Path("src/data/Sparkly ACIM lessons-extracted.pdf")
    if not pdf_path.exists():
        pytest.skip("ACIM source PDF not available in test environment")
    return extract_formatted_text(pdf_path)


def test_parsed_lessons_use_canonical_capitalized_header_prefix():
    sample = """
Lesson
1
“Nothing I see means anything."
Now look slowly around you and practice applying this idea very specifically to whatever you see.
Use this line to keep the sample long enough for parser thresholds.

Lesson
2
"I have given everything I see in this room all the meaning that it has for me."
These practice ideas should also be applied in a broad and consistent way.
""".strip()

    lessons = parse_lessons_from_text(sample)
    lesson_rows = [row for row in lessons if row[0] != 0]

    assert lesson_rows, "Expected parsed lesson rows"
    for lesson_id, _title, content in lesson_rows:
        assert content.startswith(
            f"Lesson {lesson_id}"
        ), f"Lesson {lesson_id} content must start with canonical header; got: {content[:50]!r}"


def test_does_not_treat_phrase_lesson_a_day_as_header():
    sample = """
lesson a day.
This should not be treated as a lesson header.

Lesson
1
"Nothing I see means anything."
Body text.
""".strip()

    lessons = parse_lessons_from_text(sample)
    lesson_rows = [row for row in lessons if row[0] != 0]

    assert len(lesson_rows) == 1
    assert lesson_rows[0][0] == 1
    assert lesson_rows[0][2].startswith("Lesson 1")


def test_full_pdf_lessons_start_with_capital_lesson_header(acim_pdf_text):
    lessons = parse_lessons_from_text(acim_pdf_text)
    lesson_rows = [row for row in lessons if row[0] and row[0] > 0]

    assert lesson_rows, "No lessons parsed from full PDF"
    for lesson_id, _title, content in lesson_rows:
        assert content.startswith(
            f"Lesson {lesson_id}"
        ), f"Lesson {lesson_id} must start with canonical header; got: {content[:80]!r}"


def test_full_pdf_lesson_1_title_not_intro_bleed(acim_pdf_text):
    lessons = parse_lessons_from_text(acim_pdf_text)
    by_id = {lid: (title, content) for lid, title, content in lessons if lid is not None}

    assert 1 in by_id, "Lesson 1 missing from parsed output"
    title, content = by_id[1]
    assert "Nothing I see" in title, f"Unexpected lesson 1 title: {title!r}"
    assert not content.lower().startswith(
        "lesson 1\\n\\nlesson a day"
    ), "Lesson 1 should not start with 'lesson a day' intro bleed"


def test_spacing_normalizer_repairs_missing_spaces_after_punctuation():
    s = 'This is odd.That is better,sure?Yes,"maybe."Then'
    out = _normalize_sentence_spacing(s)
    assert ". That" in out
    assert ", sure" in out
    assert "? Yes" in out
    assert '" Then' in out
