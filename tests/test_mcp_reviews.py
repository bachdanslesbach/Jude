"""ReviewManager: the state machine behind the Claude Desktop plugin.

No HTTP, no MCP protocol, no models: detection is faked (``FakePipeline``
finds "Thonnard SA" and "Marie-Claire Lefèvre"), the clock is fake, the
store is a temporary SQLite file.
"""

from __future__ import annotations

import io
import json
import threading
import time
import uuid
import zipfile
from pathlib import Path

import pytest

from jude.mcp.reviews import (
    MAX_TEXT_CHARS,
    PRE_APPROVAL,
    AlreadyReleased,
    AnswerTooLong,
    AttestationRequired,
    BadUpload,
    IllegalTransition,
    NotReleased,
    RateLimited,
    ReleaseRefused,
    ReviewManager,
    ReviewStatus,
    TextChanged,
    UnknownEntity,
    effective_mode,
    sha256_hex,
)
from jude.store import Store
from jude.types import EntityType, Matter, Mode

ORG = "Thonnard SA"
PERSON = "Marie-Claire Lefèvre"
TEXT = (
    f"Re: {ORG} — note to file\n\n"
    f"Our client {ORG} met {PERSON} on 3 March. "
    f"{PERSON} confirmed that {ORG} will file by Friday. Friday is firm.\n"
)


def _prepare(mgr: ReviewManager, matter_id: str, text: str = TEXT, suffix: str = ".txt") -> str:
    outcome = mgr.create()
    if outcome.already_open:  # a previous review of this test is still open: close it
        mgr.cancel(outcome.review.id)
        outcome = mgr.create()
    rid = outcome.review.id
    mgr.choose_matter(rid, matter_id)
    mgr.attach_file(rid, suffix, text.encode("utf-8"))
    status = mgr.wait_prepared(rid, timeout=20)
    assert status == ReviewStatus.AWAITING_REVIEW, (status, mgr.get(rid).error_key)
    return rid


def _approve(mgr: ReviewManager, rid: str, **kw) -> str:
    rendering = mgr.render(rid)
    mgr.approve(rid, rendering.sha256, attest=True, **kw)
    return rendering.sha256


def _row(mgr: ReviewManager, rid: str, canonical: str):
    return next(e for e in mgr.render(rid).entities if e.canonical == canonical)


def _approvals(store: Store) -> int:
    return int(store._conn.execute("SELECT COUNT(*) FROM approvals").fetchone()[0])


def _outcome(store: Store, approval_id: int) -> str | None:
    row = store._conn.execute(
        "SELECT outcome FROM approvals WHERE id = ?", (approval_id,)
    ).fetchone()
    return row["outcome"]


def _audit_actions(store: Store, matter_id: str) -> list[str]:
    rows = store._conn.execute(
        "SELECT action FROM audit_log WHERE matter_id = ? ORDER BY id", (matter_id,)
    ).fetchall()
    return [r["action"] for r in rows]


def _audit_rows(store: Store, matter_id: str) -> list[tuple[str, str]]:
    rows = store._conn.execute(
        "SELECT action, detail FROM audit_log WHERE matter_id = ? ORDER BY id", (matter_id,)
    ).fetchall()
    return [(r["action"], r["detail"] or "") for r in rows]


def _provisional_ids(store: Store) -> list[int]:
    rows = store._conn.execute(
        "SELECT id FROM entities WHERE provisional_review_id IS NOT NULL ORDER BY id"
    ).fetchall()
    return [int(r["id"]) for r in rows]


def _manager(store, clock, tmp_path, monkeypatch, factory, **kw) -> ReviewManager:
    monkeypatch.setenv("JUDE_HOME", str(tmp_path / "home"))
    kw.setdefault("idle_ttl", 60)
    kw.setdefault("approved_hold", 120)
    kw.setdefault("open_browser", lambda url: True)
    return ReviewManager(store, pipeline_factory=factory, now=clock.now, **kw)


class _Gate:
    """A pipeline whose detect() blocks until the test opens the gate."""

    def __init__(self, inner):
        self.inner = inner
        self.gate = threading.Event()
        self.entered = threading.Event()

    def detect(self, text):
        self.entered.set()
        assert self.gate.wait(10)
        return self.inner.detect(text)

    def language_report(self):
        return self.inner.language_report()


# ----- creation and the window -----


def test_create_returns_existing_pre_approval_review(mcp_manager):
    first = mcp_manager.create()
    second = mcp_manager.create()
    assert first.already_open is False and first.browser_opened is True
    assert second.review.id == first.review.id
    assert second.already_open is True
    assert len(mcp_manager.test_opens) == 1  # within 15 s the tab is assumed to be there


def test_create_reopens_window_when_tab_not_polling(mcp_manager, clock):
    first = mcp_manager.create()
    clock.advance(16)  # past the browser-open rate limit; nobody ever polled
    second = mcp_manager.create()
    assert second.already_open and second.review.id == first.review.id
    assert second.browser_opened is True
    assert len(mcp_manager.test_opens) == 2


def test_create_does_not_reopen_when_tab_polls_the_review(mcp_manager, clock):
    first = mcp_manager.create()
    clock.advance(16)
    mcp_manager.window_state(first.review.id)  # the tab is polling
    second = mcp_manager.create()
    assert second.already_open and second.browser_opened is False
    assert len(mcp_manager.test_opens) == 1


def test_create_skips_browser_when_tab_polled_current(mcp_manager, clock):
    rid = mcp_manager.create().review.id
    mcp_manager.cancel(rid)
    clock.advance(16)
    mcp_manager.current()  # a tab on the closed review polls /api/current
    outcome = mcp_manager.create()
    assert outcome.already_open is False and outcome.browser_opened is True
    assert len(mcp_manager.test_opens) == 1  # the tab reloads itself


def test_current_reports_live_review(mcp_manager):
    assert mcp_manager.current() == {"review_id": None, "status": None}
    rid = mcp_manager.create().review.id
    assert mcp_manager.current() == {"review_id": rid, "status": "awaiting_matter"}


def test_create_reports_approved_uncollected_as_open(mcp_manager, matter_id, clock):
    """An approved text Claude has not collected is still the lawyer's open
    business (Withdraw lives on its screen): a second conversation gets
    already_open, not a new review that would displace it."""

    rid = _prepare(mcp_manager, matter_id)
    _approve(mcp_manager, rid)
    clock.advance(16)
    outcome = mcp_manager.create()
    assert outcome.already_open and outcome.review.id == rid
    assert outcome.browser_opened is True  # nobody polled: the window is brought back
    assert mcp_manager.current_review_id() == rid
    assert mcp_manager.get(rid).status == ReviewStatus.APPROVED
    mcp_manager.release(rid)
    outcome = mcp_manager.create()
    assert outcome.already_open is False and outcome.review.id != rid



def test_browser_open_rate_limited(mcp_manager, clock):
    rid = mcp_manager.create().review.id
    mcp_manager.cancel(rid)
    rid = mcp_manager.create().review.id
    assert len(mcp_manager.test_opens) == 1  # within 15 s: the tab is assumed open
    mcp_manager.cancel(rid)
    clock.advance(16)
    mcp_manager.create()
    assert len(mcp_manager.test_opens) == 2


def test_matters_for_window_sorted_by_last_used_and_never_in_public_status(mcp_manager, store):
    a = store.create_matter("Alpha matter")
    b = store.create_matter("Bravo matter")
    store.create_entity(b.id, "Someone", EntityType.PERSON)  # touches b's audit log last
    rows = mcp_manager.matters_for_window()
    assert rows[0].id == b.id
    assert {r.id for r in rows} >= {a.id, b.id}
    rid = mcp_manager.create().review.id
    mcp_manager.choose_matter(rid, b.id)
    status = mcp_manager.public_status(rid)
    assert set(status) <= {"review_id", "status", "next"}
    assert "Bravo" not in json.dumps(status) and "Alpha" not in json.dumps(status)


def test_matter_rows_attested_only_for_claude_desktop(mcp_manager, store):
    other = store.create_matter("zr elsewhere", mode=Mode.SMART, zero_retention_attested=True)
    here = store.create_matter(
        "zr here", mode=Mode.SMART, llm_endpoint="claude-desktop", zero_retention_attested=True
    )
    rows = {r.id: r for r in mcp_manager.matters_for_window()}
    assert rows[other.id].attested is False and rows[here.id].attested is True
    assert "zr here" not in repr(rows[here.id])  # names never in a repr


