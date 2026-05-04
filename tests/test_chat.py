from __future__ import annotations

from jude.chat import FileAttachment, compose_user_message, send_turn
from jude.llm.base import LLMClient, LLMResponse
from jude.store import Store
from jude.types import MessageRole, Mode


class FakeLLM(LLMClient):
    name = "fake"

    def __init__(self, replies: list[str]):
        self.replies = list(replies)
        self.calls: list[list[dict[str, str]]] = []

    def complete_chat(self, system, messages, mode, zero_retention_attested):
        self._enforce_mode(mode, zero_retention_attested)
        self.calls.append(messages)
        text = self.replies.pop(0) if self.replies else "OK"
        return LLMResponse(text=text, model="fake-1")


def test_compose_user_message_combines_attachments_and_text(tmp_path):
    text_file = tmp_path / "memo.txt"
    text_file.write_text("Document body about Amazon.", encoding="utf-8")

    attachment = FileAttachment("memo.txt", text_file.read_bytes())
    composed = compose_user_message(
        "What's the strongest argument?", [attachment]
    )
    assert "[Attached: memo.txt]" in composed
    assert "Document body about Amazon." in composed
    assert "What's the strongest argument?" in composed


def test_send_turn_persists_user_and_assistant_messages_strict(
    store: Store, matter_id: str
):
    conv = store.create_conversation(matter_id, title="t")
    llm = FakeLLM(replies=["Reasoned reply mentioning Org1."])

    user_msg, assistant_msg = send_turn(
        conversation=conv,
        user_text="Amazon competes with Microsoft.",
        attachments=[],
        store=store,
        mode=Mode.STRICT,
        llm=llm,
    )

    assert user_msg.role == MessageRole.USER
    assert assistant_msg.role == MessageRole.ASSISTANT
    # Strict mode: real names must be fully gone from the redacted text.
    assert "Amazon" not in user_msg.redacted_text
    assert "Microsoft" not in user_msg.redacted_text
    assert "Org1" in user_msg.redacted_text
    # Display keeps the original.
    assert "Amazon" in user_msg.display_text
    # Assistant reply gets rehydrated.
    assert "Amazon" in assistant_msg.display_text
    assert "Org1" in assistant_msg.redacted_text


def test_send_turn_smart_mode_includes_public_context_in_redacted(
    store: Store, smart_matter_id: str
):
    """Smart mode is expected to leak some public-knowledge text via context tags
    (that's the whole point). What we verify here is that:
      - the user's surface form is replaced with a pseudonym, AND
      - the bundled context tag is appended in parentheses on first mention.
    """

    conv = store.create_conversation(smart_matter_id, title="t")
    llm = FakeLLM(replies=["Reply about Org1."])

    user_msg, _ = send_turn(
        conversation=conv,
        user_text="Microsoft is the partner here.",
        attachments=[],
        store=store,
        mode=Mode.SMART,
        llm=llm,
    )
    # "Microsoft" canonical doesn't appear in its own bundled context, so the
    # original surface form should be gone from the redacted text.
    assert "Microsoft" not in user_msg.redacted_text
    # Pseudonym + smart-mode parenthetical context.
    assert "Org1" in user_msg.redacted_text
    assert "DMA-designated gatekeeper" in user_msg.redacted_text


def test_send_turn_passes_full_history_to_llm(
    store: Store, smart_matter_id: str
):
    conv = store.create_conversation(smart_matter_id, title="t")
    llm = FakeLLM(replies=["First reply.", "Second reply."])

    send_turn(conv, "Amazon does X.", [], store, Mode.SMART, llm)
    send_turn(conv, "What about Microsoft?", [], store, Mode.SMART, llm)

    second_call_messages = llm.calls[-1]
    # The second LLM call must contain four messages: u/a/u/a-of-this-call... actually
    # complete_chat is called with the history INCLUDING the new user but NOT the
    # not-yet-saved assistant. So 3 messages.
    roles = [m["role"] for m in second_call_messages]
    assert roles == ["user", "assistant", "user"]
    # And the last user message is the redacted second one
    assert "Microsoft" not in second_call_messages[-1]["content"]
    assert "Org" in second_call_messages[-1]["content"]


def test_send_turn_refuses_smart_without_zr(store: Store):
    matter = store.create_matter("strict-only", mode=Mode.STRICT)
    conv = store.create_conversation(matter.id, title="t")
    llm = FakeLLM(replies=["never reached"])
    try:
        send_turn(conv, "Amazon.", [], store, Mode.SMART, llm)
    except ValueError as e:
        assert "smart" in str(e).lower()
    else:
        raise AssertionError("expected ValueError for smart mode without ZR")


def test_pseudonyms_are_stable_across_turns(
    store: Store, smart_matter_id: str
):
    conv = store.create_conversation(smart_matter_id, title="t")
    llm = FakeLLM(replies=["a", "b"])

    u1, _ = send_turn(conv, "Amazon and Microsoft.", [], store, Mode.SMART, llm)
    u2, _ = send_turn(conv, "Amazon again.", [], store, Mode.SMART, llm)

    # Org1 should appear in both with the same identity (i.e. same canonical maps to same pseudonym)
    ents = {e.canonical: e.pseudonym for e in store.list_entities(smart_matter_id)}
    assert "Amazon" in ents
    amazon_pseud = ents["Amazon"]
    assert amazon_pseud in u1.redacted_text
    assert amazon_pseud in u2.redacted_text
