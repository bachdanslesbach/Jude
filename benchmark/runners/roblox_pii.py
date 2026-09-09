"""External model: `roblox/roblox-pii-classifier`.

XLM-RoBERTa-large (0.56 B) fine-tuned as a **message-level multi-label
classifier** with two heads, `p_privacy_asking_for_pii` and
`p_privacy_giving_pii` (Apache 2.0). It does not extract spans, so it
is scored only on the sentence-level grid (see `benchmark.sentence_eval`)
where every other runner is projected too. Decision rule from the
model card: positive iff max(asking, giving) >= 0.2691.
"""

from __future__ import annotations

from ..schema import PredSpan
from ..sentence_eval import split_sentences

MODEL_ID = "roblox/roblox-pii-classifier"
REVISION = "253c2057916145e1862087783858d52a7daeb716"
THRESHOLD = 0.2691


class RobloxPiiRunner:
    name = "roblox-pii-classifier"
    sentence_level_only = True

    def __init__(self, device: str | None = None, batch_size: int = 16):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=REVISION)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            MODEL_ID, revision=REVISION
        )
        self.device = device or ("mps" if torch.backends.mps.is_available() else "cpu")
        self.model.to(self.device).eval()
        self.batch_size = batch_size
        self._max_probs: list[float] = []
        self.classify(["Warm-up: my email is jane@example.org"])

    def classify(self, texts: list[str]) -> list[tuple[float, float]]:
        import torch

        out: list[tuple[float, float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            enc = self.tokenizer(
                batch, return_tensors="pt", padding=True, truncation=True, max_length=512
            )
            enc = {k: v.to(self.device) for k, v in enc.items()}
            with torch.no_grad():
                logits = self.model(**enc).logits
            probs = torch.sigmoid(logits.float()).cpu().tolist()
            out.extend((float(p[0]), float(p[1])) for p in probs)
        return out

    def predict_sentences(self, text: str) -> tuple[list[tuple[int, int]], list[bool]]:
        sents = split_sentences(text)
        probs = self.classify([text[s:e] for s, e in sents])
        flags = []
        for asking, giving in probs:
            m = max(asking, giving)
            self._max_probs.append(m)
            flags.append(m >= THRESHOLD)
        return sents, flags

    def predict(self, text: str) -> list[PredSpan]:
        # Not a span extractor; kept so the object still satisfies the
        # runner protocol for tooling that introspects it.
        return []

    def extra_meta(self) -> dict:
        ps = self._max_probs
        return {
            "model": MODEL_ID,
            "revision": REVISION,
            "params_m": 560,
            "licence": "Apache-2.0",
            "threshold": THRESHOLD,
            "mean_max_prob": (sum(ps) / len(ps)) if ps else None,
            "notes": [
                "Message-level classifier (asking-for / giving PII); no spans. "
                "Scored on the sentence grid only.",
                "Trained on chat; the model card itself reports 45.5% F1 on the "
                "Kaggle PII essay dataset.",
            ],
        }