# ----- matter and mode -----


def test_choose_matter_and_change(mcp_manager, store, matter_id):
    other = store.create_matter("other")
    rid = mcp_manager.create().review.id
    mcp_manager.choose_matter(rid, matter_id)
    assert mcp_manager.get(rid).status == ReviewStatus.AWAITING_FILE
    mcp_manager.choose_matter(rid, other.id)
    r = mcp_manager.get(rid)
    assert r.status == ReviewStatus.AWAITING_FILE and r.matter_id == other.id


def test_smart_mode_without_attestation_falls_back_to_strict(mcp_manager, store):
    m = store.create_matter("smart, not attested", mode=Mode.SMART)
    rid = mcp_manager.create().review.id
    mcp_manager.choose_matter(rid, m.id)
    r = mcp_manager.get(rid)
    assert r.mode == Mode.STRICT and r.mode_notice == "smart_fallback"
    mcp_manager.attach_file(rid, ".txt", TEXT.encode())
    assert mcp_manager.wait_prepared(rid) == ReviewStatus.AWAITING_REVIEW
    assert "Org1" in mcp_manager.render(rid).text


def test_attested_other_endpoint_falls_back_to_strict(mcp_manager, store):
    m = store.create_matter(
        "smart, attested for anthropic", mode=Mode.SMART, llm_endpoint="anthropic",
        zero_retention_attested=True,
    )
    rid = mcp_manager.create().review.id
    mcp_manager.choose_matter(rid, m.id)
    r = mcp_manager.get(rid)
    assert r.mode == Mode.STRICT and r.mode_notice == "smart_fallback"
    assert effective_mode(Matter(id="x", name="n", mode=Mode.STRICT)) == (Mode.STRICT, None)


def test_smart_mode_uses_offline_provider_only(mcp_manager, smart_matter_id, monkeypatch):
    import jude.context_wikipedia as cw

    def boom(self, *a, **k):
        raise AssertionError("Wikipedia provider must never be built by the plugin")

    monkeypatch.setattr(cw.WikipediaContextProvider, "__init__", boom)
    rid = mcp_manager.create().review.id
    mcp_manager.choose_matter(rid, smart_matter_id)
    assert mcp_manager.get(rid).mode == Mode.SMART
    mcp_manager.attach_file(rid, ".txt", TEXT.encode())
    assert mcp_manager.wait_prepared(rid) == ReviewStatus.AWAITING_REVIEW


def test_approval_records_zero_retention_only_in_smart(
    mcp_manager, store, matter_id, smart_matter_id
):
    rid = _prepare(mcp_manager, matter_id)
    _approve(mcp_manager, rid)
    assert store.get_approval(mcp_manager.get(rid).approval_id).zero_retention is False
    rid2 = _prepare(mcp_manager, smart_matter_id)
    _approve(mcp_manager, rid2)
    row = store.get_approval(mcp_manager.get(rid2).approval_id)
    assert row.zero_retention is True and row.mode == "smart"
    other = store.create_matter(
        "smart, attested for anthropic", mode=Mode.SMART, llm_endpoint="anthropic",
        zero_retention_attested=True,
    )
    rid3 = _prepare(mcp_manager, other.id)
    _approve(mcp_manager, rid3)
    row = store.get_approval(mcp_manager.get(rid3).approval_id)
    assert row.zero_retention is False and row.mode == "strict"  # the raw flag is never copied


# ----- the state machine -----


def test_state_machine_happy_path(
    store, matter_id, clock, fake_pipeline_cls, tmp_path, monkeypatch
):
    gate = _Gate(fake_pipeline_cls())
    mgr = _manager(store, clock, tmp_path, monkeypatch, lambda s, m, c: gate)
    try:
        rid = mgr.create().review.id
        assert mgr.get(rid).status == ReviewStatus.AWAITING_MATTER
        mgr.choose_matter(rid, matter_id)
        assert mgr.get(rid).status == ReviewStatus.AWAITING_FILE
        mgr.attach_file(rid, ".txt", TEXT.encode())
        assert gate.entered.wait(5)
        assert mgr.get(rid).status == ReviewStatus.PREPARING
        gate.gate.set()
        assert mgr.wait_prepared(rid) == ReviewStatus.AWAITING_REVIEW
        _approve(mgr, rid)
        assert mgr.get(rid).status == ReviewStatus.APPROVED
        text = mgr.release(rid)
        assert mgr.get(rid).status == ReviewStatus.RELEASED
        assert ORG not in text and "Org1" in text and "Person1" in text
    finally:
        mgr.close(grace=1.0)


def test_illegal_transitions(mcp_manager, matter_id):
    rid = mcp_manager.create().review.id
    mcp_manager.choose_matter(rid, matter_id)
    with pytest.raises(IllegalTransition):
        mcp_manager.approve(rid, "x", attest=True)
    assert mcp_manager.get(rid).status == ReviewStatus.AWAITING_FILE
    with pytest.raises(NotReleased):
        mcp_manager.release(rid)
    mcp_manager.attach_file(rid, ".txt", TEXT.encode())
    with pytest.raises(IllegalTransition):
        mcp_manager.attach_file(rid, ".txt", TEXT.encode())
    assert mcp_manager.wait_prepared(rid) == ReviewStatus.AWAITING_REVIEW
    with pytest.raises(IllegalTransition):
        mcp_manager.attach_file(rid, ".txt", TEXT.encode())
    with pytest.raises(IllegalTransition):
        mcp_manager.choose_matter(rid, matter_id)
    with pytest.raises(NotReleased):
        mcp_manager.release(rid)
    assert mcp_manager.get(rid).status == ReviewStatus.AWAITING_REVIEW


def test_phase_sequence_recorded(store, matter_id, clock, fake_pipeline_cls, tmp_path, monkeypatch):
    gate = _Gate(fake_pipeline_cls())
    mgr = _manager(store, clock, tmp_path, monkeypatch, lambda s, m, c: gate)
    try:
        rid = mgr.create().review.id
        mgr.choose_matter(rid, matter_id)
        mgr.attach_file(rid, ".txt", TEXT.encode())
        assert gate.entered.wait(5)
        r = mgr.get(rid)
        assert r.phase == "detecting"
        assert mgr.window_state(rid)["phase"] == "detecting"
        gate.gate.set()
        assert mgr.wait_prepared(rid) == ReviewStatus.AWAITING_REVIEW
        r = mgr.get(rid)
        assert r.phase is None
        assert r.phase_history == ["reading", "loading_models", "detecting", "rendering"]
    finally:
        mgr.close(grace=1.0)


# ----- clocks: the TTL is the lawyer's -----


def test_idle_ttl_resets_on_touch_and_decide(mcp_manager, matter_id, clock):
    rid = mcp_manager.create().review.id
    clock.advance(50)
    mcp_manager.touch(rid)
    clock.advance(50)
    assert mcp_manager.status_of(rid) == ReviewStatus.AWAITING_MATTER
    clock.advance(61)
    assert mcp_manager.status_of(rid) == ReviewStatus.EXPIRED

    rid = _prepare(mcp_manager, matter_id)
    clock.advance(50)
    mcp_manager.decide_keep(rid, _row(mcp_manager, rid, ORG).entity_id)
    clock.advance(50)
    assert mcp_manager.status_of(rid) == ReviewStatus.AWAITING_REVIEW
    # A poll of the page never extends the clock; a heartbeat does.
    clock.advance(50)
    mcp_manager.window_state(rid)
    clock.advance(11)
    assert mcp_manager.status_of(rid) == ReviewStatus.EXPIRED
    rid = mcp_manager.create().review.id
    clock.advance(50)
    mcp_manager.heartbeat(rid)
    clock.advance(50)
    assert mcp_manager.status_of(rid) == ReviewStatus.AWAITING_MATTER


def test_idle_ttl_counts_interactions_not_polls(mcp_manager, clock):
    rid = mcp_manager.create().review.id
    for _ in range(6):
        clock.advance(10)
        mcp_manager.window_state(rid)  # polling every 10 s for a minute
    assert mcp_manager.status_of(rid) == ReviewStatus.EXPIRED


