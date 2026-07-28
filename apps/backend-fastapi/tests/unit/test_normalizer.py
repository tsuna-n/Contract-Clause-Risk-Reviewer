"""Unit tests for the text normalizer."""

import pytest

from app.parsers import is_heading, normalize, replace_ligatures


def test_normalize_collapses_whitespace() -> None:
    assert normalize("a   b\t c") == "a b c"


def test_replace_ligatures() -> None:
    assert replace_ligatures("ﬁle") == "file"


def test_is_heading() -> None:
    assert is_heading("1. Confidentiality")
    assert is_heading("2.1 Term")
    assert not is_heading("this is a normal sentence")


@pytest.mark.parametrize(
    "line",
    [
        "1. Confidentiality",
        "2.1 Term",
        "12) Termination",
        "3.2.1 Sub-clause",
        "  9. Indented heading",
        # The prefix most contracts put in front of the number.
        "Section 4. Termination",
        "Article 7. Governing Law",
        "ARTICLE 2) Payment",
        "Clause 9 Warranty",
    ],
)
def test_is_heading_matches_english_headings(line: str) -> None:
    assert is_heading(line)


@pytest.mark.parametrize(
    "line",
    [
        "ข้อ 1. การรักษาความลับ",
        "ข้อที่ 2. การเลิกสัญญา",
        "ข้อ 3 ค่าตอบแทน",  # no punctuation after the number
        "1. การรักษาความลับ",  # arabic digits, Thai title
        "๑. การรักษาความลับ",  # Thai digits
        "๒.๓ เงื่อนไขการชำระเงิน",
        # Titles opening with a leading vowel — written before their consonant,
        # so they are the first character of the word.
        "5. เงื่อนไขทั่วไป",
        "6. แก้ไขเพิ่มเติม",
        "7. โอนสิทธิ",
        "8. ใบแจ้งหนี้",
        "9. ไม่แข่งขัน",
    ],
)
def test_is_heading_matches_thai_headings(line: str) -> None:
    assert is_heading(line)


@pytest.mark.parametrize(
    "line",
    [
        "this is a normal sentence",
        "ผู้ให้บริการตกลงว่าจะรักษาความลับ",
        # A figure opening a line is not a heading — this is the case the
        # trailing letter class exists to reject.
        "500,000 baht payable on the Effective Date",
        "1. 500,000 baht payable monthly",
        "1.5% per month interest",
        "2024 was the year of...",
        "(i) first item",
        "• Confidentiality",
        "1.",  # a number with no title after it
        "",
    ],
)
def test_is_heading_rejects_non_headings(line: str) -> None:
    assert not is_heading(line)
