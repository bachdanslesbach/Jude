from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class EntityType(StrEnum):
    PERSON = "PERSON"
    ORG = "ORG"
    LOC = "LOC"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    IBAN = "IBAN"
    CASE_REF = "CASE_REF"
    URL = "URL"
    SECRET = "SECRET"
    OTHER = "OTHER"


class Mode(StrEnum):
    STRICT = "strict"
    SMART = "smart"


class DetectionSource(StrEnum):
    REGEX = "regex"
    PATTERN = "pattern"  # deterministic long-tail rules (legal forms, aliases, addresses …)
    KNOWN = "known"  # bundled public companies / banks flagged redact: true
    SPACY = "spacy"
    GLINER = "gliner"
    PRIVACY_FILTER = "privacy_filter"
    DICTIONARY = "dictionary"
    USER = "user"


class Detection(BaseModel):
    """A single span found in the input text by some detector."""

    model_config = ConfigDict(frozen=True)

    text: str
    start: int
    end: int
    entity_type: EntityType
    source: DetectionSource
    confidence: float = 1.0


class Entity(BaseModel):
    """A canonical entity with its assigned pseudonym, persisted per-matter."""

    id: int | None = None
    matter_id: str
    canonical: str
    entity_type: EntityType
    pseudonym: str
    public_context: str | None = None
    user_marked: bool = False
    surface_forms: set[str] = Field(default_factory=set)
    created_at: datetime | None = None


class Matter(BaseModel):
    id: str
    name: str
    mode: Mode = Mode.STRICT
    llm_endpoint: str = "anthropic"
    llm_model: str | None = None
    zero_retention_attested: bool = False
    notes: str | None = None
    # Ruling of 13 October 2026: deal codenames ("Project Ganymede") are
    # not identifiers by default. A matter may opt in — then the phrase
    # and its bare short form are redacted like any party name.
    redact_codenames: bool = False
    created_at: datetime | None = None


class Segment(BaseModel):
    """One emitted replacement: the span of the raw text that was replaced,
    where its replacement sits in the redacted text, and the entity it
    resolved to. Type-aware by construction (it comes out of `redact()`),
    unlike a surface lookup after the fact."""

    model_config = ConfigDict(frozen=True)

    raw_start: int
    raw_end: int
    red_start: int
    red_end: int
    entity_id: int


class RedactionResult(BaseModel):
    """Output of a redaction pass."""

    redacted_text: str
    detections: list[Detection]
    entities_used: list[Entity]
    mode: Mode
    # One per emitted span, in text order. Empty for results built by
    # callers that predate the field.
    segments: list[Segment] = Field(default_factory=list)
    # Ids of the entities this pass created in the store (not the ones
    # it reused). A review that is cancelled prunes exactly these.
    created_entity_ids: list[int] = Field(default_factory=list)
    # (entity_id, form) for every surface form this pass added to an
    # entity that already existed. A cancelled review removes exactly
    # these, so a pre-existing entity's dictionary is left as it was.
    added_surface_forms: list[tuple[int, str]] = Field(default_factory=list)


class Approval(BaseModel):
    """One row of the `approvals` ledger: a text the user approved for
    release, hashed and recorded on disk before anything left."""

    id: int
    review_id: str | None
    matter_id: str
    purpose: str
    payload_sha256: str
    chars: int | None
    endpoint: str
    endpoint_host: str
    mode: str | None
    zero_retention: bool
    n_hidden: int | None
    n_kept: int | None
    n_user_marked: int | None
    attestation: str
    approver_os_user: str
    ui_lang: str | None
    verified_at_send: int | None
    approved_at: datetime
    released_at: datetime | None
    # How the approval ended: released | refused | withdrawn | expired |
    # lost_on_restart. None while the text is still waiting for the model.
    outcome: str | None = None


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    id: int | None = None
    conversation_id: str
    role: MessageRole
    redacted_text: str          # what the LLM sees (pseudonymized)
    display_text: str           # what the user sees (originals or rehydrated)
    created_at: datetime | None = None


class Conversation(BaseModel):
    id: str
    matter_id: str
    title: str
    created_at: datetime | None = None


def normalize_surface(text: str) -> str:
    """Normalize a surface form for entity-merging lookup.

    Strips company suffixes, punctuation, and case. Naive but adequate for v0.
    """
    import re

    s = text.strip().lower()
    suffixes = (
        r"\b(inc\.?|llc|ltd\.?|limited|s\.?a\.?|sarl|sas|"
        r"gmbh|ag|n\.?v\.?|b\.?v\.?|plc|co\.?|corp\.?|"
        r"corporation|company|sprl|scrl|asbl)\b\.?"
    )
    s = re.sub(suffixes, "", s, flags=re.IGNORECASE)
    s = re.sub(r"[^\w\s.&-]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip(" .")
    return s
