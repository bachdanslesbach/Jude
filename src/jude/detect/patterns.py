"""Deterministic long-tail rules and the known-entity detector.

Statistical NER misses a predictable long tail: a company named with
its legal form but never seen in training, a short name defined in
parentheses, a witness called only "Mr. Tan", a vessel, a bare domain,
a street address, a family behind a trust, a bank known by its
acronym. Each is a pattern a lawyer recognises at a glance; each is a
rule here. Rules are precise by construction and outrank the neural
detectors on overlap; the public-knowledge whitelist still filters
their output afterwards.

`KnownEntityDetector` matches the bundled public-knowledge entries
flagged `redact: true` (public companies, banks) — their identity is
public, their involvement in a matter is not.
"""

from __future__ import annotations

import re
from functools import lru_cache

from ..public_knowledge import is_public_no_redact
from ..types import Detection, DetectionSource, EntityType
from .spacy_detector import _DEMONYMS, _LEGAL_HEADERS

_CAP = r"[A-ZÀ-ÝÆØ]"
_TOKEN = rf"{_CAP}[\w'’&.-]*"
_CONNECTOR = r"(?:de|du|des|d'|la|le|les|of|and|van|der|den|en|et|the|y|di|da|&)"
_BOUNDARY_AFTER = r"(?=[\s,;:)\]\"'’”]|\.(?!\w)|$)"

# --- legal-form suffix ------------------------------------------------------

# Longest / most specific first: the alternation is ordered.
_SUFFIXES = [
    r"Sp\. z o\.o\.", r"Sdn\. Bhd\.", r"Pty\.? Ltd\.?", r"Pte\.? Ltd\.?",
    r"S\.A\.S\.", r"S\.A\.R\.L\.", r"S\.à ?r\.l\.", r"Sàrl", r"S\.p\.A\.", r"S\.r\.l\.",
    r"S\.C\.A\.", r"S\.C\.S\.", r"SCSp", r"SCS", r"SCA", r"SARL", r"SAS", r"SPRL", r"SCRL", r"SRL",
    r"BVBA", r"CVBA", r"B\.V\.", r"N\.V\.", r"S\.A\.", r"S\.E\.", r"BV", r"NV", r"SA", r"SE", r"CV",
    r"GmbH & Co\. KG", r"GmbH", r"mbH", r"KGaA", r"A\.G\.", r"AG", r"KG",
    r"A/S", r"ApS", r"Oyj", r"Oy", r"AB", r"AS",
    r"s\.r\.o\.", r"OOO", r"ZAO", r"OAO", r"PJSC", r"JSC", r"DAC",
    r"Limited", r"Ltd", r"plc", r"PLC", r"LLLP", r"LLP", r"LLC", r"LP",
    r"Inc\.", r"Inc", r"Corp\.", r"Corp", r"Co\.", r"K\.K\.",
]
_AMBIGUOUS_SUFFIXES = frozenset({"AS", "AB", "SE", "CV", "LP", "KG", "AG", "Co.", "Inc", "Corp"})
_SUFFIX_ALT = "|".join(_SUFFIXES)
_LEGAL_FORM_RE = re.compile(
    rf"(?<![\w.])({_TOKEN}(?:\s+(?:{_TOKEN}|{_CONNECTOR}))*?)\s+({_SUFFIX_ALT}){_BOUNDARY_AFTER}"
)