def test_expires_in_reported(mcp_manager, clock):
    rid = mcp_manager.create().review.id
    assert mcp_manager.window_state(rid)["expires_in"] == 60
    clock.advance(20)
    assert mcp_manager.window_state(rid)["expires_in"] == 40
    assert mcp_manager.heartbeat(rid)["expires_in"] == 60


def test_max_age_caps_idle_resets(
    store, matter_id, clock, fake_pipeline_cls, tmp_path, monkeypatch
):
    mgr = _manager(
        store, clock, tmp_path, monkeypatch, lambda s, m, c: fake_pipeline_cls(), max_age=150
    )
    try:
        rid = mgr.create().review.id
        for step in (50, 50, 45):
            clock.advance(step)
            mgr.touch(rid)
        assert mgr.status_of(rid) == ReviewStatus.AWAITING_MATTER  # t = 145, idle would allow 205
        clock.advance(6)  # t = 151 > max_age
        assert mgr.status_of(rid) == ReviewStatus.EXPIRED
    finally:
        mgr.close(grace=1.0)


def test_preparing_refreshes_activity(mcp_manager, matter_id, clock):
    rid = mcp_manager.create().review.id
    mcp_manager.choose_matter(rid, matter_id)
    clock.advance(55)
    mcp_manager.attach_file(rid, ".txt", TEXT.encode())
    assert mcp_manager.wait_prepared(rid) == ReviewStatus.AWAITING_REVIEW
    clock.advance(55)
    assert mcp_manager.status_of(rid) == ReviewStatus.AWAITING_REVIEW


def test_approved_hold_is_fixed_grace(mcp_manager, matter_id, store, clock):
    rid = _prepare(mcp_manager, matter_id)
    _approve(mcp_manager, rid)
    assert mcp_manager.window_state(rid)["expires_in"] == 120
    clock.advance(100)
    mcp_manager.heartbeat(rid)  # the lawyer is in the chat, not in the tab: no extension
    assert mcp_manager.window_state(rid)["expires_in"] == 20
    clock.advance(21)
    assert mcp_manager.status_of(rid) == ReviewStatus.EXPIRED


def test_approved_hold_independent_of_window(mcp_manager, matter_id, store, clock):
    rid = _prepare(mcp_manager, matter_id)
    _approve(mcp_manager, rid)
    n_entities = len(store.list_entities(matter_id))
    approval_id = mcp_manager.get(rid).approval_id
    clock.advance(119)
    mcp_manager.sweep()
    assert mcp_manager.status_of(rid) == ReviewStatus.APPROVED
    clock.advance(2)
    mcp_manager.sweep()
    assert mcp_manager.status_of(rid) == ReviewStatus.EXPIRED
    assert len(store.list_entities(matter_id)) == n_entities
    assert store.get_approval(approval_id) is not None


def test_approved_expiry_marks_ledger_outcome(mcp_manager, matter_id, store, clock):
    rid = _prepare(mcp_manager, matter_id)
    _approve(mcp_manager, rid)
    approval_id = mcp_manager.get(rid).approval_id
    clock.advance(121)
    mcp_manager.sweep()
    assert _outcome(store, approval_id) == "expired"
    assert mcp_manager.get(rid).outcome == "expired"
    assert "mcp.approved.expired" in _audit_actions(store, matter_id)
    with pytest.raises(NotReleased):
        mcp_manager.release(rid)


# ----- approve and release -----


def test_approve_requires_matching_sha(mcp_manager, matter_id, store):
    rid = _prepare(mcp_manager, matter_id)
    with pytest.raises(TextChanged):
        mcp_manager.approve(rid, "0" * 64, attest=True)
    with pytest.raises(TextChanged):
        mcp_manager.approve(rid, "0" * 64, attest=False)
    with pytest.raises(AttestationRequired):
        mcp_manager.approve(rid, mcp_manager.render(rid).sha256, attest=False)
    assert mcp_manager.get(rid).status == ReviewStatus.AWAITING_REVIEW
    assert _approvals(store) == 0


def test_approve_two_tabs_race(mcp_manager, matter_id):
    rid = _prepare(mcp_manager, matter_id)
    tab_b_sha = mcp_manager.render(rid).sha256
    mcp_manager.decide_keep(rid, _row(mcp_manager, rid, ORG).entity_id)  # tab A
    with pytest.raises(TextChanged):
        mcp_manager.approve(rid, tab_b_sha, attest=True)
    mcp_manager.approve(rid, mcp_manager.render(rid).sha256, attest=True)
    assert mcp_manager.get(rid).status == ReviewStatus.APPROVED


def test_approval_record_and_prune_in_one_transaction(mcp_manager, matter_id, store, monkeypatch):
    rid = _prepare(mcp_manager, matter_id)
    org = _row(mcp_manager, rid, ORG)
    mcp_manager.decide_keep(rid, org.entity_id)  # a deletion will be part of the transaction

    def failing_log(self, matter_id, action, detail=None):
        raise RuntimeError("audit insert failed")

    monkeypatch.setattr(Store, "_log", failing_log)
    with pytest.raises(RuntimeError):
        mcp_manager.approve(rid, mcp_manager.render(rid).sha256, attest=True)
    assert _approvals(store) == 0
    assert any(e.id == org.entity_id for e in store.list_entities(matter_id, review_id=rid))
    assert _provisional_ids(store)  # nothing was confirmed either
    assert mcp_manager.get(rid).status == ReviewStatus.AWAITING_REVIEW


def test_approval_record_written_before_status_flips(mcp_manager, matter_id, store, monkeypatch):
    rid = _prepare(mcp_manager, matter_id)
    seen: list[tuple[str, int]] = []
    original = Store.record_approval

    def spy(self, **kwargs):
        approval_id = original(self, **kwargs)
        seen.append((mcp_manager.get(rid).status.value, _approvals(self)))
        return approval_id

    monkeypatch.setattr(Store, "record_approval", spy)
    _approve(mcp_manager, rid)
    assert seen == [("awaiting_review", 1)]
    assert mcp_manager.get(rid).status == ReviewStatus.APPROVED


def test_sha256_matches_displayed_text_and_record(mcp_manager, matter_id, store):
    rid = _prepare(mcp_manager, matter_id)
    rendering = mcp_manager.render(rid)
    assert rendering.sha256 == sha256_hex(rendering.text)
    sha = _approve(mcp_manager, rid)
    row = store.get_approval(mcp_manager.get(rid).approval_id)
    assert row is not None and row.payload_sha256 == sha
    text = mcp_manager.release(rid)
    assert sha256_hex(text) == sha
    assert store.get_approval(row.id).verified_at_send == 1


def test_text_read_attestation_recorded(mcp_manager, matter_id, store):
    rid = _prepare(mcp_manager, matter_id)
    _approve(mcp_manager, rid)
    assert store.get_approval(mcp_manager.get(rid).approval_id).attestation == (
        "items_reviewed_text_opened"
    )
    rid = _prepare(mcp_manager, matter_id)
    _approve(mcp_manager, rid, text_read=True)
    row = store.get_approval(mcp_manager.get(rid).approval_id)
    assert row.attestation == "items_reviewed_text_read" and mcp_manager.get(rid).text_read


def test_release_single_shot(mcp_manager, matter_id):
    rid = _prepare(mcp_manager, matter_id)
    _approve(mcp_manager, rid)
    assert "Org1" in mcp_manager.release(rid)
    with pytest.raises(AlreadyReleased):
        mcp_manager.release(rid)
    status = mcp_manager.public_status(rid)
    assert "text" not in status and status["status"] == "released"


def test_release_sets_outcome_released(mcp_manager, matter_id, store):
    rid = _prepare(mcp_manager, matter_id)
    _approve(mcp_manager, rid)
    approval_id = mcp_manager.get(rid).approval_id
    assert _outcome(store, approval_id) is None
    mcp_manager.release(rid)
    assert _outcome(store, approval_id) == "released"
    assert mcp_manager.get(rid).outcome == "released"
    assert store.get_approval(approval_id).released_at is not None


