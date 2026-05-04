from jude.store import Store
from jude.types import MessageRole, Mode


def test_create_and_list_conversations(store: Store, matter_id: str):
    a = store.create_conversation(matter_id, title="First")
    b = store.create_conversation(matter_id, title="Second")
    convs = store.list_conversations(matter_id)
    ids = [c.id for c in convs]
    # Most recent first
    assert ids[0] == b.id
    assert a.id in ids


def test_conversations_scoped_to_matter(store: Store):
    m1 = store.create_matter("M1", mode=Mode.STRICT)
    m2 = store.create_matter("M2", mode=Mode.STRICT)
    store.create_conversation(m1.id, title="m1-conv")
    store.create_conversation(m2.id, title="m2-conv")
    assert len(store.list_conversations(m1.id)) == 1
    assert len(store.list_conversations(m2.id)) == 1


def test_rename_and_delete_conversation(store: Store, matter_id: str):
    c = store.create_conversation(matter_id, title="old")
    store.rename_conversation(c.id, "new")
    refetched = store.get_conversation(c.id)
    assert refetched.title == "new"

    store.delete_conversation(c.id)
    assert store.get_conversation(c.id) is None


def test_messages_persist_in_order(store: Store, matter_id: str):
    c = store.create_conversation(matter_id, title="t")
    m1 = store.add_message(c.id, MessageRole.USER, "hi", "hi")
    m2 = store.add_message(c.id, MessageRole.ASSISTANT, "Org1 here", "Acme here")
    msgs = store.list_messages(c.id)
    assert [m.id for m in msgs] == [m1.id, m2.id]
    assert msgs[1].redacted_text == "Org1 here"
    assert msgs[1].display_text == "Acme here"


def test_deleting_conversation_cascades_to_messages(store: Store, matter_id: str):
    c = store.create_conversation(matter_id, title="t")
    store.add_message(c.id, MessageRole.USER, "hi", "hi")
    store.delete_conversation(c.id)
    assert store.list_messages(c.id) == []
