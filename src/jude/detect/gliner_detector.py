from __future__ import annotations

from functools import lru_cache

from ..types import Detection, DetectionSource, EntityType


_LABELS_TO_TYPE: dict[str, EntityType] = {
    "person": EntityType.PERSON,
    "organization": EntityType.ORG,
    "company": EntityType.ORG,
    "location": EntityType.LOC,
    "city": EntityType.LOC,
    "country": EntityType.LOC,
    "case reference": EntityType.CASE_REF,
    "court case": EntityType.CASE_REF,
}


@lru_cache(maxsize=2)
def _load(model_name: str):  # type: ignore[no-untyped-def]
    from gliner import GLiNER

    return GLiNER.from_pretrained(model_name)


class GlinerDetector:
    """Optional GLiNER-based NER. Install with `pip install jude[gliner]`."""

    def __init__(self, model_name: str = "urchade/gliner_multi-v2.1"):
        self.model = _load(model_name)
        self.labels = list(_LABELS_TO_TYPE.keys())

    def detect(self, text: str) -> list[Detection]:
        spans = self.model.predict_entities(text, self.labels)
        out: list[Detection] = []
        for s in spans:
            etype = _LABELS_TO_TYPE.get(s["label"].lower())
            if etype is None:
                continue
            out.append(
                Detection(
                    text=s["text"],
                    start=int(s["start"]),
                    end=int(s["end"]),
                    entity_type=etype,
                    source=DetectionSource.GLINER,
                    confidence=float(s.get("score", 0.8)),
                )
            )
        return out
