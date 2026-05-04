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
    OTHER = "OTHER"


class Mode(StrEnum):
    STRICT = "strict"
    SMART = "smart"


class DetectionSource(StrEnum):
    REGEX = "regex"
    SPACY = "spacy"
    GLINER = "gliner"
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
    zero_retention_attested: bool = False
    created_at: datetime | None = None


class RedactionResult(BaseModel):
    """Output of a redaction pass."""

    redacted_text: str
    detections: list[Detection]
    entities_used: list[Entity]
    mode: Mode


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
