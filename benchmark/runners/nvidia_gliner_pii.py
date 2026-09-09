"""GLiNER-family runners: `nvidia/gliner-PII` and the base it was
fine-tuned from, `urchade/gliner_large-v2.1`.

GLiNER takes its entity labels as natural-language strings at
inference time, so the *same* checkpoint can be queried two ways:

* **native labels** — the labels the checkpoint was trained on
  (NVIDIA: 55 Nemotron-PII categories, of which we query the eighteen
  that have a counterpart in Jude's schema). This is the model "as
  its authors intended".
* **Jude's legal labels** — the curated label set Jude's own GLiNER
  detector uses (`person`, `company`, `law firm`, `regulator`,
  `case reference`, …). Querying NVIDIA's checkpoint with these
  isolates the effect of their PII fine-tuning against the base
  model on the legal task.

Both variants get the same post-processing: adjacent same-type spans
separated only by whitespace are merged, because NVIDIA's taxonomy
splits `first_name` / `last_name` while the gold has one PERSON span.

Long documents are chunked to ~200 words on paragraph boundaries.
GLiNER's `max_len` is 384 word-tokens and `predict_entities` silently
truncates beyond it — a corpus document of two pages would otherwise
lose its tail.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from jude.detect.chunking import chunk_text as _chunk_text

from ..schema import PredSpan

NVIDIA_MODEL_ID = "nvidia/gliner-PII"
NVIDIA_REVISION = "bd23e8ef4425fd04e34c5204ab49ffaa706eae79"  # 2025-12-07
BASE_MODEL_ID = "urchade/gliner_large-v2.1"

# Nemotron-PII labels with a counterpart in Jude's schema. Deliberately
# excluded: `state` / `county` / `postcode` (jurisdictions and address
# fragments the gold does not annotate), `date*` / `time` (not
# redacted by Jude), demographic labels (`age`, `gender`, …).
NATIVE_LABEL_MAP: dict[str, str] = {
    "first_name": "PERSON",
    "last_name": "PERSON",
    "company_name": "ORG",
    "street_address": "LOC",
    "city": "LOC",
    "country": "LOC",
    "email": "EMAIL",
    "phone_number": "PHONE",
    "fax_number": "PHONE",
    "account_number": "IBAN",
    "bank_routing_number": "IBAN",
    "swift_bic": "IBAN",
    "tax_id": "IBAN",
    "national_id": "IBAN",
    "credit_debit_card": "IBAN",
    "customer_id": "IBAN",
    "unique_id": "IBAN",
    "url": "URL",
}


def jude_label_map() -> dict[str, str]:
    from jude.detect.gliner_detector import _LABELS_TO_TYPE

    return {label: etype.value for label, etype in _LABELS_TO_TYPE.items()}


_WS_ONLY = re.compile(r"^\s*$")


def merge_adjacent(preds: list[PredSpan], text: str) -> list[PredSpan]:
    """Merge consecutive same-type spans separated only by whitespace."""

    if not preds:
        return []
    ordered = sorted(preds, key=lambda p: (p.start, -p.end))
    out: list[PredSpan] = [ordered[0]]
    for cur in ordered[1:]:
        prev = out[-1]
        gap = text[prev.end:cur.start] if cur.start >= prev.end else None
        if (
            cur.type == prev.type
            and gap is not None
            and _WS_ONLY.match(gap)
        ):
            merged_end = max(prev.end, cur.end)
            out[-1] = PredSpan(
                start=prev.start,
                end=merged_end,
                type=prev.type,
                text=text[prev.start:merged_end],
            )
        else:
            out.append(cur)
    return out


# One implementation, shared with Jude's own GLiNER detector.
chunk_text = _chunk_text


class GlinerLabelRunner:
    """Any GLiNER checkpoint × any label map."""

    def __init__(
        self,
        name: str,
        model_id: str,
        label_map: dict[str, str],
        threshold: float = 0.5,
        revision: str | None = None,
        merge: bool = True,
        max_words: int = 200,
        device: str | None = None,
    ):
        import torch
        from gliner import GLiNER

        self.name = name
        self.model_id = model_id
        self.revision = revision
        self.label_map = dict(label_map)
        self.labels = list(label_map)
        self.threshold = threshold
        self.merge = merge
        self.max_words = max_words
        kwargs = {"revision": revision} if revision else {}
        self.model = GLiNER.from_pretrained(model_id, **kwargs)
        self.device = "cpu"
        want = device or ("mps" if torch.backends.mps.is_available() else "cpu")
        if want != "cpu":
            try:
                self.model.to(want)
                self.model.predict_entities("Warm-up: Jane Doe of Acme SA.", self.labels)
                self.device = want
            except Exception:
                self.model.to("cpu")
                self.device = "cpu"
        self.model.eval()

    def predict(self, text: str) -> list[PredSpan]:
        preds: list[PredSpan] = []
        for offset, chunk in chunk_text(text, self.max_words):
            ents = self.model.predict_entities(chunk, self.labels, threshold=self.threshold)
            for e in ents:
                jude_type = self.label_map.get(str(e.get("label", "")))
                if jude_type is None:
                    continue
                start = offset + int(e["start"])
                end = offset + int(e["end"])
                preds.append(PredSpan(start=start, end=end, type=jude_type, text=text[start:end]))
        preds = _dedupe(preds)
        if self.merge:
            preds = merge_adjacent(preds, text)
        return preds

    def extra_meta(self) -> dict:
        return {
            "model": self.model_id,
            "revision": self.revision,
            "threshold": self.threshold,
            "labels": self.labels,
            "chunk_words": self.max_words,
        }


def _dedupe(preds: Iterable[PredSpan]) -> list[PredSpan]:
    """GLiNER can return the same span under two labels that map to the
    same Jude type; keep one per (start, end, type), longest-first when
    spans nest."""

    seen: set[tuple[int, int, str]] = set()
    out: list[PredSpan] = []
    for p in sorted(preds, key=lambda p: (p.start, -(p.end - p.start))):
        key = (p.start, p.end, p.type)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


# --- factories used by benchmark.run -------------------------------------


def nvidia_native(threshold: float = 0.5) -> GlinerLabelRunner:
    suffix = "" if threshold == 0.5 else f"-t{threshold:.1f}".replace(".", "")
    return GlinerLabelRunner(
        name=f"nvidia-gliner-pii-native{suffix}",
        model_id=NVIDIA_MODEL_ID,
        revision=NVIDIA_REVISION,
        label_map=NATIVE_LABEL_MAP,
        threshold=threshold,
    )


def nvidia_jude_labels(threshold: float = 0.5) -> GlinerLabelRunner:
    return GlinerLabelRunner(
        name="nvidia-gliner-pii-jude-labels",
        model_id=NVIDIA_MODEL_ID,
        revision=NVIDIA_REVISION,
        label_map=jude_label_map(),
        threshold=threshold,
    )


def gliner_base_jude_labels(threshold: float = 0.5) -> GlinerLabelRunner:
    return GlinerLabelRunner(
        name="gliner-large-v2.1-jude-labels",
        model_id=BASE_MODEL_ID,
        label_map=jude_label_map(),
        threshold=threshold,
    )