# Sentence starters, roles and labels that a left-to-right scan glues
# onto a company name ("Plaintiff Helios Photonics Inc.").
_LEADING_NOISE = frozenset({
    "the", "a", "an", "this", "that", "these", "those", "by", "for", "from", "in", "on", "at",
    "to", "with", "of", "and", "or", "between", "among", "whereas", "following", "pursuant",
    "under", "against", "notwithstanding", "each", "both", "our", "its", "their", "your",
    "his", "her", "dear", "re", "subject", "plaintiff", "defendant", "claimant", "respondent",
    "applicant", "appellant", "counsel", "buyer", "seller", "purchaser", "vendor", "client",
    "lender", "borrower", "guarantor", "target", "company", "licensor", "licensee", "lessor",
    "lessee", "supplier", "customer", "party", "parties", "issuer", "arranger", "agent",
    "sponsor", "investor", "bidder", "acquirer", "seller's", "buyer's", "via", "through",
    "into", "onto", "per", "see", "cf", "also", "including", "namely", "notably", "against",
    "le", "la", "les", "de", "du", "des", "et", "pour", "par", "entre", "avec", "chez",
    "de", "het", "een", "en", "voor", "door", "tussen", "met", "bij",
    # honorifics: "Ms. Hilda Brennan of Brennan & Park LLP" starts at "Ms."
    "mr", "mrs", "ms", "mx", "dr", "prof", "professor", "maître", "maitre", "me", "m",
    "mme", "mlle", "dhr", "mevr", "mw", "herr", "frau", "sir", "dame", "lord", "lady",
})

_CONNECTOR_WORDS = frozenset({
    "de", "du", "des", "d'", "la", "le", "les", "of", "and", "van", "der", "den", "en", "et",
    "the", "y", "di", "da", "&",
})

# "of" / "de" glue a person to their firm — "Hilda Brennan of Brennan &
# Park LLP" — unless what precedes is an institution noun: "Bank of
# Ireland plc", "Société Générale de Belgique SA", "Banque de Luxembourg".
_GENITIVE_CONNECTORS = frozenset({"of", "de", "du", "des", "d'"})
_INSTITUTION_NOUNS = frozenset({
    "bank", "banque", "banca", "banco", "caja", "société", "societe", "compagnie", "company",
    "caisse", "groupe", "group", "institut", "institute", "université", "university",
    "chambre", "chamber", "bureau", "office", "cabinet", "fonds", "fund", "association",
    "fédération", "federation", "conseil", "council", "maison", "house", "centre", "center",
    "agence", "agency", "crédit", "credit", "board", "college", "school", "academy",
    "society", "trust", "church", "order", "port", "city", "ville", "union", "ordre",
    "état", "etat", "state", "republic", "kingdom", "royaume", "koninkrijk",
})


def _strip_leading_noise(phrase: str) -> str:
    tokens = phrase.split()
    while tokens and tokens[0].lower().strip(".,") in _LEADING_NOISE:
        tokens.pop(0)
    while tokens and tokens[0].lower() in _CONNECTOR_WORDS:
        tokens.pop(0)
    # Cut at a genitive connector that no institution noun precedes.
    for i, tok in enumerate(tokens):
        if tok.lower() in _GENITIVE_CONNECTORS and not any(
            t.lower() in _INSTITUTION_NOUNS for t in tokens[:i]
        ):
            return _strip_leading_noise(" ".join(tokens[i + 1:]))
    return " ".join(tokens)


def _is_name_worthy(phrase: str, suffix: str) -> bool:
    if not phrase:
        return False
    low = phrase.lower()
    if low in _DEMONYMS or low in _LEGAL_HEADERS:
        return False
    if is_public_no_redact(phrase, EntityType.LOC) or is_public_no_redact(phrase, EntityType.ORG):
        return False
    if suffix in _AMBIGUOUS_SUFFIXES and not any(ch.islower() for ch in phrase):
        return False  # "COURT AS", "SECTION AB" in all-caps headings
    return True


# --- defined alias ------------------------------------------------------------

