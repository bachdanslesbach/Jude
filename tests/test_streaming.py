"""Tests for streaming LLM responses.

The chat UI currently waits for the full LLM response before
rendering anything. With streaming, words appear as the model
produces them — a meaningful UX improvement.

Design:
  * LLMClient gains a `stream_chat(...)` method returning an
    Iterator[str]. Each yielded chunk is a piece of the assistant's
    reply text. Concatenating all chunks reproduces the full reply.
  * The default implementation falls back to `complete_chat` and
    yields the whole text at once — so any LLMClient subclass that
    doesn't implement streaming still works.
  * AnthropicClient and OllamaClient override with real streaming
    (Anthropic via the SDK's `messages.stream`, Ollama via
    NDJSON over the existing /api/chat endpoint).
  * Mode / zero-retention enforcement applies to streaming too.
  * The chat orchestrator gains `send_turn_streaming(...)` which is
    a generator yielding rehydrated cumulative text. It persists the
    user and assistant messages as in the synchronous path.
"""

from __future__ import annotations

import pytest

from jude.chat import FileAttachment, send_turn_streaming
from jude.llm.base import LLMClient, LLMResponse
from jude.store import Store
from jude.types import MessageRole, Mode


class StreamingFakeLLM(LLMClient):
    """Yields a fixed list of chunks for stream_chat; for complete_chat,
    returns the joined text. Used to test the chat orchestrator's
    streaming generator without hitting any real API."""

    name = "streaming-fake"

    def __init__(self, chunks: list[str]):
        self.chunks = list(chunks)
        self.calls: list[list[dict[str, str]]] = []

    def complete_chat(self, system, messages, mode, zero_retention_attested):
        self._enforce_mode(mode, zero_retention_attested)
        self.calls.append(messages)
        return LLMResponse(text="".join(self.chunks), model="streaming-fake")

    def stream_chat(self, system, messages, mode, zero_retention_attested):
        self._enforce_mode(mode, zero_retention_attested)
        self.calls.append(messages)
        for c in self.chunks:
            yield c


# ---------- LLMClient default fallback ----------


def test_default_stream_chat_yields_full_text_at_once():
    """Subclasses that only implement complete_chat should still expose
    a working stream_chat via the default in the base class."""

    class OnlyComplete(LLMClient):
        name = "fallback"

        def complete_chat(self, system, messages, mode, zero_retention_attested):
            self._enforce_mode(mode, zero_retention_attested)
            return LLMResponse(text="Hello world", model="fallback")

    c = OnlyComplete()
    chunks = list(c.stream_chat("", [{"role": "user", "content": "hi"}], Mode.STRICT, False))
    assert chunks == ["Hello world"]


def test_stream_chat_enforces_smart_mode_attestation():
    """Streaming must respect the same mode-vs-attestation guard the
    synchronous path does."""

    class S(LLMClient):
        name = "s"

        def complete_chat(self, system, messages, mode, zero_retention_attested):
            self._enforce_mode(mode, zero_retention_attested)
            return LLMResponse(text="x", model="s")

    c = S()
    with pytest.raises(PermissionError, match="zero-retention"):
        list(c.stream_chat("", [{"role": "user", "content": "x"}], Mode.SMART, False))


# ---------- chat orchestrator streaming ----------


def test_send_turn_streaming_yields_rehydrated_cumulative_text(
    store: Store, matter_id: str
):
    conv = store.create_conversation(matter_id, title="t")
    llm = StreamingFakeLLM(chunks=[
        "Reasoning about ", "Org1 in detail.",
    ])

    pieces = list(send_turn_streaming(
        conversation=conv,
        user_text="Amazon paid the price.",
        attachments=[],
        store=store,
        mode=Mode.STRICT,
        llm=llm,
    ))
    assert pieces, "generator must yield at least one chunk"
    final = pieces[-1]
    # Cumulative text grows monotonically.
    for i in range(1, len(pieces)):
        assert pieces[i].startswith(pieces[i - 1]) or len(pieces[i]) >= len(pieces[i - 1])
    # Final text is rehydrated (canonicals replace pseudonyms).
    assert "Amazon" in final
    assert "Org1" not in final


def test_send_turn_streaming_persists_both_messages(
    store: Store, matter_id: str
):
    conv = store.create_conversation(matter_id, title="t")
    llm = StreamingFakeLLM(chunks=["First ", "second ", "third."])

    list(send_turn_streaming(
        conversation=conv,
        user_text="Microsoft is a counterparty.",
        attachments=[],
        store=store,
        mode=Mode.STRICT,
        llm=llm,
    ))
    msgs = store.list_messages(conv.id)
    assert [m.role for m in msgs] == [MessageRole.USER, MessageRole.ASSISTANT]
    assert msgs[0].redacted_text != msgs[0].display_text  # USER msg redacted
    assert "First second third." == msgs[1].redacted_text  # streamed pieces joined
    assert msgs[1].display_text == "First second third."  # nothing to rehydrate


def test_send_turn_streaming_passes_full_history_to_llm(
    store: Store, matter_id: str
):
    conv = store.create_conversation(matter_id, title="t")
    llm = StreamingFakeLLM(chunks=["a", "b"])
    list(send_turn_streaming(conv, "Amazon does X.", [], store, Mode.STRICT, llm))
    list(send_turn_streaming(conv, "What about Microsoft?", [], store, Mode.STRICT, llm))

    second_call = llm.calls[-1]
    roles = [m["role"] for m in second_call]
    # Prior user + prior assistant + new user
    assert roles == ["user", "assistant", "user"]
