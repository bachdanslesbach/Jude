"""Chat orchestrator: ties redaction, LLM, and rehydration into one turn.

The chat UI calls `send_turn()` with the user's text + optional files.
This module:

  1. Concatenates attached files (text/docx/pdf) into the user's message.
  2. Runs detection + redaction; new entities get pseudonyms, known ones reuse.
  3. Persists the user message (redacted + display copies).
  4. Builds the full conversation history in redacted form for the LLM.
  5. Calls the LLM; receives the raw (still-pseudonymized) response.
  6. Rehydrates the response and persists the assistant message.
"""

from __future__ import annotations

from pathlib import Path

from typing import Iterator

from pydantic import BaseModel, ConfigDict

from .adapters import DocxAdapter, PdfAdapter, TextAdapter, XlsxAdapter
from .context import ContextProvider, make_provider
from .detect import DetectionPipeline
from .llm.base import LLMClient
from .redact import redact, redact_two_pass
from .rehydrate import rehydrate
from .store import Store
from .types import Conversation, Detection, Entity, Message, MessageRole, Mode


class PreparedTurn(BaseModel):
    """A user turn that has been detected + redacted but not yet sent.

    The entities are already persisted in the per-matter store (so
    pseudonym allocation is stable), but the user message and the
    assistant message have NOT been written to the conversation log.
    The UI shows the user this object's `redacted_text` for review;
    on approval we move on to `commit_streaming_turn` which finally
    persists messages and calls the LLM.

    `detections` exposes the (start, end) spans in `raw_text` that
    will be replaced — used by the UI to highlight them inline so
    the user sees exactly what's being redacted before they approve.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    raw_text: str
    redacted_text: str
    entities: list[Entity]
    detections: list[Detection] = []
    conversation_id: str


class FileAttachment:
    """A file the user attached to the next chat turn."""

    def __init__(self, name: str, data: bytes):
        self.name = name
        self.data = data


def read_attachment_text(att: FileAttachment, *, enable_ocr: bool = False) -> str:
    """Read a single attachment to plain text using the right adapter."""

    suffix = Path(att.name).suffix.lower()
    tmp = Path("/tmp") / f"jude_chat_{att.name}"
    tmp.write_bytes(att.data)
    try:
        if suffix == ".docx":
            return DocxAdapter.read(tmp).text
        if suffix == ".pdf":
            return PdfAdapter.read(tmp, enable_ocr=enable_ocr).text
        if suffix == ".xlsx":
            return XlsxAdapter.read(tmp).text
        return TextAdapter.read(tmp)
    finally:
        tmp.unlink(missing_ok=True)


def compose_user_message(text: str, attachments: list[FileAttachment]) -> str:
    """Combine user text + attachments into the single string sent through redaction."""

    parts: list[str] = []
    for att in attachments:
        try:
            content = read_attachment_text(att)
        except Exception as e:  # noqa: BLE001
            content = f"<could not read {att.name}: {e}>"
        parts.append(f"[Attached: {att.name}]\n\n{content}")
    if text.strip():
        parts.append(text)
    return "\n\n---\n\n".join(parts)


def prepare_turn(
    conversation: Conversation,
    user_text: str,
    attachments: list[FileAttachment],
    store: Store,
    mode: Mode,
    use_privacy_filter: bool = False,
    use_wikipedia: bool = False,
    wikipedia_provider: ContextProvider | None = None,
) -> PreparedTurn:
    """Detect + redact for review. Entities ARE persisted (pseudonym
    stability), but no message is written to the conversation log yet."""

    matter = store.get_matter(conversation.matter_id)
    if matter is None:
        raise ValueError(f"Unknown matter for conversation {conversation.id}")

    raw = compose_user_message(user_text, attachments)
    pipeline = DetectionPipeline(
        store=store,
        matter_id=matter.id,
        use_privacy_filter=use_privacy_filter,
    )
    provider = make_provider(
        use_wikipedia=use_wikipedia or wikipedia_provider is not None,
        wikipedia_provider=wikipedia_provider,
    )
    redaction = redact_two_pass(
        raw, pipeline, store, matter.id, mode,
        context_provider=provider,
    )
    return PreparedTurn(
        raw_text=raw,
        redacted_text=redaction.redacted_text,
        entities=redaction.entities_used,
        detections=redaction.detections,
        conversation_id=conversation.id,
    )


def commit_streaming_turn(
    conversation: Conversation,
    prepared: PreparedTurn,
    store: Store,
    mode: Mode,
    llm: LLMClient,
) -> Iterator[str]:
    """Persist the user message from a prepared turn, stream the assistant
    reply, and persist the assistant message at end-of-stream. Yields
    rehydrated cumulative text the same way send_turn_streaming does."""

    matter = store.get_matter(conversation.matter_id)
    if matter is None:
        raise ValueError(f"Unknown matter for conversation {conversation.id}")

    store.add_message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        redacted_text=prepared.redacted_text,
        display_text=prepared.raw_text,
    )

    history = store.list_messages(conversation.id)
    llm_messages = [
        {"role": m.role.value, "content": m.redacted_text} for m in history
    ]

    cumulative_redacted = ""
    cumulative_rehydrated = ""
    for chunk in llm.stream_chat(
        system="",
        messages=llm_messages,
        mode=mode,
        zero_retention_attested=matter.zero_retention_attested,
    ):
        cumulative_redacted += chunk
        cumulative_rehydrated = rehydrate(cumulative_redacted, store, matter.id)
        yield cumulative_rehydrated

    store.add_message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        redacted_text=cumulative_redacted,
        display_text=cumulative_rehydrated,
    )


def preview_detection(
    text: str,
    store: Store,
    matter_id: str,
    use_privacy_filter: bool = False,
) -> dict[str, int]:
    """Run detection only (no redaction, no persistence) and return a
    {EntityType.value: count} summary.

    Used by the UI's "preview redaction" panel. Critically, this does
    not write to the per-matter store — pasting text into the preview
    must not silently populate the dictionary.
    """

    if not text.strip():
        return {}
    pipeline = DetectionPipeline(
        store=store,
        matter_id=matter_id,
        use_privacy_filter=use_privacy_filter,
    )
    counts: dict[str, int] = {}
    for d in pipeline.detect(text):
        counts[d.entity_type.value] = counts.get(d.entity_type.value, 0) + 1
    return counts


def send_turn(
    conversation: Conversation,
    user_text: str,
    attachments: list[FileAttachment],
    store: Store,
    mode: Mode,
    llm: LLMClient,
    use_privacy_filter: bool = False,
    use_wikipedia: bool = False,
    wikipedia_provider: ContextProvider | None = None,
) -> tuple[Message, Message]:
    """Run one full chat turn. Returns (saved_user_message, saved_assistant_message).

    `use_privacy_filter` enables the optional 5th detector backed by
    `openai/privacy-filter` for addresses, secrets and additional PII coverage.
    Requires `pip install jude[privacy-filter]`.

    `use_wikipedia` (or passing an explicit `wikipedia_provider`) chains a
    Wikipedia-backed context provider after the bundled known-entities
    dataset. This sends entity names to Wikipedia's REST API and should be
    opt-in per matter.
    """

    matter = store.get_matter(conversation.matter_id)
    if matter is None:
        raise ValueError(f"Unknown matter for conversation {conversation.id}")

    raw_user_text = compose_user_message(user_text, attachments)
    pipeline = DetectionPipeline(
        store=store,
        matter_id=matter.id,
        use_privacy_filter=use_privacy_filter,
    )
    provider = make_provider(
        use_wikipedia=use_wikipedia or wikipedia_provider is not None,
        wikipedia_provider=wikipedia_provider,
    )
    # Two-pass: a first detect+redact populates the per-matter dictionary
    # so a second detection sweep catches title/header occurrences that
    # spaCy missed in pass 1.
    redaction = redact_two_pass(
        raw_user_text, pipeline, store, matter.id, mode,
        context_provider=provider,
    )

    user_msg = store.add_message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        redacted_text=redaction.redacted_text,
        display_text=raw_user_text,
    )

    history = store.list_messages(conversation.id)
    llm_messages = [
        {"role": m.role.value, "content": m.redacted_text} for m in history
    ]
    response = llm.complete_chat(
        system="",
        messages=llm_messages,
        mode=mode,
        zero_retention_attested=matter.zero_retention_attested,
    )

    rehydrated = rehydrate(response.text, store, matter.id)
    assistant_msg = store.add_message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        redacted_text=response.text,
        display_text=rehydrated,
    )
    return user_msg, assistant_msg


def send_turn_streaming(
    conversation: Conversation,
    user_text: str,
    attachments: list[FileAttachment],
    store: Store,
    mode: Mode,
    llm: LLMClient,
    use_privacy_filter: bool = False,
    use_wikipedia: bool = False,
    wikipedia_provider: ContextProvider | None = None,
) -> Iterator[str]:
    """Generator-flavoured `send_turn`. Yields the rehydrated cumulative
    response text as the LLM streams.

    The user message is detected, redacted and persisted up-front (same
    as the synchronous path). The assistant message is persisted at the
    end, after the stream finishes — its `redacted_text` is the joined
    chunks and its `display_text` is the rehydrated form.

    Designed to be passed straight to Streamlit's `st.write_stream(...)`.
    """

    matter = store.get_matter(conversation.matter_id)
    if matter is None:
        raise ValueError(f"Unknown matter for conversation {conversation.id}")

    raw_user_text = compose_user_message(user_text, attachments)
    pipeline = DetectionPipeline(
        store=store,
        matter_id=matter.id,
        use_privacy_filter=use_privacy_filter,
    )
    provider = make_provider(
        use_wikipedia=use_wikipedia or wikipedia_provider is not None,
        wikipedia_provider=wikipedia_provider,
    )
    redaction = redact_two_pass(
        raw_user_text, pipeline, store, matter.id, mode,
        context_provider=provider,
    )
    store.add_message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        redacted_text=redaction.redacted_text,
        display_text=raw_user_text,
    )

    history = store.list_messages(conversation.id)
    llm_messages = [
        {"role": m.role.value, "content": m.redacted_text} for m in history
    ]

    cumulative_redacted = ""
    cumulative_rehydrated = ""
    for chunk in llm.stream_chat(
        system="",
        messages=llm_messages,
        mode=mode,
        zero_retention_attested=matter.zero_retention_attested,
    ):
        cumulative_redacted += chunk
        cumulative_rehydrated = rehydrate(cumulative_redacted, store, matter.id)
        yield cumulative_rehydrated

    store.add_message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        redacted_text=cumulative_redacted,
        display_text=cumulative_rehydrated,
    )
