from jude.detect.language import detect_language, split_into_paragraphs


def test_detects_english():
    text = "The European Commission has issued a decision on Amazon's marketplace practices."
    assert detect_language(text) == "en"


def test_detects_french():
    text = "La Commission européenne a rendu une décision sur les pratiques de marketplace d'Amazon."
    assert detect_language(text) == "fr"


def test_returns_none_for_too_short_input():
    assert detect_language("Hi") is None
    assert detect_language("") is None


def test_returns_none_for_unknown_or_unsupported():
    assert detect_language("コードコード コードコード コードコード コードコード") is None


def test_split_paragraphs_preserves_offsets():
    text = "First paragraph here.\n\nSecond.\n\n\nThird with multiple breaks."
    parts = split_into_paragraphs(text)
    assert len(parts) == 3
    for offset, chunk in parts:
        assert text[offset : offset + len(chunk)] == chunk


def test_split_paragraphs_skips_blank_only():
    text = "\n\n   \n\nReal content.\n\n   \t   "
    parts = split_into_paragraphs(text)
    assert len(parts) == 1
    assert "Real content" in parts[0][1]


def test_split_paragraphs_handles_no_breaks():
    text = "Single paragraph without any blank line."
    parts = split_into_paragraphs(text)
    assert len(parts) == 1
    assert parts[0] == (0, text)
