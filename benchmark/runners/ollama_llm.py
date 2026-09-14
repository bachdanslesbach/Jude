"""A local generative LLM as the span extractor, through Ollama.

The "few-billion-parameter LLM" rung of the model-size ladder. The
model is prompted to list every identifier in the document as JSON
(`{"text": ..., "type": ...}`); every occurrence of each listed surface
becomes a predicted span (the same convention the corpus builder uses
for gold). Reasoning/"thinking" is switched off so the timing reflects
extraction, not deliberation. Runs against a local daemon at
http://localhost:11434 — nothing leaves the machine.
"""

from __future__ import annotations

import json
import re
import time
import urllib.request

from ..schema import PredSpan

TYPES = ("PERSON", "ORG", "LOC", "EMAIL", "PHONE", "IBAN", "CASE_REF", "URL", "SECRET")

_SYSTEM = (
    "You redact legal documents before they are sent to an outside AI service. "
    "List EVERY identifier that could reveal a party, adviser, witness, matter or "
    "account: people (with or without titles), companies and firms (with legal-form "
    "suffixes), deal codenames, street addresses and cities of parties, e-mail "
    "addresses, phone numbers, IBANs and account/registry numbers, case or docket "
    "references, web domains, secrets. Do NOT list public institutions, regulators, "
    "courts, statutes, treaties, countries, or generic roles (the Buyer, our client). "
    "Return ONLY a JSON object: {\"entities\": [{\"text\": \"<exact substring as it appears>\", "
    "\"type\": \"<PERSON|ORG|LOC|EMAIL|PHONE|IBAN|CASE_REF|URL|SECRET>\"}, ...]}. "
    "Copy each surface form verbatim, including every distinct variant (full name, "
    "surname only, acronym)."
)


class OllamaSpanRunner:
    def __init__(self, model: str = "qwen3:4b", host: str = "http://localhost:11434",
                 timeout: int = 1800):
        self.model = model
        self.host = host
        self.timeout = timeout
        self.name = "ollama-" + re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-")
        self.device = "ollama"
        self._raw_failures = 0
        self._tokens_out = 0
        self._eval_seconds = 0.0
        # Warm-up: loads the weights so the first document is not charged
        # for it (load time is reported separately by the harness).
        self._chat("Warm-up. Return {\"entities\": []}.")

    def _chat(self, user: str) -> dict:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}],
            "stream": False,
            "format": "json",
            "think": False,
            "options": {"temperature": 0, "num_ctx": 8192},
        }
        req = urllib.request.Request(
            f"{self.host}/api/chat", data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310 — localhost only
            return json.loads(resp.read().decode("utf-8"))

    def predict(self, text: str) -> list[PredSpan]:
        # One retry: the daemon occasionally unloads the model between
        # documents and the reload can exceed the read timeout. A second
        # failure counts as a document with no predictions.
        resp: dict = {}
        for attempt in (1, 2):
            try:
                resp = self._chat("Document:\n\n" + text)
                break
            except (OSError, TimeoutError) as e:  # urllib raises URLError(OSError)
                self._raw_failures += 1
                if attempt == 2:
                    print(f"[ollama] giving up on a document after two failures: {e}")
                    return []
        self._tokens_out += int(resp.get("eval_count", 0))
        self._eval_seconds += float(resp.get("eval_duration", 0)) / 1e9
        content = (resp.get("message") or {}).get("content") or ""
        try:
            data = json.loads(content)
            items = data.get("entities", []) if isinstance(data, dict) else data
        except json.JSONDecodeError:
            self._raw_failures += 1
            items = []
        cands: list[tuple[int, int, str]] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            surface = str(it.get("text", "")).strip()
            typ = str(it.get("type", "")).upper().strip()
            if not surface or typ not in TYPES:
                continue
            for m in re.finditer(r"(?<!\w)" + re.escape(surface) + r"(?!\w)", text):
                cands.append((m.start(), m.end(), typ))
        # Longest-first, non-overlapping.
        kept: list[tuple[int, int, str]] = []
        for c in sorted(cands, key=lambda c: (-(c[1] - c[0]), c[0])):
            if any(not (c[1] <= k[0] or k[1] <= c[0]) for k in kept):
                continue
            kept.append(c)
        kept.sort()
        return [PredSpan(start=s, end=e, type=t, text=text[s:e]) for s, e, t in kept]

    def extra_meta(self) -> dict:
        return {
            "model": self.model,
            "licence": "model-specific (Apache-2.0 for Qwen3)",
            "json_failures": self._raw_failures,
            "tokens_generated": self._tokens_out,
            "tokens_per_sec": (self._tokens_out / self._eval_seconds) if self._eval_seconds else None,
            "notes": [
                "Generative extraction via Ollama (local); thinking disabled, temperature 0.",
                "Surfaces are located by exact string search — every occurrence counts.",
            ],
        }
