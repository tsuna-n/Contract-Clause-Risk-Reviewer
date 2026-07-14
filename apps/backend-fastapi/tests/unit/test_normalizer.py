"""Unit tests for the text normalizer."""

from app.parsers.normalizer import is_heading, normalize, replace_ligatures


def test_normalize_collapses_whitespace() -> None:
    assert normalize("a   b\t c") == "a b c"


def test_replace_ligatures() -> None:
    assert replace_ligatures("ﬁle") == "file"


def test_is_heading() -> None:
    assert is_heading("1. Confidentiality")
    assert is_heading("2.1 Term")
    assert not is_heading("this is a normal sentence")
