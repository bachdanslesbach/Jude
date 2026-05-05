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

from .adapters import DocxAdapter, PdfAdapter, TextAdapter
from .detect import DetectionPipeline
from .llm.base import LLMClient
from .redact import redact
from .rehydrate import rehydrate
from .store import Store
from .types import Conversation, Message, MessageRole, Mode


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


def send_turn(
    conversation: Conversation,
    user_text: str,
    attachments: list[FileAttachment],
    store: Store,
    mode: Mode,
    llm: LLMClient,
    use_privacy_filter: bool = False,
) -> tuple[Message, Message]:
    """Run one full chat turn. Returns (saved_user_message, saved_assistant_message).

    `use_privacy_filter` enables the optional 5th detector backed by
    `openai/privacy-filter` for addresses, secrets and additional PII coverage.
    Requires `pip install jude[privacy-filter]`.
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
    detections = pipeline.detect(raw_user_text)
    redaction = redact(raw_user_text, detections, store, matter.id, mode)

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
