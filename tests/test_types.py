from jude.types import normalize_surface


def test_normalize_strips_company_suffixes():
    assert normalize_surface("Amazon.com Inc.") == "amazon.com"
    assert normalize_surface("Acme S.A.") == "acme"
    assert normalize_surface("Test Corporation") == "test"
    assert normalize_surface("Example GmbH") == "example"
    assert normalize_surface("ALPHABET LLC") == "alphabet"


def test_normalize_collapses_whitespace_and_case():
    assert normalize_surface("  Foo   Bar  ") == "foo bar"
    assert normalize_surface("Foo BAR") == "foo bar"


def test_normalize_handles_unicode():
    assert normalize_surface("Société Générale S.A.") == "société générale"
