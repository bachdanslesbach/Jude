"""Negative-class metric: public bodies that must NOT be redacted.

Generic PII detectors are scored on what they catch. Legal
anonymisation has a second, equally important requirement: leave the
regulatory framing intact. A memo whose every mention of the European
Commission, the Bundeskartellamt, the DMA or Article 102 TFEU has been
replaced by `Org7` is useless to the LLM that receives it — and none
of that framing identifies the client.

This module measures **public-body over-redaction**: of all mentions
of whitelisted institutions / statutes / jurisdictions in a document
(the bundled `known_entities.json` entries with `redact: false`), how
many did a runner redact anyway? Lower is better; Jude's whitelist
exists precisely to drive this to zero.

Mentions that overlap a gold span are excluded from the denominator —
where the corpus annotation policy disagrees with the whitelist (e.g.
"Luxembourg" as a place of business rather than a jurisdiction), the
gold wins and the mention is scored through the ordinary F1 instead.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache

from .schema import GoldSpan, PredSpan

# Whitelist aliases that are not institution *names* and would make the
# denominator noisy: legal-form suffixes (bundled as no-redact ORG
# entries so "NV" alone is never pseudonymised) and demonyms (bundled
# as aliases of jurisdictions).
_IGNORED_ALIASES = frozenset({
    "nv", "se", "bvba", "sa", "sarl", "srl", "gmbh", "ag", "ltd", "plc",
    "llc", "inc", "bv", "sprl", "scrl", "cv", "kg", "oy", "ab", "as",
    "belgian", "belge", "belgisch", "french", "français", "française",
    "swiss", "german", "dutch", "luxembourgish", "british", "american",
    "irish", "italian", "spanish",
})

# Aliases at or below this length are matched case-sensitively so
# "EC" / "DMA" / "COM" do not fire inside ordinary prose.
_CASE_SENSITIVE_MAX_LEN = 4


@dataclass(frozen=True)
class PublicMention:
    start: int
    end: int
    text: str
    canonical: str


def _overlaps(a, b) -> bool:
    return not (a.end <= b.start or b.end <= a.start)


@lru_cache(maxsize=1)
def _alias_patterns() -> tuple[tuple[re.Pattern[str], str], ...]:
    from jude.context import _load_bundled

    out: list[tuple[re.Pattern[str], str]] = []
    seen: set[str] = set()
    for rec in _load_bundled():
        if rec.get("redact", True):
            continue
        for name in [rec["canonical"], *rec.get("aliases", [])]:
            name = (name or "").strip()
            if len(name) < 2 or name.lower() in _IGNORED_ALIASES or name in seen:
                continue
            seen.add(name)
            flags = 0 if len(name) <= _CASE_SENSITIVE_MAX_LEN else re.IGNORECASE
            pat = re.compile(r"(?<!\w)" + re.escape(name) + r"(?!\w)", flags)
            out.append((pat, rec["canonical"]))
    return tuple(out)


def public_mentions(
    text: str,
    gold_spans: Iterable[GoldSpan],
    explicit: Iterable[GoldSpan] = (),
) -> list[PublicMention]:
    """Whitelisted public-body mentions in `text` that no gold span covers,
    plus any `explicit` mentions the annotator marked as public.

    Overlapping alias hits are resolved longest-first so "European
    Commission" is reported once, not additionally as "Commission".
    Explicit mentions take precedence over whitelist hits they overlap.
    """

    golds = list(gold_spans)
    candidates: list[PublicMention] = [
        PublicMention(s.start, s.end, s.text, "(annotator)") for s in explicit
    ]
    n_explicit = len(candidates)
    for pat, canonical in _alias_patterns():
        for m in pat.finditer(text):
            candidates.append(PublicMention(m.start(), m.end(), m.group(0), canonical))
    # Stable sort keeps explicit mentions ahead of equal-length hits.
    explicit_set = set(range(n_explicit))
    candidates = [c for i, c in sorted(
        enumerate(candidates),
        key=lambda ic: (ic[0] not in explicit_set, -(ic[1].end - ic[1].start), ic[1].start),
    )]
    kept: list[PublicMention] = []
    for c in candidates:
        if any(_overlaps(c, k) for k in kept):
            continue
        if any(_overlaps(c, g) for g in golds):
            continue
        kept.append(c)
    return sorted(kept, key=lambda c: c.start)


def over_redaction(
    pred_spans: Iterable[PredSpan],
    mentions: Iterable[PublicMention],
) -> tuple[int, int]:
    """(hits, total): how many public-body mentions a runner redacted.

    A mention counts as redacted if any predicted span overlaps it by at
    least one character — the same lenient rule the F1 uses.
    """

    preds = list(pred_spans)
    ms = list(mentions)
    hits = sum(1 for m in ms if any(_overlaps(m, p) for p in preds))
    return hits, len(ms)
