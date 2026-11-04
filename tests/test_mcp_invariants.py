"""Cross-cutting invariants of the plugin: static coaching, no placeholders,
a complete en/fr table, and no canary anywhere the model can read."""

from __future__ import annotations

import json
import re
import uuid

import anyio
import pytest

from jude.mcp.strings import (
    INSTRUCTIONS,
    LANGS,
    MODEL_KEYS,
    STRINGS,
    TOOL_DESCRIPTIONS,
    TOOL_NAMES,
)
from jude.types import EntityType

CANARY_MATTER = "CANARY-MATTER-9f1e"
CANARY_FILE = "CANARY-FILE-77ab.txt"
CANARY_NAME = "CANARY-NAME-3c4d"
CANARIES = (CANARY_MATTER, CANARY_FILE, CANARY_NAME)


def test_tool_descriptions_are_static_and_coach_the_model(tmp_path, stdio_harness_cls):
    async def main():
        async with stdio_harness_cls(tmp_path / "home") as h:
            tools = (await h.session.list_tools()).tools
            return {t.name: t.description for t in tools}, h.init.instructions

    descriptions, instructions = anyio.run(main)
    assert descriptions == TOOL_DESCRIPTIONS
    assert set(descriptions) == set(TOOL_NAMES)
    assert "Takes no arguments" in descriptions["prepare_document"]
    assert "never ask the user which matter or which file" in descriptions["prepare_document"]
    assert "at most three times" in descriptions["fetch_approved"]
    assert "handed out once" in descriptions["fetch_approved"]
    assert instructions == INSTRUCTIONS
    assert "Approved" in instructions and "Never try to guess" in instructions
    assert "other_review_open" in instructions
    for text in (*descriptions.values(), instructions):
        assert "{" not in text and "}" not in text


def test_every_tool_result_scanned_for_canaries(tmp_path, stdio_harness_cls):
    pytest.importorskip("mcp")
    from tests.conftest import tool_result_dict, tool_result_text

    home = tmp_path / "home"
    document = (
        f"Memo about {CANARY_NAME}, who advises Thonnard SA. "
        f"{CANARY_NAME} signed on 3 March.\n"
    )

    async def main():
        outputs: list[str] = []
        async with stdio_harness_cls(home) as h:
            matter_id = h.seed(CANARY_MATTER, entity=(CANARY_NAME, EntityType.PERSON))
            for t in (await h.session.list_tools()).tools:
                outputs.append(json.dumps(t.model_dump(mode="json"), ensure_ascii=False))
            outputs.append(h.init.instructions or "")
            wrong = await h.call("prepare_document", {"matter": CANARY_MATTER})
            assert wrong.is_error
            outputs.append(tool_result_text(wrong))
            prepared = await h.call("prepare_document")
            outputs.append(tool_result_text(prepared))
            rid = tool_result_dict(prepared)["review_id"]
            already_open = await h.call("prepare_document")
            outputs.append(tool_result_text(already_open))
            assert set(tool_result_dict(already_open)) <= {"status", "next"}
            outputs.append(tool_result_text(
                await h.call("fetch_approved", {"review_id": rid, "wait_seconds": 5})
            ))
            client = h.window_client()
            h.drive_to_approved(client, rid, matter_id, suffix=".txt", text=document)
            released = await h.call("fetch_approved", {"review_id": rid, "wait_seconds": 5})
            outputs.append(tool_result_text(released))
            body = tool_result_dict(released)
            assert body["status"] == "released" and "Person1" in body["text"]
            outputs.append(tool_result_text(
                await h.call("show_answer", {"review_id": rid, "text": "Person1 advises Org1."})
            ))
            outputs.append(tool_result_text(
                await h.call("fetch_approved", {"review_id": rid, "wait_seconds": 5})
            ))
            outputs.append(tool_result_text(
                await h.call("fetch_approved", {"review_id": str(uuid.uuid4()), "wait_seconds": 5})
            ))
            outputs.append(tool_result_text(
                await h.call("show_answer", {"review_id": str(uuid.uuid4()), "text": "x"})
            ))
            outputs.append(tool_result_text(
                await h.call("show_answer", {"review_id": rid, "text": CANARY_NAME})
            ))
            return outputs, h

    outputs, h = anyio.run(main)
    for i, out in enumerate(outputs):
        for canary in CANARIES:
            assert canary not in out, (i, canary, out[:200])
    err = h.stderr()
    for canary in CANARIES:
        assert canary not in err, canary
    assert not re.search(r"\.txt\b", err)


def test_static_error_catalogue_has_no_placeholders():
    assert len(MODEL_KEYS) >= 12
    assert sorted(k for k in MODEL_KEYS if k.startswith("err.")) == [
        "err.busy", "err.internal_tool", "err.not_released", "err.refused",
        "err.too_long_answer", "err.unknown_argument", "err.unknown_review",
    ]
    assert len([k for k in MODEL_KEYS if k.startswith("next.")]) == 7
    for key in MODEL_KEYS:
        for lang in ("en", "fr"):
            text = STRINGS[key][lang]
            assert text
            assert "{" not in text and "}" not in text
            assert "%s" not in text and "%(" not in text
    assert set(TOOL_NAMES) == set(TOOL_DESCRIPTIONS)


def test_strings_table_complete_en_fr():
    assert LANGS == ("en", "fr", "nl")
    for key, entry in STRINGS.items():
        assert entry["en"].strip(), key
        assert entry["fr"].strip(), key
        assert "nl" in entry, key
        assert set(entry) == {"en", "fr", "nl"}, key
    for key in (
        "ui.status.handed_once", "ui.ledger_ref", "ui.zr_tag", "ui.after_approve",
        "ui.approved_window", "ui.withdraw", "ui.too_late", "ui.closed_withdrawn",
        "ui.error.component_missing", "ui.missing.command", "ui.phase.detecting",
        "ui.warn.comments", "ui.risk.lead", "ui.invisible_chars", "ui.expires_in",
    ):
        assert key in STRINGS, key
    assert "ui.approved_nudge" not in STRINGS and "ui.approved_detail" not in STRINGS