# ("Helios"), (“LOS”), ("RVK" or "the Firm"), (the "Buyer") — quoted
# alias, or an unquoted all-caps acronym (LOS). Roles and defined
# terms are excluded below.
_ALIAS_RE = re.compile(
    r"\(\s*(?:the\s+)?"
    r"(?:[\"“‘']([A-ZÀ-ÝÆØ][\w&.\-]{1,39}(?:\s+[A-ZÀ-ÝÆØ][\w&.\-]+){0,3})[\"”’']"
    r"|([A-Z]{2,6}))"
    r"\s*(?:,|\)|\bor\b|\band\b)"
)
_DEFINED_TERMS = frozenset({
    "agreement", "closing", "completion", "signing", "transaction", "shares", "share",
    "facility", "facilities", "loan", "loans", "term sheet", "business day", "business days",
    "effective date", "closing date", "longstop date", "conditions", "condition",
    "warranties", "warranty", "indemnity", "escrow", "deposit", "purchase price",
    "consideration", "notice", "schedule", "annex", "exhibit", "group", "company",
    "bank", "banks", "security", "collateral", "services", "products", "territory",
    "confidential information", "intellectual property", "ip", "know-how", "licence",
    "license", "software", "data", "personal data", "restricted period",
    "restricted business", "proceedings", "claim", "claims", "dispute", "matter", "engagement",
    "fees", "fee", "work product", "deliverables", "order", "decision", "judgment",
    "award", "settlement", "offer", "commitments", "undertakings", "remedies",
    "relevant market", "market", "act", "regulation", "directive", "code", "rules",
    "guidelines", "policy", "plan", "budget", "report", "audit", "review",
})


# --- honorific + name ---------------------------------------------------------

# No Sir / Dame / Lord / Lady: they name streets and public figures
# ("16 Sir John Rogerson's Quay") more often than parties.
_HONORIFIC = (
    r"Mr\.?|Mrs\.?|Ms\.?|Mx\.?|Dr\.?|Prof\.?|Professor|Maître|Maitre|Me\.?|M\.|Mme\.?|Mlle\.?|"
    r"Dhr\.?|Mevr\.?|Mw\.?|Herr|Frau|Judge|Justice|Hon\.?|Rev\.?|"
    r"Capt\.?|Captain|Col\.?|Gen\.?|Ing\.?|Ir\."
)
_NAME_TOKEN = rf"{_CAP}(?:['’]{_CAP})?[\w-]+"
_HONORIFIC_RE = re.compile(
    rf"(?<![\w.])(?:{_HONORIFIC})\s+"
    rf"({_NAME_TOKEN}(?:\s+(?:{_NAME_TOKEN}|van|der|de|von|du|le|la|den)){{0,3}})"
    r"(?=['’]s\b|[^\w'’]|$)"
)
_ROLE_AFTER_HONORIFIC = frozenset({
    "president", "chairman", "chairwoman", "chair", "speaker", "secretary", "minister",
    "ambassador", "mayor", "governor", "attorney", "attorney general", "prime minister",
    "commissioner", "director", "chief executive", "chief", "vice president", "treasurer",
    "registrar", "clerk", "recorder", "arbitrator", "mediator", "referee",
})


# --- vessel, domain, family ---------------------------------------------------

_VESSEL_RE = re.compile(
    rf"(?<![\w/])((?:M/V|MV|M/T|M/S|S/S|M/Y|S/Y)\s+{_CAP}[\w-]+(?:\s+{_CAP}[\w-]+){{0,2}})\b"
)

_TLDS = (
    "com|net|org|eu|be|fr|nl|lu|de|ch|uk|co\\.uk|io|law|legal|info|biz|ai|it|es|pt|at|pl|se|"
    "dk|no|fi|ie|us|ca|jp|cn|in|au|sg|hk|edu|gov|int|lu|li|mc"
)
# A trailing full stop is the sentence's, not the domain's.
_DOMAIN_RE = re.compile(
    rf"(?<![\w@.\-/])((?:[a-z0-9](?:[a-z0-9-]{{0,61}}[a-z0-9])?\.)+(?:{_TLDS}))(?![\w-]|\.\w|@)",
    re.IGNORECASE,
)

_FAMILY_RE = re.compile(
    rf"\b({_CAP}[a-zà-ÿ]+(?:-{_CAP}[a-zà-ÿ]+)?)\s+(?:family|families|famille)\b"
)
_NOT_A_FAMILY_NAME = frozenset({
    "royal", "holy", "whole", "entire", "one", "two", "single", "host", "extended", "nuclear",
    "immediate", "same", "new", "old", "the", "this", "that", "each", "every", "no", "any",
    "founding", "controlling", "ruling", "wider", "broader", "same",
})


