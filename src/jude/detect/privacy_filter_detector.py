"""Optional 5th detector backed by `openai/privacy-filter` (Apache 2.0).

Adds three things spaCy + regex don't catch well today:
  * `private_address` — full postal addresses (registered offices, home
    addresses, etc.). Maps to LOC.
  * `secret` — API keys, tokens, passwords accidentally pasted into legal
    drafts. Maps to a new EntityType.SECRET.
  * `account_number` — non-IBAN account-like identifiers. Maps to IBAN
    (we already pseudonymize that pseudonym prefix; a single category is
    enough for v0).

It also detects PERSON / EMAIL / PHONE / URL with similar quality to
spaCy's `_lg`, so it serves as a useful cross-check.

`private_date` is intentionally dropped — Jude does not redact dates by
default, per the project's "numerical and date data is preserved when not
linkable to a party" rule.

Heavy: ~1.5 GB on disk (1.5B params, MoE with 50M active). Install with
`pip install jude[privacy-filter]`.
"""

from __future__ import annotations

from functools import lru_cache

from ..types import Detection, DetectionSource, EntityType


_LABEL_MAP: dict[str, EntityType | None] = {
    "private_person": EntityType.PERSON,
    "private_address": EntityType.LOC,
    "private_email": EntityType.EMAIL,
    "private_phone": EntityType.PHONE,
    "private_url": EntityType.URL,
    "private_date": None,  # Jude policy: don't redact dates.
    "account_number": EntityType.IBAN,
    "secret": EntityType.SECRET,
}


@lru_cache(maxsize=2)
def _load_pipeline(model_name: str):  # type: ignore[no-untyped-def]
    """Lazy-load the HuggingFace pipeline. Cached so we don't reload per call."""

    from transformers import pipeline

    return pipeline(
        task="token-classification",
        model=model_name,
        aggregation_strategy="simple",
    )


class PrivacyFilterDetector:
    """Wraps the openai/privacy-filter token-classification model."""

    def __init__(self, model_name: str = "openai/privacy-filter"):
        self.pipe = _load_pipeline(model_name)

    def detect(self, text: str) -> list[Detection]:
        if not text.strip():
            return []
        results = self.pipe(text)
        out: list[Detection] = []
        for span in results:
            etype = _LABEL_MAP.get(span["entity_group"])
            if etype is None:
                continue
            surface = (span["word"] or "").strip()
            if not surface:
                continue
            out.append(
                Detection(
                    text=surface,
                    start=int(span["start"]),
                    end=int(span["end"]),
                    entity_type=etype,
                    source=DetectionSource.PRIVACY_FILTER,
                    confidence=float(span.get("score", 0.9)),
                )
            )
        return out
