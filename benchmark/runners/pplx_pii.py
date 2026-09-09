"""External model: `perplexity-ai/pplx-pii-masking`.

~600 M-parameter bidirectional Qwen3 encoder with a BIOES token-
classification head and a constrained Viterbi decoder (MIT licence,
September 2026). Loaded through `trust_remote_code=True`; the remote
code was reviewed and is pinned to a revision below so a later push to
the hub cannot change what runs on this machine.

Label policy
------------
The model's nine labels are mapped onto Jude's schema where a
counterpart exists. Two labels have none and are dropped **and
counted** (`meta["out_of_schema"]`) rather than scored as false
positives:

* `private_date` — Jude does not redact dates (a matter's timeline is
  reasoning-critical and rarely identifying on its own).
* `other_pii`    — catch-all with no definition on the model card.

There is no organisation label at all, so ORG recall is 0 by
construction — the single largest gap for legal work, where the
parties are companies.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from ..schema import PredSpan

MODEL_ID = "perplexity-ai/pplx-pii-masking"
REVISION = "f1f90a53823f5df0a1344c1e137d9fffdaab54d6"  # 2026-09-02

PPLX_LABEL_MAP: dict[str, str] = {
    "private_person": "PERSON",
    "private_email": "EMAIL",
    "private_phone": "PHONE",
    "private_address": "LOC",
    "private_url": "URL",
    "account_number": "IBAN",
    "secret": "SECRET",
}


def convert_spans(spans: Iterable, text: str) -> tuple[list[PredSpan], dict[str, int]]:
    """Map model spans (objects with .start/.end/.label) to PredSpans.

    Returns the in-schema predictions and a {label: count} of dropped
    out-of-schema spans.
    """

    preds: list[PredSpan] = []
    dropped: Counter[str] = Counter()
    for s in spans:
        jude_type = PPLX_LABEL_MAP.get(s.label)
        if jude_type is None:
            dropped[s.label] += 1
            continue
        preds.append(PredSpan(start=s.start, end=s.end, type=jude_type, text=text[s.start:s.end]))
    return preds, dict(dropped)


class PplxPiiRunner:
    name = "pplx-pii-masking"

    def __init__(self, device: str | None = None):
        import torch
        from transformers import AutoModel

        self.model = AutoModel.from_pretrained(
            MODEL_ID, trust_remote_code=True, revision=REVISION
        )
        self.device = device or ("mps" if torch.backends.mps.is_available() else "cpu")
        self.model.to(self.device).eval()
        self._dropped: Counter[str] = Counter()
        self._sensitivity: list[float] = []
        # Warm-up: the first MPS call compiles kernels (~8 s) and would
        # otherwise be booked against the first document.
        self.model.predict("Warm-up: Jane Doe, jane@example.org.")

    def predict(self, text: str) -> list[PredSpan]:
        spans, sensitivity = self.model.predict(text)
        preds, dropped = convert_spans(spans, text)
        self._dropped.update(dropped)
        self._sensitivity.append(float(sensitivity))
        return preds

    def extra_meta(self) -> dict:
        sens = self._sensitivity
        return {
            "model": MODEL_ID,
            "revision": REVISION,
            "params_m": 596,
            "licence": "MIT (trust_remote_code)",
            "out_of_schema": dict(self._dropped),
            "mean_document_sensitivity": (sum(sens) / len(sens)) if sens else None,
            "notes": [
                "No organisation label: ORG recall is 0 by construction.",
                "`private_date` / `other_pii` predictions dropped as out-of-schema "
                "(counted, not scored as FP).",
                "Input truncated at 4096 tokens; corpus documents are far shorter.",
            ],
        }