# --- street addresses -----------------------------------------------------------

_FR_STREET_WORDS = (
    r"rue|avenue|av\.|boulevard|bd\.?|bld\.?|chaussée|chee|chée|place|square|quai|allée|"
    r"impasse|chemin|route|cours|passage|clos|drève|dreve|sentier|galerie|esplanade"
)
# "22 rue de Rivoli", "14 boulevard Haussmann" — number first (FR).
_FR_ADDRESS_RE = re.compile(
    rf"(?<![\w-])(\d{{1,4}}\s?(?:bis|ter|[A-Za-z])?,?\s+(?:{_FR_STREET_WORDS})\s+[\w'’-]+"
    rf"(?:\s+[\w'’-]+){{0,4}}?)(?=\s*[,;\n)]|\s+\d{{4,5}}\b|\.(?!\w)|$)",
    re.IGNORECASE,
)
# "Avenue Louise 250", "Boulevard du Régent 47" — number last (BE).
_BE_ADDRESS_RE = re.compile(
    rf"\b((?:Rue|Avenue|Boulevard|Chaussée|Place|Square|Quai|Allée|Chemin|Route|Drève|Clos|"
    rf"Galerie|Esplanade)\s+[\w'’-]+(?:\s+[\w'’-]+){{0,3}}?\s+\d{{1,4}}\s?[A-Za-z]?)"
    rf"(?=\s*[,;\n)]|\s+\d{{4}}\b|\.(?!\w)|$)"
)
# "Strawinskylaan 3127", "Keizersgracht 12A" (NL).
_NL_ADDRESS_RE = re.compile(
    rf"\b({_CAP}[\w-]*(?:straat|laan|plein|weg|dreef|kaai|lei|singel|gracht|markt|steenweg|"
    rf"baan|dijk|hof|kade|vest|wal|plantsoen)\s+\d{{1,4}}\s?[A-Za-z]?)\b"
)
# "10 Old Bailey", "14 Cornhill", "221B Baker Street" (EN) — a street
# word (or one of London's nameless streets) is mandatory.
_EN_STREET_WORDS = (
    r"Street|St\.?|Road|Rd\.?|Avenue|Ave\.?|Lane|Ln\.?|Square|Sq\.?|Place|Pl\.?|Drive|Dr\.?|"
    r"Way|Row|Gardens|Terrace|Crescent|Boulevard|Blvd\.?|Close|Walk|Mews|Grove|Circus|Parade|"
    r"Broadway|Plaza|Wharf|Quay|Embankment|Hill|Yard|Court|Ct\.?|"
    r"Bailey|Cornhill|Strand|Cheapside|Piccadilly|Whitehall|Aldgate|Bishopsgate|Moorgate|"
    r"Holborn|Fleet|Poultry|Eastcheap"
)
_EN_ADDRESS_RE = re.compile(
    rf"(?<![\w-])(\d{{1,5}}[A-Z]?\s+(?:(?:Old|New|Upper|Lower|Great|Little|North|South|East|"
    rf"West|Saint|St\.)\s+)?(?:{_CAP}[\w'’-]+\s+){{0,3}}(?:{_EN_STREET_WORDS}))"
    rf"(?=[,;\n)]|\s+[A-Z]{{1,2}}\d|\.(?!\w)|$)"
)


def _det(text: str, start: int, end: int, etype: EntityType,
         source: DetectionSource = DetectionSource.PATTERN, confidence: float = 0.95) -> Detection:
    return Detection(text=text[start:end], start=start, end=end, entity_type=etype,
                     source=source, confidence=confidence)


