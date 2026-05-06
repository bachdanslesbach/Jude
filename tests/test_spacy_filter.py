from jude.detect.spacy_detector import _normalize_span


def test_rejects_year():
    assert _normalize_span("January 2025", 0, 12, "en") is None
    assert _normalize_span("2024", 0, 4, "en") is None


def test_rejects_month_word():
    assert _normalize_span("March", 0, 5, "en") is None
    assert _normalize_span("janvier", 0, 7, "fr") is None


def test_rejects_all_stopwords_french():
    assert _normalize_span("Notre", 0, 5, "fr") is None
    assert _normalize_span("le la", 0, 5, "fr") is None


def test_rejects_long_span():
    assert _normalize_span("a b c d e f g", 0, 13, "en") is None


def test_rejects_single_lowercase_word():
    assert _normalize_span("dominante", 0, 9, "fr") is None
    assert _normalize_span("retailer", 0, 8, "en") is None


def test_accepts_legitimate_org():
    out = _normalize_span("Acme Solutions SA", 0, 17, "en")
    assert out == ("Acme Solutions SA", 0, 17)


def test_accepts_legitimate_person():
    out = _normalize_span("Jean-Pierre Dubois", 5, 23, "fr")
    assert out == ("Jean-Pierre Dubois", 5, 23)


def test_accepts_legitimate_location():
    out = _normalize_span("Bruxelles", 0, 9, "fr")
    assert out == ("Bruxelles", 0, 9)


def test_trims_trailing_punctuation():
    out = _normalize_span("Acme Inc.,", 0, 10, "en")
    assert out is not None
    surface, start, end = out
    assert surface == "Acme Inc"
    assert (start, end) == (0, 8)


def test_rejects_sheet_marker():
    """`--- Sheet: Foo ---` is structural annotation injected by the XLSX
    adapter; never redactable."""

    assert _normalize_span("--- Sheet: Sheet1 ---", 0, 21, "en") is None
    assert _normalize_span("--- Page 5 ---", 0, 14, "en") is None


def test_trims_at_newline():
    text = "Maître Jean-Pierre Dubois\nDe:"
    out = _normalize_span(text, 0, len(text), "fr")
    assert out is not None
    surface, start, end = out
    assert "\n" not in surface
    assert "De" not in surface
    assert surface == "Maître Jean-Pierre Dubois"
    assert end == start + len(surface)