def test_release_refused_on_tampered_text(mcp_manager, matter_id, store):
    rid = _prepare(mcp_manager, matter_id)
    _approve(mcp_manager, rid)
    review = mcp_manager.get(rid)
    review.frozen_text = review.frozen_text + " tampered"
    with pytest.raises(ReleaseRefused):
        mcp_manager.release(rid)
    assert review.status == ReviewStatus.FAILED and review.error_key == "refused"
    assert store.get_approval(review.approval_id).verified_at_send == 0
    assert "mcp.release.refused" in _audit_actions(store, matter_id)


def test_refused_sets_outcome_refused(mcp_manager, matter_id, store):
    rid = _prepare(mcp_manager, matter_id)
    _approve(mcp_manager, rid)
    review = mcp_manager.get(rid)
    review.frozen_text = "not the approved text"
    with pytest.raises(ReleaseRefused):
        mcp_manager.release(rid)
    assert _outcome(store, review.approval_id) == "refused" and review.outcome == "refused"


# ----- withdraw: serialised with release -----


def test_withdraw_after_approve_wins_until_release(mcp_manager, matter_id, store):
    rid = _prepare(mcp_manager, matter_id)
    _approve(mcp_manager, rid)
    approval_id = mcp_manager.get(rid).approval_id
    n_entities = len(store.list_entities(matter_id))
    r = mcp_manager.cancel(rid)
    assert r.status == ReviewStatus.CANCELLED and r.outcome == "withdrawn"
    with pytest.raises(NotReleased):
        mcp_manager.release(rid)
    assert _outcome(store, approval_id) == "withdrawn"
    assert "mcp.approved.withdrawn" in _audit_actions(store, matter_id)
    assert len(store.list_entities(matter_id)) == n_entities  # approved entities stay
    assert r.frozen_text is None


def test_withdraw_after_release_is_noop(mcp_manager, matter_id, store):
    rid = _prepare(mcp_manager, matter_id)
    _approve(mcp_manager, rid)
    approval_id = mcp_manager.get(rid).approval_id
    mcp_manager.release(rid)
    r = mcp_manager.cancel(rid)
    assert r.status == ReviewStatus.RELEASED and r.outcome == "released"
    assert _outcome(store, approval_id) == "released"
    assert "mcp.approved.withdrawn" not in _audit_actions(store, matter_id)


# ----- decisions -----


def test_keep_new_entity_deleted_at_approve_only(mcp_manager, matter_id, store):
    rid = _prepare(mcp_manager, matter_id)
    org = _row(mcp_manager, rid, ORG)
    assert org.is_new
    rendering = mcp_manager.decide_keep(rid, org.entity_id)
    assert ORG in rendering.text and "Org1" not in rendering.text
    assert any(e.id == org.entity_id for e in store.list_entities(matter_id, review_id=rid))
    _approve(mcp_manager, rid)
    assert not any(e.id == org.entity_id for e in store.list_entities(matter_id))
    assert ORG in mcp_manager.release(rid)


def test_keep_known_entity_is_one_turn(mcp_manager, matter_id, store):
    known = store.create_entity(matter_id, ORG, EntityType.ORG)
    rid = _prepare(mcp_manager, matter_id)
    org = _row(mcp_manager, rid, ORG)
    assert org.entity_id == known.id and not org.is_new
    mcp_manager.decide_keep(rid, org.entity_id)
    _approve(mcp_manager, rid)
    assert any(e.id == known.id for e in store.list_entities(matter_id))


def test_keep_unknown_entity_id_404(mcp_manager, matter_id):
    rid = _prepare(mcp_manager, matter_id)
    with pytest.raises(UnknownEntity):
        mcp_manager.decide_keep(rid, 99_999)


def test_mark_adds_user_detections_without_detector_rerun(
    store, matter_id, clock, fake_pipeline_cls, tmp_path, monkeypatch
):
    pipe = fake_pipeline_cls()
    mgr = _manager(store, clock, tmp_path, monkeypatch, lambda s, m, c: pipe)
    try:
        rid = _prepare(mgr, matter_id)
        assert pipe.calls == 2
        rendering = mgr.mark(rid, "Friday", "OTHER")
        assert pipe.calls == 2
        assert "Friday" not in rendering.text
        assert rendering.text.count("X1") == 2
        row = next(e for e in rendering.entities if e.canonical == "Friday")
        assert row.user_marked and row.is_new
        assert row.entity_id in _provisional_ids(store)  # provisional until approval
    finally:
        mgr.close(grace=1.0)


def test_reapply_never_runs_detector(
    store, matter_id, clock, fake_pipeline_cls, tmp_path, monkeypatch
):
    pipe = fake_pipeline_cls()
    mgr = _manager(store, clock, tmp_path, monkeypatch, lambda s, m, c: pipe)
    try:
        rid = _prepare(mgr, matter_id)
        org = _row(mgr, rid, ORG).entity_id
        person = _row(mgr, rid, PERSON).entity_id
        mgr.decide_keep(rid, org)
        mgr.decide_keep(rid, person)
        mgr.decide_hide(rid, org)
        mgr.mark(rid, "Friday", "OTHER")
        assert pipe.calls == 2
    finally:
        mgr.close(grace=1.0)


# ----- pruning, provisional entities, recovery -----


def test_cancel_prunes_created_entities_keeps_preexisting(mcp_manager, matter_id, store):
    known = store.create_entity(matter_id, PERSON, EntityType.PERSON)
    rid = _prepare(mcp_manager, matter_id)
    assert len(store.list_entities(matter_id, review_id=rid)) == 2
    mcp_manager.cancel(rid)
    remaining = store.list_entities(matter_id)
    assert [e.id for e in remaining] == [known.id]
    assert mcp_manager.get(rid).status == ReviewStatus.CANCELLED


def test_cancel_removes_surface_forms_added_to_preexisting_entities(store, matter_id, clock,
                                                                   fake_pipeline_cls, tmp_path,
                                                                   monkeypatch):
    class ShortForm(fake_pipeline_cls):
        surfaces = ((ORG, EntityType.ORG), ("Lefèvre", EntityType.PERSON))

    known = store.create_entity(matter_id, PERSON, EntityType.PERSON)  # the full name is known
    before = set(store.list_entities(matter_id)[0].surface_forms)
    mgr = _manager(store, clock, tmp_path, monkeypatch, lambda s, m, c: ShortForm())
    try:
        rid = _prepare(mgr, matter_id, text=f"Our client {ORG} met Lefèvre on 3 March.\n")
        during = next(e for e in store.list_entities(matter_id) if e.id == known.id).surface_forms
        assert "Lefèvre" in during  # the short form resolved to the known entity by alias
        assert (known.id, "Lefèvre") in mgr.get(rid).added_surface_forms
        assert "Person1" in mgr.render(rid).text  # same pseudonym, no new entity
        mgr.cancel(rid)
        after = next(e for e in store.list_entities(matter_id) if e.id == known.id).surface_forms
        assert set(after) == before
        detail = dict(_audit_rows(store, matter_id))["mcp.cancel"]
        assert json.loads(detail)["forms_removed"] == 1
    finally:
        mgr.close(grace=1.0)


def test_cancelled_review_leaves_no_audit_names(mcp_manager, matter_id, store):
    rid = _prepare(mcp_manager, matter_id)
    mcp_manager.cancel(rid)
    rows = _audit_rows(store, matter_id)
    assert not any(a == "entity.create" for a, _ in rows)
    assert all(ORG not in d and PERSON not in d for _, d in rows)
    rid = _prepare(mcp_manager, matter_id)
    assert not any(a == "entity.create" for a, _ in _audit_rows(store, matter_id))
    _approve(mcp_manager, rid)
    confirms = [json.loads(d) for a, d in _audit_rows(store, matter_id) if a == "entity.confirm"]
    assert {c["canonical"] for c in confirms} == {ORG, PERSON}
    assert all(c["review_id"] == rid for c in confirms)
    assert _provisional_ids(store) == []