class PatternDetector:
    """Deterministic long-tail rules. See module docstring."""

    def detect(self, text: str) -> list[Detection]:
        out: list[Detection] = []
        out.extend(self._legal_forms(text))
        out.extend(self._aliases(text))
        out.extend(self._honorifics(text))
        out.extend(self._vessels(text))
        out.extend(self._domains(text))
        out.extend(self._families(text))
        out.extend(self._addresses(text))
        return out

    def _legal_forms(self, text: str) -> list[Detection]:
        out = []
        for m in _LEGAL_FORM_RE.finditer(text):
            raw_phrase, suffix = m.group(1), m.group(2)
            phrase = _strip_leading_noise(raw_phrase)
            if not _is_name_worthy(phrase, suffix):
                continue
            start = m.start(1) + (len(raw_phrase) - len(phrase))
            out.append(_det(text, start, m.end(2), EntityType.ORG))
        return out

    def _aliases(self, text: str) -> list[Detection]:
        out = []
        for m in _ALIAS_RE.finditer(text):
            alias = m.group(1) or m.group(2)
            grp = 1 if m.group(1) else 2
            low = alias.lower()
            if low in _LEGAL_HEADERS or low in _DEFINED_TERMS or low in _DEMONYMS:
                continue
            if is_public_no_redact(alias, EntityType.ORG):
                continue
            out.append(_det(text, m.start(grp), m.end(grp), EntityType.ORG))
        return out

    def _honorifics(self, text: str) -> list[Detection]:
        out = []
        for m in _HONORIFIC_RE.finditer(text):
            name = m.group(1)
            low = name.lower()
            if low in _ROLE_AFTER_HONORIFIC or low in _LEGAL_HEADERS or low in _DEMONYMS:
                continue
            out.append(_det(text, m.start(1), m.end(1), EntityType.PERSON))
        return out

    def _vessels(self, text: str) -> list[Detection]:
        return [_det(text, m.start(1), m.end(1), EntityType.ORG) for m in _VESSEL_RE.finditer(text)]

    def _domains(self, text: str) -> list[Detection]:
        return [_det(text, m.start(1), m.end(1), EntityType.URL) for m in _DOMAIN_RE.finditer(text)]

    def _families(self, text: str) -> list[Detection]:
        out = []
        for m in _FAMILY_RE.finditer(text):
            low = m.group(1).lower()
            if low in _NOT_A_FAMILY_NAME or low in _DEMONYMS or low in _LEGAL_HEADERS:
                continue
            out.append(_det(text, m.start(1), m.end(1), EntityType.PERSON))
        return out

    def _addresses(self, text: str) -> list[Detection]:
        out = []
        for rx in (_FR_ADDRESS_RE, _BE_ADDRESS_RE, _NL_ADDRESS_RE, _EN_ADDRESS_RE):
            for m in rx.finditer(text):
                out.append(_det(text, m.start(1), m.end(1), EntityType.LOC))
        return out


# --- known entities -------------------------------------------------------------


@lru_cache(maxsize=1)
def _known_patterns() -> tuple[tuple[re.Pattern[str], EntityType], ...]:
    from ..context import _load_bundled

    out: list[tuple[re.Pattern[str], EntityType]] = []
    seen: set[str] = set()
    for rec in _load_bundled():
        if not rec.get("redact", True):
            continue
        try:
            etype = EntityType(rec["type"])
        except ValueError:
            continue
        for name in [rec["canonical"], *rec.get("aliases", [])]:
            name = (name or "").strip()
            if len(name) < 3 or name in seen:
                continue
            seen.add(name)
            out.append((re.compile(r"(?<!\w)" + re.escape(name) + r"(?!\w)"), etype))
    out.sort(key=lambda p: -len(p[0].pattern))
    return tuple(out)


class KnownEntityDetector:
    """Bundled public companies and banks (`redact: true`), matched
    case-sensitively on word boundaries. Public bodies are never emitted."""

    def detect(self, text: str) -> list[Detection]:
        out: list[Detection] = []
        for pat, etype in _known_patterns():
            for m in pat.finditer(text):
                out.append(_det(text, m.start(), m.end(), etype,
                                source=DetectionSource.KNOWN, confidence=0.9))
        return out
