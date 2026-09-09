"""GLiNER-based NER with legal-domain labels.

GLiNER (Knowledgator, 2024) is a bidirectional transformer that accepts
arbitrary entity labels at inference time as natural-language strings.
That lets us express **redaction intent** directly ("client", "lawyer",
"deal codename") instead of being stuck with spaCy's fixed OntoNotes
vocabulary (PERSON / ORG / GPE / …).

This module ships a curated label set tuned for competition-law and
M&A practice. Each natural-language label maps to one of Jude's
internal `EntityType` values; the same internal type can receive
detections from multiple labels (e.g. both "lawyer" and "person" feed
into PERSON), which the overlap-resolver then dedupes.

Default model: `urchade/gliner_large-v2.1` for English work
(~770 MB, English-focused, higher accuracy than the multilingual
variant). Override with the `model_name` constructor arg if you need
multilingual coverage (`urchade/gliner_multi-v2.1`, ~430 MB) or the
PII-specific variant (`urchade/gliner_multi_pii-v1`).

Enable per-pipeline via `DetectionPipeline(..., use_gliner=True)` or
let auto-detect turn it on when the `gliner` package is importable
(see `_AUTO_GLINER` in `detect/__init__.py`).
"""

from __future__ import annotations

from functools import lru_cache

from ..types import Detection, DetectionSource, EntityType
from .chunking import DEFAULT_MAX_WORDS, chunk_text

# Label → EntityType map. Each label is a natural-language phrase that
# GLiNER scores against every token span; the cost grows roughly
# linearly with the number of labels, so this set is kept tight.
_LABELS_TO_TYPE: dict[str, EntityType] = {
    # People
    "person": EntityType.PERSON,
    "lawyer": EntityType.PERSON,
    "judge": EntityType.PERSON,
    # Organisations
    "company": EntityType.ORG,
    "law firm": EntityType.ORG,
    "client": EntityType.ORG,
    "deal codename": EntityType.ORG,
    "regulator": EntityType.ORG,
    "court": EntityType.ORG,
    # Locations
    "address": EntityType.LOC,
    "city": EntityType.LOC,
    "country": EntityType.LOC,
    # Case refs
    "case reference": EntityType.CASE_REF,
}


# Minimum confidence to accept a span. GLiNER's score is calibrated on
# Pile-NER; below this threshold spans tend to be noise.
_DEFAULT_THRESHOLD = 0.5


@lru_cache(maxsize=2)
def _load(model_name: str):  # type: ignore[no-untyped-def]
    from gliner import GLiNER

    return GLiNER.from_pretrained(model_name)


class GlinerDetector:
    """Wrap a GLiNER model with Jude's curated legal labels."""

    def __init__(
        self,
        model_name: str = "urchade/gliner_large-v2.1",
        threshold: float = _DEFAULT_THRESHOLD,
        max_words: int = DEFAULT_MAX_WORDS,
    ):
        self.model = _load(model_name)
        self.labels = list(_LABELS_TO_TYPE.keys())
        self.threshold = threshold
        self.max_words = max_words

    def detect(self, text: str) -> list[Detection]:
        if not text.strip():
            return []
        # GLiNER tokenises with truncation=True at the model's max_len
        # (384 word-tokens for the large checkpoints) and silently drops
        # everything past it, so the document is windowed on paragraph
        # boundaries and offsets are shifted back. The threshold filters
        # out low-confidence spans before they hit the overlap resolver.
        out: list[Detection] = []
        seen: set[tuple[int, int, EntityType]] = set()
        for offset, chunk in chunk_text(text, self.max_words):
            spans = self.model.predict_entities(
                chunk, self.labels, threshold=self.threshold
            )
            for s in spans:
                label = (s.get("label") or "").lower()
                etype = _LABELS_TO_TYPE.get(label)
                if etype is None:
                    continue
                start = offset + int(s["start"])
                end = offset + int(s["end"])
                # Trim whitespace at the edges and keep offsets honest:
                # `text[start:end]` must equal the reported surface.
                while start < end and text[start].isspace():
                    start += 1
                while end > start and text[end - 1].isspace():
                    end -= 1
                if start >= end:
                    continue
                key = (start, end, etype)
                if key in seen:
                    continue
                seen.add(key)
                out.append(
                    Detection(
                        text=text[start:end],
                        start=start,
                        end=end,
                        entity_type=etype,
                        source=DetectionSource.GLINER,
                        confidence=float(s.get("score", 0.8)),
                    )
                )
        return out