def test_restart_prunes_provisional_entities(store, matter_id):
    kept = store.create_entity(matter_id, "Kept Co", EntityType.ORG)
    store.create_entity(matter_id, "Half Done", EntityType.PERSON, provisional_review_id="r-1")
    store.create_entity(matter_id, "Half Two", EntityType.PERSON, provisional_review_id="r-1")
    lost = store.record_approval(
        review_id="r-2", matter_id=matter_id, payload_sha256="0" * 64, chars=1,
        endpoint="claude-desktop", endpoint_host="stdio:", mode="strict", zero_retention=False,
        n_hidden=0, n_kept=0, n_user_marked=0, attestation="items_reviewed_text_opened",
        approver_os_user="t", ui_lang=None,
    )
    done = store.record_approval(
        review_id="r-3", matter_id=matter_id, payload_sha256="1" * 64, chars=1,
        endpoint="claude-desktop", endpoint_host="stdio:", mode="strict", zero_retention=False,
        n_hidden=0, n_kept=0, n_user_marked=0, attestation="items_reviewed_text_opened",
        approver_os_user="t", ui_lang=None,
    )
    store.set_approval_verified(done, True)
    report = store.recover_after_restart()
    assert report == {"pruned": 2, "approvals_lost": 1, "matters": 1}
    assert [e.id for e in store.list_entities(matter_id)] == [kept.id]
    assert _outcome(store, lost) == "lost_on_restart" and _outcome(store, done) == "released"
    recover = [json.loads(d) for a, d in _audit_rows(store, matter_id) if a == "mcp.recover"]
    assert recover == [{"pruned": 2, "approvals_lost": 1}]
    assert store.recover_after_restart() == {"pruned": 0, "approvals_lost": 0, "matters": 0}


def test_expire_prunes(mcp_manager, matter_id, store, clock):
    rid = _prepare(mcp_manager, matter_id)
    assert len(store.list_entities(matter_id, review_id=rid)) == 2
    clock.advance(61)
    mcp_manager.sweep()
    assert mcp_manager.get(rid).status == ReviewStatus.EXPIRED
    assert store.list_entities(matter_id) == []


def test_failure_prunes(store, matter_id, clock, fake_pipeline_cls, tmp_path, monkeypatch):
    class SecondCallFails(fake_pipeline_cls):
        def detect(self, text):
            out = super().detect(text)
            if self.calls == 2:
                raise RuntimeError("detector crashed CANARY-NAME-3c4d")
            return out

    mgr = _manager(store, clock, tmp_path, monkeypatch, lambda s, m, c: SecondCallFails())
    try:
        rid = mgr.create().review.id
        mgr.choose_matter(rid, matter_id)
        mgr.attach_file(rid, ".txt", TEXT.encode())
        assert mgr.wait_prepared(rid) == ReviewStatus.FAILED
        r = mgr.get(rid)
        assert r.error_key == "internal"
        assert store.list_entities(matter_id) == []
        assert "CANARY" not in repr(vars(r))
    finally:
        mgr.close(grace=1.0)


def test_cancel_during_preparing_discards_worker_result(store, matter_id, clock, fake_pipeline_cls,
                                                        tmp_path, monkeypatch):
    gate = _Gate(fake_pipeline_cls())
    mgr = _manager(store, clock, tmp_path, monkeypatch, lambda s, m, c: gate)
    try:
        rid = mgr.create().review.id
        mgr.choose_matter(rid, matter_id)
        mgr.attach_file(rid, ".txt", TEXT.encode())
        assert gate.entered.wait(5)
        mgr.cancel(rid)
        assert mgr.get(rid).status == ReviewStatus.CANCELLED
        gate.gate.set()
        mgr.wait_prepared(rid)
        assert mgr.get(rid).status == ReviewStatus.CANCELLED
        assert mgr.get(rid).rendering is None
        assert store.list_entities(matter_id) == []
    finally:
        mgr.close(grace=1.0)


def test_cancel_during_preparing_returns_immediately(store, matter_id, clock, fake_pipeline_cls,
                                                     tmp_path, monkeypatch):
    gate = _Gate(fake_pipeline_cls())
    mgr = _manager(store, clock, tmp_path, monkeypatch, lambda s, m, c: gate)
    try:
        rid = mgr.create().review.id
        mgr.choose_matter(rid, matter_id)
        mgr.attach_file(rid, ".txt", TEXT.encode())
        assert gate.entered.wait(5)
        t0 = time.monotonic()
        mgr.cancel(rid)
        assert time.monotonic() - t0 < 1.0
        gate.gate.set()
        mgr.wait_prepared(rid)
    finally:
        mgr.close(grace=1.0)


# ----- locks: detection never holds the store -----


def test_release_not_blocked_by_other_review_detection(store, matter_id, clock, fake_pipeline_cls,
                                                        tmp_path, monkeypatch):
    other = store.create_matter("second matter")
    pipes = {matter_id: fake_pipeline_cls(), other.id: _Gate(fake_pipeline_cls())}
    mgr = _manager(store, clock, tmp_path, monkeypatch, lambda s, m, c: pipes[m])
    try:
        a = _prepare(mgr, matter_id)
        _approve(mgr, a)
        # create() refuses a second review while A is approved and not
        # collected (by design); the lock property is what is tested here,
        # so B is registered directly.
        from jude.mcp.reviews import Review

        b = str(uuid.uuid4())
        mgr._reviews[b] = Review(
            id=b, status=ReviewStatus.AWAITING_MATTER, created_at=clock.now(),
            last_interaction=clock.now(),
        )
        mgr.choose_matter(b, other.id)
        mgr.attach_file(b, ".txt", TEXT.encode())
        assert pipes[other.id].entered.wait(5)
        t0 = time.monotonic()
        text = mgr.release(a)
        assert time.monotonic() - t0 < 1.0 and "Org1" in text
        pipes[other.id].gate.set()
        assert mgr.wait_prepared(b) == ReviewStatus.AWAITING_REVIEW
    finally:
        mgr.close(grace=1.0)


def test_pipeline_built_outside_db_lock(store, matter_id, clock, fake_pipeline_cls, tmp_path,
                                        monkeypatch):
    seen: list[bool] = []
    holder: dict[str, ReviewManager] = {}

    def factory(s, m, c):
        free = holder["mgr"]._db.acquire(blocking=False)
        seen.append(free)
        if free:
            holder["mgr"]._db.release()
        return fake_pipeline_cls()

    mgr = _manager(store, clock, tmp_path, monkeypatch, factory)
    holder["mgr"] = mgr
    try:
        _prepare(mgr, matter_id)
        assert seen == [True]
    finally:
        mgr.close(grace=1.0)


def test_prune_with_no_ids_writes_nothing(mcp_manager, matter_id, store):
    before = len(_audit_rows(store, matter_id))
    assert mcp_manager._prune(matter_id, [], []) == (0, 0)
    assert len(_audit_rows(store, matter_id)) == before
    rid = mcp_manager.create().review.id
    mcp_manager.choose_matter(rid, matter_id)
    mcp_manager.cancel(rid)  # a cancel is always logged, even with nothing to prune
    rows = _audit_rows(store, matter_id)
    assert rows[-1][0] == "mcp.cancel" and json.loads(rows[-1][1])["pruned"] == 0


def test_flush_prunes_requeues_when_db_busy(mcp_manager, matter_id, store, clock):
    rid = _prepare(mcp_manager, matter_id)
    assert len(store.list_entities(matter_id, review_id=rid)) == 2
    clock.advance(61)
    held = threading.Event()
    release = threading.Event()

    def hold():
        with mcp_manager._db:
            held.set()
            release.wait(5)

    t = threading.Thread(target=hold)
    t.start()
    assert held.wait(5)
    t0 = time.monotonic()
    mcp_manager.sweep()
    assert time.monotonic() - t0 < 1.5
    assert mcp_manager.get(rid).status == ReviewStatus.EXPIRED
    assert len(store.list_entities(matter_id, review_id=rid)) == 2  # the prune waits
    release.set()
    t.join()
    mcp_manager.sweep()
    assert store.list_entities(matter_id) == []


