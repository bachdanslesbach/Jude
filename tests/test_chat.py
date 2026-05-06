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


def test_send_turn_wikipedia_fallback_fills_context_for_unknown_entity(
    store: Store, smart_matter_id: str
):
    """When use_wikipedia=True is passed to send_turn, an entity not in the
    bundled dataset (here, a fictional client) gets its public_context
    populated by the chained Wikipedia provider."""

    from jude.types import EntityType

    class StubWikipedia:
        def lookup(self, canonical, entity_type):
            if entity_type == EntityType.ORG and "Lumen" in canonical:
                return "fake wikipedia summary about Lumen"
            return None

    conv = store.create_conversation(smart_matter_id, title="t")
    llm = FakeLLM(replies=["Reply mentioning Org1."])

    user_msg, _ = send_turn(
        conversation=conv,
        user_text="Lumen Reality SARL filed a complaint.",
        attachments=[],
        store=store,
        mode=Mode.SMART,
        llm=llm,
        wikipedia_provider=StubWikipedia(),
    )
    # The entity should now have the Wikipedia-derived context.
    ents = {e.canonical: e for e in store.list_entities(smart_matter_id)}
    assert any(
        c == "fake wikipedia summary about Lumen"
        for c in (e.public_context for e in ents.values())
    )


def test_preview_detection_returns_counts_by_type(
    store: Store, matter_id: str
):
    """Counts detections-by-type without persisting anything to the store
    or producing redacted text. Used by the UI live-preview panel so the
    user can sanity-check what Jude sees before they actually send a
    chat turn."""

    from jude.chat import preview_detection
    from jude.types import EntityType

    # Pre-populate one entity so the dictionary detector also fires.
    store.create_entity(matter_id, "Acme Corp", EntityType.ORG)

    text = (
        "Acme Corp paid €100,000 to alice@example.com. "
        "See Case T-1/24 and ECLI:EU:C:2024:512."
    )
    counts = preview_detection(text, store, matter_id)
    assert counts.get("ORG", 0) >= 1  # Acme Corp
    assert counts.get("EMAIL", 0) >= 1  # alice@example.com
    assert counts.get("CASE_REF", 0) >= 2  # T-1/24 + ECLI


def test_preview_detection_empty_text_returns_empty_dict(
    store: Store, matter_id: str
):
    from jude.chat import preview_detection

    assert preview_detection("", store, matter_id) == {}
    assert preview_detection("   \n  ", store, matter_id) == {}


def test_preview_detection_does_not_persist_anything(
    store: Store, matter_id: str
):
    """Critical: previewing must NOT create entities. Otherwise typing in
    the preview pane would silently populate the dictionary and surprise
    the user later."""

    from jude.chat import preview_detection

    before = len(store.list_entities(matter_id))
    preview_detection(
        "Acme Corp acquired Beta SARL in 2024.", store, matter_id
    )
    after = len(store.list_entities(matter_id))
    assert before == after


def test_prepare_turn_runs_detection_without_persisting_messages(
    store: Store, matter_id: str
):
    """prepare_turn() runs detection + redaction (entities ARE persisted
    so the dictionary stays consistent and pseudonyms are stable) but
    does NOT save any user/assistant message. The user can still cancel."""

    from jude.chat import prepare_turn

    conv = store.create_conversation(matter_id, title="t")
    prepared = prepare_turn(
        conversation=conv,
        user_text="Amazon paid €100M.",
        attachments=[],
        store=store,
        mode=Mode.STRICT,
    )
    # Entities created (so pseudonym allocation is committed)
    assert len(store.list_entities(matter_id)) >= 1
    # But no messages persisted
    assert store.list_messages(conv.id) == []
    # The prepared object exposes what the UI needs to render review.
    assert "Amazon" not in prepared.redacted_text
    assert "Amazon" in prepared.raw_text
    assert any(e.canonical == "Amazon" for e in prepared.entities)


def test_commit_streaming_turn_persists_both_messages_and_yields_chunks(
    store: Store, matter_id: str
):
    from jude.chat import commit_streaming_turn, prepare_turn
    from tests.test_streaming import StreamingFakeLLM

    conv = store.create_conversation(matter_id, title="t")
    prepared = prepare_turn(
        conversation=conv,
        user_text="Microsoft is mentioned.",
        attachments=[],
        store=store,
        mode=Mode.STRICT,
    )
    llm = StreamingFakeLLM(chunks=["Hello ", "from the ", "model."])
    pieces = list(commit_streaming_turn(
        conversation=conv,
        prepared=prepared,
        store=store,
        mode=Mode.STRICT,
        llm=llm,
    ))
    assert pieces  # something streamed
    msgs = store.list_messages(conv.id)
    assert len(msgs) == 2
    assert msgs[0].role == MessageRole.USER
    assert msgs[1].role == MessageRole.ASSISTANT


def test_prepare_then_discard_does_not_pollute_messages(
    store: Store, matter_id: str
):
    """If the user hits Cancel after preview, no message ever gets
    persisted — only the entities (which is fine because pseudonym
    stability is per-matter)."""

    from jude.chat import prepare_turn

    conv = store.create_conversation(matter_id, title="t")
    prepare_turn(
        conversation=conv,
        user_text="Some sensitive Amazon mention.",
        attachments=[],
        store=store,
        mode=Mode.STRICT,
    )
    assert store.list_messages(conv.id) == []
    assert any(e.canonical == "Amazon" for e in store.list_entities(matter_id))


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
