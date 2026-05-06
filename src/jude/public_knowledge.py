"""Public-knowledge whitelist — institutions that should NEVER be redacted.

The bundled known-entities dataset (`src/jude/data/known_entities.json`)
classifies each entry with a boolean `redact` flag:

  * `redact: true`   — public companies (Amazon, Microsoft, etc.).
                       Their corporate identity is public, but in any
                       given matter they may BE the client or a
                       counterparty whose involvement is confidential,
                       so we still pseudonymise them.
  * `redact: false`  — public institutions, regulators, courts, NCAs,
                       DPAs, financial bodies. Their mention in a
                       legal document does not identify a client; on
                       the contrary, redacting them forces the LLM to
                       reason without any regulatory framing.

This module exposes `is_public_no_redact(text, entity_type)` which
matches the surface form against the bundled set's `redact: false`
entries (canonical + aliases, normalised). Used by the redact
pipeline to skip these entities entirely.
"""

from __future__ import annotations

from functools import lru_cache

from .context import _load_bundled  # cached loader, returns dict records
from .types import EntityType, normalize_surface


@lru_cache(maxsize=1)
def _no_redact_index() -> dict[tuple[str, str], dict]:
    """{(normalized_form, type): record} for every bundled entry whose
    `redact` is explicitly false. Loads once per process."""

    index: dict[tuple[str, str], dict] = {}
    for rec in _load_bundled():
        if rec.get("redact", True):
            continue  # default: redactable
        for norm in rec.get("_normalized_aliases", set()):
            index[(norm, rec["type"])] = rec
    return index


def is_public_no_redact(text: str, entity_type: EntityType) -> bool:
    """True if `text` matches a bundled public-knowledge entity that is
    flagged as `redact: false`."""

    norm = normalize_surface(text)
    if not norm:
        return False
    return (norm, entity_type.value) in _no_redact_index()
