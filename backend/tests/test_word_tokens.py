import pytest

from app.word_tokens import normalize_word, tokenize


def test_case_punctuation_and_accents():
    assert tokenize("Hello, HELLO! Café.") == ["hello", "hello", "café"]


def test_identifiers_and_apostrophes():
    assert tokenize("ERR-401 account_id customer's customer’s") == [
        "err-401",
        "account_id",
        "customer's",
        "customer's",
    ]


def test_unicode_normalization():
    assert tokenize("ＣＡＦÉ cafe\u0301") == ["café", "café"]


def test_stopwords_are_retained():
    assert tokenize("Where is the phone?") == [
        "where",
        "is",
        "the",
        "phone",
    ]


def test_empty_and_punctuation_only_text():
    assert tokenize("") == []
    assert tokenize("... !!!") == []


def test_lookup_normalizes_one_word():
    assert normalize_word(" ERR-401! ") == "err-401"


@pytest.mark.parametrize("value", ["", "!!!", "locked out"])
def test_lookup_rejects_zero_or_multiple_words(value):
    with pytest.raises(ValueError, match="exactly one"):
        normalize_word(value)