def test_provisional_entities_scoped_to_their_review(mcp_manager, matter_id, store):
    """The entities an open review created are visible to that review alone.
    A second Store connection (``jude redact``, the Streamlit UI) neither
    sees them nor resolves a surface to their pseudonym, so a cancel or a
    restart can never destroy a mapping another front-end relied on."""

    from jude.detect.dictionary_detector import DictionaryDetector
    from jude.redact import redact
    from jude.rehydrate import rehydrate
    from tests.conftest import FakePipeline

    rid = _prepare(mcp_manager, matter_id)
    assert len(_provisional_ids(store)) == 2
    assert "Org1" in mcp_manager.render(rid).text
    other = Store(store.db_path)  # the CLI or the UI, on the same jude.db
    try:
        assert other.list_entities(matter_id) == []
        assert other.find_entity_by_surface(matter_id, ORG) is None
        assert other.find_entity_by_surface_or_alias(
            matter_id, "Lefèvre", EntityType.PERSON
        ) is None
        assert other.find_entity_by_pseudonym(matter_id, "Org1") is None
        assert DictionaryDetector(other, matter_id).detect(TEXT) == []
        # The review itself does see its rows (second pass, decide, mark).
        assert len(store.list_entities(matter_id, review_id=rid)) == 2
        assert store.find_entity_by_surface(matter_id, ORG, review_id=rid) is not None
        assert DictionaryDetector(store, matter_id, review_id=rid).detect(TEXT)
        # A concurrent CLI redaction gets its own, confirmed entities and
        # pseudonyms (the counter is shared, so no collision either).
        result = redact(TEXT, FakePipeline().detect(TEXT), other, matter_id)
        assert "Org1" not in result.redacted_text and "Org2" in result.redacted_text
        assert "Person2" in result.redacted_text
        assert len(result.created_entity_ids) == 2
        mcp_manager.cancel(rid)  # the plugin review dies: its rows go, the CLI's stay
        assert _provisional_ids(store) == []
        assert rehydrate(result.redacted_text, other, matter_id) == TEXT
        assert len(other.list_entities(matter_id)) == 2
    finally:
        other.close()


def test_attach_file_write_failure_leaves_review_retryable(mcp_manager, matter_id, monkeypatch):
    """A temp-file write error (ENOSPC, EACCES) surfaces to the caller and
    leaves the review awaiting_file — never 'preparing' with no worker."""

    import errno

    rid = mcp_manager.create().review.id
    mcp_manager.choose_matter(rid, matter_id)

    def boom(data, suffix):
        raise OSError(errno.ENOSPC, "No space left on device")

    # A scoped patch: ``monkeypatch.undo()`` would also undo the fixture's
    # JUDE_HOME and send the retry's temp copy under the real ~/.jude.
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(mcp_manager, "_write_temp", boom)
        with pytest.raises(OSError):
            mcp_manager.attach_file(rid, ".txt", TEXT.encode())
    r = mcp_manager.get(rid)
    assert r.status == ReviewStatus.AWAITING_FILE and r.future is None and r.phase is None
    mcp_manager.attach_file(rid, ".txt", TEXT.encode())  # the retry works
    assert mcp_manager.wait_prepared(rid) == ReviewStatus.AWAITING_REVIEW


def test_attach_file_after_shutdown_fails_closed(store, matter_id, clock, fake_pipeline_cls,
                                                 tmp_path, monkeypatch):
    mgr = _manager(store, clock, tmp_path, monkeypatch, lambda s, m, c: fake_pipeline_cls())
    rid = mgr.create().review.id
    mgr.choose_matter(rid, matter_id)
    mgr.close(grace=0.1)  # the executor is shut down: no worker will ever run
    with pytest.raises(IllegalTransition):
        mgr.attach_file(rid, ".txt", TEXT.encode())
    r = mgr.get(rid)
    assert r.status == ReviewStatus.FAILED and r.error_key == "internal"
    assert "mcp.fail" in _audit_actions(store, matter_id)
    tmp_root = tmp_path / "home" / "mcp" / "tmp"
    assert not tmp_root.exists() or list(tmp_root.glob("r-*")) == []  # the copy is gone


def test_base_exception_in_detector_fails_review(store, matter_id, clock, fake_pipeline_cls,
                                                 tmp_path, monkeypatch):
    """A library that calls sys.exit must not leave the review 'preparing'
    with its phase frozen until expiry."""

    class Exits(fake_pipeline_cls):
        def detect(self, text):
            out = super().detect(text)
            if self.calls == 2:
                raise SystemExit(3)  # the first pass persisted provisional entities
            return out

    mgr = _manager(store, clock, tmp_path, monkeypatch, lambda s, m, c: Exits())
    try:
        rid = mgr.create().review.id
        mgr.choose_matter(rid, matter_id)
        mgr.attach_file(rid, ".txt", TEXT.encode())
        assert mgr.wait_prepared(rid, timeout=20) == ReviewStatus.FAILED
        r = mgr.get(rid)
        assert r.error_key == "internal" and r.phase is None
        assert _provisional_ids(store) == [] and store.list_entities(matter_id) == []
    finally:
        mgr.close(grace=1.0)  # must not re-raise the SystemExit


def test_approve_store_read_failure_leaves_no_orphan_record(mcp_manager, matter_id, store,
                                                            monkeypatch):
    """Every store read of approve() happens before the ledger commit: a
    locked database cannot leave an approvals row without a status flip,
    and the lawyer's retry writes exactly one row."""

    import sqlite3

    rid = _prepare(mcp_manager, matter_id)
    original = Store.list_entities
    calls: list[int] = []

    def locked_once(self, matter_id, *, review_id=None):
        calls.append(1)
        if len(calls) == 1:
            raise sqlite3.OperationalError("database is locked")
        return original(self, matter_id, review_id=review_id)

    monkeypatch.setattr(Store, "list_entities", locked_once)
    with pytest.raises(sqlite3.OperationalError):
        _approve(mcp_manager, rid)
    assert _approvals(store) == 0
    assert mcp_manager.get(rid).status == ReviewStatus.AWAITING_REVIEW
    assert _provisional_ids(store)  # nothing confirmed or deleted either
    _approve(mcp_manager, rid)
    assert _approvals(store) == 1 and mcp_manager.get(rid).status == ReviewStatus.APPROVED
    assert len(mcp_manager.get(rid).released_entities) == 2


def test_release_audit_failure_keeps_text_and_retries(mcp_manager, matter_id, store, monkeypatch):
    """The verification and the mcp.release line are one transaction written
    before the state flips: when it fails the review stays approved with
    its text, the ledger says nothing, and the next fetch retries."""

    import sqlite3

    rid = _prepare(mcp_manager, matter_id)
    _approve(mcp_manager, rid)
    approval_id = mcp_manager.get(rid).approval_id
    original = Store.set_approval_verified
    calls: list[int] = []

    def locked_once(self, approval_id, verified, *, audit=None):
        calls.append(1)
        if len(calls) == 1:
            raise sqlite3.OperationalError("database is locked")
        return original(self, approval_id, verified, audit=audit)

    monkeypatch.setattr(Store, "set_approval_verified", locked_once)
    with pytest.raises(sqlite3.OperationalError):
        mcp_manager.release(rid)
    r = mcp_manager.get(rid)
    assert r.status == ReviewStatus.APPROVED and r.frozen_text and r.outcome is None
    assert _outcome(store, approval_id) is None
    assert "mcp.release" not in _audit_actions(store, matter_id)
    text = mcp_manager.release(rid)
    assert "Org1" in text and r.status == ReviewStatus.RELEASED
    assert _outcome(store, approval_id) == "released"
    assert _audit_actions(store, matter_id).count("mcp.release") == 1
    # A refusal is likewise one transaction: row and audit line together.
    rid2 = _prepare(mcp_manager, matter_id)
    _approve(mcp_manager, rid2)
    mcp_manager.get(rid2).frozen_text = "tampered"
    with pytest.raises(ReleaseRefused):
        mcp_manager.release(rid2)
    assert _outcome(store, mcp_manager.get(rid2).approval_id) == "refused"
    assert "mcp.release.refused" in _audit_actions(store, matter_id)


# ----- failures that must stay opaque -----


