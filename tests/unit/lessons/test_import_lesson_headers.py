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
        assert content.startswith(f"Lesson {lesson_id}"), (
            f"Lesson {lesson_id} content must start with canonical header; got: {content[:50]!r}"
        )


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
    lesson_rows = [row for row in lessons if row[0] and row[0] >= 2]

    assert lesson_rows, "No lessons parsed from full PDF"
    # These lessons start with review markers (normalized to <b>Review N</b>)
    review_lessons = {51, 81, 111, 141, 171, 201}
    # This lesson starts with Part II introduction
    intro_lessons = {221}
    for lesson_id, _title, content in lesson_rows:
        if lesson_id in review_lessons:
            assert "<b>Review " in content[:40], (
                f"Lesson {lesson_id} must start with <b>Review N</b> marker; got: {content[:80]!r}"
            )
        elif lesson_id in intro_lessons:
            assert "INTRODUCTION" in content[:50], (
                f"Lesson {lesson_id} must start with INTRODUCTION; got: {content[:80]!r}"
            )
        else:
            assert content.startswith(f"Lesson {lesson_id}"), (
                f"Lesson {lesson_id} must start with canonical header; got: {content[:80]!r}"
            )


def test_full_pdf_lesson_1_starts_with_introduction(acim_pdf_text):
    lessons = parse_lessons_from_text(acim_pdf_text)
    by_id = {lid: (title, content) for lid, title, content in lessons if lid is not None}

    assert 1 in by_id, "Lesson 1 missing from parsed output"
    title, content = by_id[1]
    # Lesson 1 should start with the introduction text
    assert "INTRODUCTION" in content, f"Lesson 1 should start with INTRODUCTION; got: {content[:80]!r}"


def test_full_pdf_lesson_1_title_not_intro_bleed(acim_pdf_text):
    lessons = parse_lessons_from_text(acim_pdf_text)
    by_id = {lid: (title, content) for lid, title, content in lessons if lid is not None}

    assert 1 in by_id, "Lesson 1 missing from parsed output"
    title, content = by_id[1]
    assert "Nothing I see" in title, f"Unexpected lesson 1 title: {title!r}"
    assert not content.lower().startswith("lesson 1\\n\\nlesson a day"), (
        "Lesson 1 should not start with 'lesson a day' intro bleed"
    )


def test_full_pdf_review_markers_moved_to_next_lesson(acim_pdf_text):
    """Verify review markers are moved from prev lesson to next and normalized."""
    lessons = parse_lessons_from_text(acim_pdf_text)
    by_id = {lid: (title, content) for lid, title, content in lessons if lid is not None}

    # Review marker pairs: (prev_lesson, next_lesson, expected_normalized_marker)
    review_pairs = [
        (50, 51, "<b>Review 1</b>"),
        (80, 81, "<b>Review 2</b>"),
        (110, 111, "<b>Review 3</b>"),
        (140, 141, "<b>Review 4</b>"),
        (170, 171, "<b>Review 5</b>"),
        (200, 201, "<b>Review 6</b>"),
    ]
    for prev_id, next_id, marker in review_pairs:
        assert prev_id in by_id, f"Lesson {prev_id} missing"
        assert next_id in by_id, f"Lesson {next_id} missing"
        prev_content = by_id[prev_id][1]
        next_content = by_id[next_id][1]
        # The original spaced-letter marker should NOT be in either lesson
        spaced = "r e v i e w " + marker.replace("<b>Review ", "").replace("</b>", "")
        assert spaced not in prev_content, f"Original review marker should not remain in lesson {prev_id}"
        # The normalized marker should be in the next lesson
        assert marker in next_content, (
            f"Normalized review marker '{marker}' should be in lesson {next_id}; not found in: {next_content[:200]!r}"
        )


def test_spacing_normalizer_repairs_missing_spaces_after_punctuation():
    s = 'This is odd.That is better,sure?Yes,"maybe."Then'
    out = _normalize_sentence_spacing(s)
    assert ". That" in out
    assert ", sure" in out
    assert "? Yes" in out
    assert '" Then' in out
