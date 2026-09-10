from __future__ import annotations

from typing import Iterable

from ..store import Store
from ..types import Detection, DetectionSource
from .dictionary_detector import DictionaryDetector
from .patterns import KnownEntityDetector, PatternDetector
from .regex_rules import RegexDetector
from .spacy_detector import SpacyDetector

__all__ = [
    "DictionaryDetector",
    "KnownEntityDetector",
    "PatternDetector",
    "RegexDetector",
    "SpacyDetector",
    "DetectionPipeline",
]


_SOURCE_PRIORITY = {
    DetectionSource.USER: 0,
    DetectionSource.DICTIONARY: 1,
    DetectionSource.REGEX: 2,
    DetectionSource.PATTERN: 3,
    DetectionSource.KNOWN: 4,
    DetectionSource.PRIVACY_FILTER: 5,
    DetectionSource.GLINER: 6,
    DetectionSource.SPACY: 7,
}


class DetectionPipeline:
    """Run all detectors over a text, then resolve overlaps.

    Resolution policy:
      1. Higher-priority source wins
         (user > dictionary > regex > pattern > known > privacy_filter
         > gliner > spacy) — deterministic layers outrank neural ones.
      2. Within the same source, the longer span wins.
      3. Ties are broken by leftmost start position.
    """

    def __init__(
        self,
        store: Store,
        matter_id: str,
        languages: tuple[str, ...] = ("en", "fr", "nl"),
        use_gliner: bool | None = None,
        use_privacy_filter: bool = False,
    ):
        self.store = store
        self.matter_id = matter_id
        self.regex = RegexDetector()
        self.patterns = PatternDetector()
        self.known = KnownEntityDetector()
        self.spacy = SpacyDetector(languages=languages)
        self.dictionary = DictionaryDetector(store=store, matter_id=matter_id)
        # GLiNER auto-detect: when use_gliner is None (the default) we
        # enable it iff the `gliner` package is importable. Explicit
        # True/False overrides the auto behaviour. This makes
        # `pip install -e ".[gliner]"` a single-step opt-in.
        if use_gliner is None:
            use_gliner = _gliner_available()
        self.use_gliner = use_gliner
        if use_gliner:
            from .gliner_detector import GlinerDetector

            self.gliner: GlinerDetector | None = GlinerDetector()
        else:
            self.gliner = None
        self.use_privacy_filter = use_privacy_filter
        if use_privacy_filter:
            from .privacy_filter_detector import PrivacyFilterDetector

            self.privacy_filter: PrivacyFilterDetector | None = PrivacyFilterDetector()
        else:
            self.privacy_filter = None

    def detect(self, text: str) -> list[Detection]:
        candidates: list[Detection] = []
        candidates.extend(self.regex.detect(text))
        candidates.extend(self.patterns.detect(text))
        candidates.extend(self.known.detect(text))
        candidates.extend(self.spacy.detect(text))
        candidates.extend(self.dictionary.detect(text))
        if self.gliner is not None:
            candidates.extend(self.gliner.detect(text))
        if self.privacy_filter is not None:
            candidates.extend(self.privacy_filter.detect(text))
        return resolve_overlaps(candidates)


def resolve_overlaps(detections: Iterable[Detection]) -> list[Detection]:
    """Drop overlapping detections according to the source priority policy."""

    items = sorted(
        detections,
        key=lambda d: (
            _SOURCE_PRIORITY.get(d.source, 99),
            -(d.end - d.start),
            d.start,
        ),
    )
    kept: list[Detection] = []
    for d in items:
        if any(_overlaps(d, k) for k in kept):
            continue
        kept.append(d)
    return sorted(kept, key=lambda d: d.start)


def _overlaps(a: Detection, b: Detection) -> bool:
    return not (a.end <= b.start or b.end <= a.start)


def _gliner_available() -> bool:
    """True iff the `gliner` package is importable in this interpreter.
    Cached at module import so we don't re-import on every pipeline."""

    try:
        import gliner  # noqa: F401
    except ImportError:
        return False
    return True