def test_models_missing_key_for_spacy_and_gliner(store, matter_id, clock, tmp_path, monkeypatch):
    import jude.detect.spacy_detector as sd
    import jude.mcp.models as models_mod

    monkeypatch.setattr(sd, "_resolve_model_for_language", lambda lang, overrides: None)
    monkeypatch.setattr(models_mod, "gliner_package_missing", lambda: False)
    monkeypatch.setattr(models_mod, "gliner_cached", lambda model: False)
    monkeypatch.setenv("JUDE_MCP_LANGS", "en,fr,nl")
    monkeypatch.setenv("JUDE_HOME", str(tmp_path / "home"))
    mgr = ReviewManager(store, idle_ttl=60, now=clock.now, open_browser=lambda url: True)
    try:
        rid = mgr.create().review.id
        mgr.choose_matter(rid, matter_id)
        mgr.attach_file(rid, ".txt", TEXT.encode())
        assert mgr.wait_prepared(rid) == ReviewStatus.FAILED
        r = mgr.get(rid)
        assert r.error_key == "models_missing"
        assert r.missing == ("spacy_en", "spacy_fr", "spacy_nl", "gliner")
        assert mgr.window_state(rid)["missing"] == list(r.missing)
    finally:
        mgr.close(grace=1.0)

    def gliner_factory(s, m, c):
        # What GlinerDetector.__init__ raises when the weights are not cached offline.
        raise OSError("CANARY-WEIGHTS /Users/someone/.cache/huggingface not found")

    mgr = _manager(store, clock, tmp_path, monkeypatch, gliner_factory)
    try:
        rid = mgr.create().review.id
        mgr.choose_matter(rid, matter_id)
        mgr.attach_file(rid, ".txt", TEXT.encode())
        assert mgr.wait_prepared(rid) == ReviewStatus.FAILED
        r = mgr.get(rid)
        assert r.error_key == "models_missing"
        assert "CANARY" not in repr(vars(r)) and "/Users" not in repr(vars(r))
    finally:
        mgr.close(grace=1.0)


def test_models_missing_lists_components(monkeypatch):
    import jude.detect.spacy_detector as sd
    import jude.mcp.models as models_mod
    from jude.mcp.reviews import ModelsMissing, check_models

    monkeypatch.setattr(
        sd, "_resolve_model_for_language", lambda lang, o: None if lang == "nl" else "x"
    )
    monkeypatch.setattr(models_mod, "gliner_package_missing", lambda: True)
    with pytest.raises(ModelsMissing) as info:
        check_models(("en", "fr", "nl"))
    assert info.value.missing == ("spacy_nl", "gliner_package")
    monkeypatch.setattr(models_mod, "gliner_package_missing", lambda: False)
    monkeypatch.setattr(models_mod, "gliner_cached", lambda model: True)
    monkeypatch.setattr(sd, "_resolve_model_for_language", lambda lang, o: "x")
    check_models(("en", "fr", "nl"))  # nothing missing: no exception


def test_too_long_text_fails_closed(mcp_manager, matter_id):
    assert MAX_TEXT_CHARS == 150_000
    rid = mcp_manager.create().review.id
    mcp_manager.choose_matter(rid, matter_id)
    mcp_manager.attach_file(rid, ".txt", ("a" * 150_001).encode())
    assert mcp_manager.wait_prepared(rid) == ReviewStatus.FAILED
    assert mcp_manager.get(rid).error_key == "too_long"
    assert mcp_manager.get(rid).rendering is None


def test_no_text(mcp_manager, matter_id):
    rid = mcp_manager.create().review.id
    mcp_manager.choose_matter(rid, matter_id)
    mcp_manager.attach_file(rid, ".txt", b"  \n\t ")
    assert mcp_manager.wait_prepared(rid) == ReviewStatus.FAILED
    assert mcp_manager.get(rid).error_key == "no_text"


def test_unsupported_suffix(mcp_manager, matter_id):
    rid = mcp_manager.create().review.id
    mcp_manager.choose_matter(rid, matter_id)
    with pytest.raises(BadUpload) as info:
        mcp_manager.attach_file(rid, ".exe", b"MZ")
    assert info.value.key == "unsupported_suffix"
    assert mcp_manager.get(rid).status == ReviewStatus.AWAITING_FILE


def test_oversize(mcp_manager, matter_id):
    rid = mcp_manager.create().review.id
    mcp_manager.choose_matter(rid, matter_id)
    with pytest.raises(BadUpload) as info:
        mcp_manager.attach_file(rid, ".txt", bytes(50 * 1024 * 1024 + 1))
    assert info.value.key == "oversize"
    assert mcp_manager.get(rid).status == ReviewStatus.AWAITING_FILE


def test_component_missing_for_import_error(store, matter_id, clock, fake_pipeline_cls, tmp_path,
                                            monkeypatch):
    import jude.mcp.reviews as reviews

    def no_reader(path):
        raise ImportError("No module named 'pymupdf'")

    monkeypatch.setattr(reviews, "_read_text", no_reader)
    mgr = _manager(store, clock, tmp_path, monkeypatch, lambda s, m, c: fake_pipeline_cls())
    try:
        rid = mgr.create().review.id
        mgr.choose_matter(rid, matter_id)
        mgr.attach_file(rid, ".pdf", b"%PDF-1.4")
        assert mgr.wait_prepared(rid) == ReviewStatus.FAILED
        r = mgr.get(rid)
        assert r.error_key == "component_missing" and r.missing == ("pdf",)
    finally:
        mgr.close(grace=1.0)


def test_temp_file_removed_before_detection(store, matter_id, clock, fake_pipeline_cls, tmp_path,
                                            monkeypatch):
    tmp_root = tmp_path / "home" / "mcp" / "tmp"
    observed: list[list[str]] = []

    class Spy(fake_pipeline_cls):
        def detect(self, text):
            observed.append([p.name for p in tmp_root.iterdir()] if tmp_root.exists() else [])
            return super().detect(text)

    mgr = _manager(store, clock, tmp_path, monkeypatch, lambda s, m, c: Spy(), tmp_dir=tmp_root)
    try:
        _prepare(mgr, matter_id)
        assert observed == [[], []]
    finally:
        mgr.close(grace=1.0)


# ----- inputs: what the lawyer sees is what is hashed -----


def test_crlf_normalised_before_hash(mcp_manager, matter_id):
    rid = _prepare(mcp_manager, matter_id, text=TEXT.replace("\n", "\r\n"))
    rendering = mcp_manager.render(rid)
    assert "\r" not in rendering.text and mcp_manager.get(rid).raw_text == TEXT
    assert rendering.sha256 == sha256_hex(rendering.text)
    expected = TEXT.replace(ORG, "Org1").replace(PERSON, "Person1")
    assert rendering.text == expected  # what the browser shows is what is hashed
    rid2 = _prepare(mcp_manager, matter_id, text="one\rtwo\r\nthree\n")
    assert mcp_manager.get(rid2).raw_text == "one\ntwo\nthree\n"


def test_invisible_characters_flagged(mcp_manager, matter_id):
    text = f"Our client {ORG} said: pay​ now‮.\n"
    rid = _prepare(mcp_manager, matter_id, text=text)
    r = mcp_manager.get(rid)
    assert r.n_invisible == 2
    rendering = r.rendering
    labels = [label for _, label in rendering.invisible]
    assert labels == ["U+200B", "U+202E"]
    for offset, _ in rendering.invisible:
        assert rendering.text[offset] in ("​", "‮")
    rid2 = _prepare(mcp_manager, matter_id, text=TEXT)
    assert mcp_manager.get(rid2).n_invisible == 0 and mcp_manager.render(rid2).invisible == ()


def _minimal_docx(with_comment: bool) -> bytes:
    """A .docx built with zipfile: one paragraph, optionally a comment."""

    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p>"
        + ('<w:commentRangeStart w:id="0"/>' if with_comment else "")
        + f"<w:r><w:t>Our client {ORG} met {PERSON}.</w:t></w:r>"
        + ('<w:commentRangeEnd w:id="0"/><w:r><w:commentReference w:id="0"/></w:r>'
           if with_comment else "")
        + "</w:p></w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
        'relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
        'officedocument.wordprocessingml.document.main+xml"/>'
        + ('<Override PartName="/word/comments.xml" ContentType="application/vnd.openxmlformats-'
           'officedocument.wordprocessingml.comments+xml"/>' if with_comment else "")
        + "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        'relationships/officeDocument" Target="word/document.xml"/></Relationships>'
    )
    doc_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + ('<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
           'relationships/comments" Target="comments.xml"/>' if with_comment else "")
        + "</Relationships>"
    )
    comments = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:comment w:id="0" w:author="CANARY-AUTHOR"><w:p><w:r><w:t>secret note</w:t></w:r></w:p>'
        "</w:comment></w:comments>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", document)
        z.writestr("word/_rels/document.xml.rels", doc_rels)
        if with_comment:
            z.writestr("word/comments.xml", comments)
    return buf.getvalue()


def test_adapter_warnings_recorded(mcp_manager, matter_id):
    rid = mcp_manager.create().review.id
    mcp_manager.choose_matter(rid, matter_id)
    mcp_manager.attach_file(rid, ".docx", _minimal_docx(with_comment=True))
    status = mcp_manager.wait_prepared(rid)
    assert status == ReviewStatus.AWAITING_REVIEW, mcp_manager.get(rid).error_key
    r = mcp_manager.get(rid)
    assert "comments" in r.warnings
    assert "secret note" not in r.raw_text and "CANARY-AUTHOR" not in r.raw_text
    mcp_manager.cancel(rid)
    rid2 = mcp_manager.create().review.id
    mcp_manager.choose_matter(rid2, matter_id)
    mcp_manager.attach_file(rid2, ".docx", _minimal_docx(with_comment=False))
    assert mcp_manager.wait_prepared(rid2) == ReviewStatus.AWAITING_REVIEW
    assert "comments" not in mcp_manager.get(rid2).warnings


def test_image_only_pdf_reports_needs_ocr(mcp_manager, matter_id):
    pymupdf = pytest.importorskip("pymupdf")
    doc = pymupdf.open()
    doc.new_page()
    data = doc.tobytes()
    doc.close()
    rid = mcp_manager.create().review.id
    mcp_manager.choose_matter(rid, matter_id)
    mcp_manager.attach_file(rid, ".pdf", data)
    assert mcp_manager.wait_prepared(rid) == ReviewStatus.FAILED
    assert mcp_manager.get(rid).error_key == "needs_ocr"


def test_public_status_keys_whitelist(mcp_manager, matter_id, store, clock):
    allowed = {"review_id", "status", "next"}
    rid = mcp_manager.create().review.id
    assert set(mcp_manager.public_status(rid)) <= allowed  # awaiting_matter
    mcp_manager.choose_matter(rid, matter_id)
    assert set(mcp_manager.public_status(rid)) <= allowed  # awaiting_file
    mcp_manager.attach_file(rid, ".txt", TEXT.encode())
    assert set(mcp_manager.public_status(rid)) <= allowed  # preparing or later
    mcp_manager.wait_prepared(rid)
    assert set(mcp_manager.public_status(rid)) <= allowed  # awaiting_review
    _approve(mcp_manager, rid)
    assert set(mcp_manager.public_status(rid)) <= allowed  # approved
    mcp_manager.release(rid)
    assert set(mcp_manager.public_status(rid)) <= allowed  # released
    for closer in ("cancel", "expire", "fail"):
        rid = mcp_manager.create().review.id
        mcp_manager.choose_matter(rid, matter_id)
        if closer == "cancel":
            mcp_manager.cancel(rid)
        elif closer == "expire":
            clock.advance(61)
            mcp_manager.sweep()
        else:
            mcp_manager.attach_file(rid, ".txt", b" ")
            mcp_manager.wait_prepared(rid)
        assert mcp_manager.get(rid).status in (
            ReviewStatus.CANCELLED, ReviewStatus.EXPIRED, ReviewStatus.FAILED
        )
        assert set(mcp_manager.public_status(rid)) <= allowed
    assert all(r.status not in PRE_APPROVAL for r in mcp_manager.reviews())


# ----- rendering: risks, languages -----


def test_rendering_carries_risk_assessments(mcp_manager, matter_id):
    text = f"{ORG} paid EUR 1,250,000 on 13 October 2023 in Case T-123/21.\n\nUnrelated line.\n"
    rid = _prepare(mcp_manager, matter_id, text=text)
    rendering = mcp_manager.render(rid)
    assert rendering.risks and rendering.risks[0].pseudonym == "Org1"
    assert rendering.risks[0].score >= 3 and rendering.risks[0].reasons
    assert "risks" not in repr(rendering) and ORG not in repr(rendering)
    rid2 = _prepare(mcp_manager, matter_id, text=f"{ORG} wrote a short note.\n")
    assert mcp_manager.render(rid2).risks == ()


def test_language_report_recorded(
    store, matter_id, clock, fake_pipeline_cls, tmp_path, monkeypatch
):
    class Reporting(fake_pipeline_cls):
        def language_report(self):
            return {"fr": 5, "nl": 1, "und": 2}, ("de",)

    mgr = _manager(store, clock, tmp_path, monkeypatch, lambda s, m, c: Reporting())
    try:
        rid = _prepare(mgr, matter_id)
        r = mgr.get(rid)
        assert r.languages == {"fr": 5, "nl": 1, "und": 2} and r.unmodelled == ("de",)
    finally:
        mgr.close(grace=1.0)


def test_pipeline_rebuilt_when_codename_toggle_changes(store, matter_id, clock, fake_pipeline_cls,
                                                       tmp_path, monkeypatch):
    built: list[bool] = []

    def factory(s, m, c):
        built.append(c)
        return fake_pipeline_cls(redact_codenames=c)

    mgr = _manager(store, clock, tmp_path, monkeypatch, factory)
    try:
        _prepare(mgr, matter_id)
        _prepare(mgr, matter_id)
        assert built == [False]
        store.set_redact_codenames(matter_id, True)
        _prepare(mgr, matter_id)
        assert built == [False, True]
    finally:
        mgr.close(grace=1.0)


# ----- answers -----


def test_answer_show_requires_released_and_uses_released_entities_only(
    mcp_manager, matter_id, store
):
    rid = _prepare(mcp_manager, matter_id)
    with pytest.raises(NotReleased):
        mcp_manager.show_answer(rid, "Org1")
    _approve(mcp_manager, rid)
    mcp_manager.release(rid)
    later = store.create_entity(matter_id, "Acme Holdings", EntityType.ORG)  # Org2, after approval
    answer = mcp_manager.show_answer(
        rid, f"Org1 instructed Person1; {later.pseudonym} and Org9 did not."
    )
    assert ORG in answer.rehydrated and PERSON in answer.rehydrated
    assert "Acme" not in answer.rehydrated and later.pseudonym in answer.rehydrated
    assert {p for p, _, _ in answer.legend} == {"Org1", "Person1"}
    assert set(answer.unknown) == {later.pseudonym, "Org9"}
    assert ORG not in repr(answer)


def test_answer_too_long(mcp_manager, matter_id):
    rid = _prepare(mcp_manager, matter_id)
    _approve(mcp_manager, rid)
    mcp_manager.release(rid)
    with pytest.raises(AnswerTooLong):
        mcp_manager.show_answer(rid, "a" * 400_001)
    assert mcp_manager.get(rid).answers == []


def test_answer_rate_limit(mcp_manager, matter_id):
    rid = _prepare(mcp_manager, matter_id)
    _approve(mcp_manager, rid)
    mcp_manager.release(rid)
    for _ in range(20):
        mcp_manager.show_answer(rid, "Org1")
    with pytest.raises(RateLimited):
        mcp_manager.show_answer(rid, "Org1")


def test_answer_opens_browser_only_if_no_recent_poll(mcp_manager, matter_id, clock):
    rid = _prepare(mcp_manager, matter_id)
    _approve(mcp_manager, rid)
    mcp_manager.release(rid)
    clock.advance(20)  # past the browser-open rate limit
    mcp_manager.window_state(rid)  # the page is polling
    mcp_manager.show_answer(rid, "Org1")
    assert len(mcp_manager.test_opens) == 1
    clock.advance(20)  # nobody polled for 20 s
    mcp_manager.show_answer(rid, "Org1")
    assert len(mcp_manager.test_opens) == 2


def test_idle_unload_clears_pipelines(
    store, matter_id, clock, fake_pipeline_cls, tmp_path, monkeypatch
):
    mgr = _manager(
        store, clock, tmp_path, monkeypatch, lambda s, m, c: fake_pipeline_cls(),
        idle_ttl=600, unload_after=100,
    )
    try:
        _prepare(mgr, matter_id)
        assert mgr._pipelines
        clock.advance(99)
        mgr.sweep()
        assert mgr._pipelines
        clock.advance(2)
        mgr.sweep()
        assert not mgr._pipelines
    finally:
        mgr.close(grace=1.0)


def test_tmp_dir_is_private(mcp_manager, matter_id, tmp_path):
    _prepare(mcp_manager, matter_id)
    root = Path(tmp_path / "home" / "mcp" / "tmp")
    assert root.is_dir() and (root.stat().st_mode & 0o777) == 0o700
