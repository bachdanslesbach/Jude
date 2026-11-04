"""The real server process, driven by the MCP SDK client over stdio.

The detector is faked (``tests/mcp_fake_server.py``); the window is driven
over HTTP from the test through ``window-<pid>.json`` and the HMAC mint.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import signal
import sqlite3
import stat
import subprocess
import sys
import time
import uuid

import anyio
import pytest

from jude.mcp.strings import STRINGS
from jude.store import Store

pytest.importorskip("mcp")

ORG = "Thonnard SA"
CANARY_NAME = "CANARY-NAME-3c4d"
CANARY_FILE = "CANARY-FILE-77ab"


def _dict(result):
    from tests.conftest import tool_result_dict

    return tool_result_dict(result)


def _text(result) -> str:
    from tests.conftest import tool_result_text

    return tool_result_text(result)


def _rows(home, sql: str) -> list[sqlite3.Row]:
    conn = sqlite3.connect(home / "jude.db")
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def test_tools_list_is_exactly_three(tmp_path, stdio_harness_cls):
    async def main():
        async with stdio_harness_cls(tmp_path / "home") as h:
            tools = (await h.session.list_tools()).tools
            assert sorted(t.name for t in tools) == [
                "fetch_approved", "prepare_document", "show_answer",
            ]
            for t in tools:
                assert "matter" not in json.dumps(t.input_schema).lower()
                assert "path" not in json.dumps(t.input_schema).lower()
                assert t.output_schema is None  # unstructured: one text block, no duplicate
                assert t.input_schema.get("additionalProperties") is False, t.name

    anyio.run(main)


def test_prepare_document_returns_review_id_without_names_or_url(tmp_path, stdio_harness_cls):
    home = tmp_path / "home"

    async def main():
        async with stdio_harness_cls(home) as h:
            h.seed("Thonnard / Kestrel")
            first = _dict(await h.call("prepare_document"))
            assert uuid.UUID(first["review_id"]).version == 4
            assert first["status"] == "awaiting_matter"
            assert first["next"] == STRINGS["next.prepared"]["en"]
            dumped = json.dumps(first)
            assert "http://" not in dumped and "Thonnard" not in dumped and "Kestrel" not in dumped
            second = _dict(await h.call("prepare_document"))
            assert second["status"] == "other_review_open" and "review_id" not in second
            assert second["next"] == STRINGS["next.already_open"]["en"]
            opens = (home / "browser_opens.log").read_text().splitlines()
            assert len(opens) == 1 and opens[0].startswith("http://127.0.0.1:")

    anyio.run(main)


def test_already_open_does_not_return_review_id(tmp_path, stdio_harness_cls):
    async def main():
        async with stdio_harness_cls(tmp_path / "home") as h:
            first = _dict(await h.call("prepare_document"))
            result = await h.call("prepare_document")
            body = _dict(result)
            assert not result.is_error
            assert body == {
                "status": "other_review_open", "next": STRINGS["next.already_open"]["en"],
            }
            assert first["review_id"] not in _text(result)

    anyio.run(main)


def test_unknown_arguments_rejected_with_static_error(tmp_path, stdio_harness_cls):
    """A model that types a matter or a file name into a tool gets a static
    correction, never a silent success: no review is created, the value it
    typed is not echoed back, and the schema forbids extra keys."""

    home = tmp_path / "home"

    async def main():
        async with stdio_harness_cls(home) as h:
            h.seed("Thonnard / Kestrel")
            result = await h.call(
                "prepare_document", {"matter": "CANARY-MATTER-ARG", "file": "memo.docx"}
            )
            assert result.is_error
            message = _text(result)
            assert message.endswith(STRINGS["err.unknown_argument"]["en"])
            assert "CANARY" not in message and "memo" not in message
            client = h.window_client()
            assert client.get_json("/api/current")[1] == {"review_id": None, "status": None}
            # The rightful call still works, and the wrong one created nothing.
            first = _dict(await h.call("prepare_document"))
            assert first["status"] == "awaiting_matter"
            rid = first["review_id"]
            result = await h.call(
                "fetch_approved", {"review_id": rid, "wait_seconds": 5, "path": "x.docx"}
            )
            assert result.is_error and _text(result).endswith(
                STRINGS["err.unknown_argument"]["en"]
            )
            result = await h.call("show_answer", {"review_id": rid, "text": "x", "matter": "m"})
            assert result.is_error and _text(result).endswith(
                STRINGS["err.unknown_argument"]["en"]
            )
            assert client.get_json("/api/current")[1]["review_id"] == rid

    anyio.run(main)


def test_fetch_approved_before_approval_has_no_text_key_and_waits_at_least_5s(
    tmp_path, stdio_harness_cls
):
    async def main():
        async with stdio_harness_cls(tmp_path / "home") as h:
            rid = _dict(await h.call("prepare_document"))["review_id"]
            t0 = time.monotonic()
            result = await h.call("fetch_approved", {"review_id": rid, "wait_seconds": 0})
            elapsed = time.monotonic() - t0
            assert elapsed >= 5.0, elapsed
            body = _dict(result)
            assert "text" not in body and not result.is_error
            assert body["status"] == "awaiting_matter"
            assert body["next"] == STRINGS["next.not_yet"]["en"]

    anyio.run(main)


def test_fetch_approved_after_http_approval_returns_exact_text_once(tmp_path, stdio_harness_cls):
    home = tmp_path / "home"

    async def main():
        async with stdio_harness_cls(home) as h:
            matter_id = h.seed("Thonnard / Kestrel")
            rid = _dict(await h.call("prepare_document"))["review_id"]
            client = h.window_client()
            sha = h.drive_to_approved(client, rid, matter_id)
            result = _dict(await h.call("fetch_approved", {"review_id": rid, "wait_seconds": 5}))
            assert result["status"] == "released"
            text = result["text"]
            assert hashlib.sha256(text.encode("utf-8")).hexdigest() == result["sha256"] == sha
            assert ORG not in text and "Marie-Claire" not in text
            assert "Org1" in text and re.search(r"\bPerson\d\b", text)
            with Store(home / "jude.db") as s:
                row = s._conn.execute(
                    "SELECT payload_sha256, verified_at_send, outcome FROM approvals"
                ).fetchone()
            assert row["payload_sha256"] == sha and row["verified_at_send"] == 1
            assert row["outcome"] == "released"
            again = await h.call("fetch_approved", {"review_id": rid, "wait_seconds": 5})
            body = _dict(again)
            assert body["status"] == "released" and "text" not in body
            assert body["next"] == STRINGS["next.already_released"]["en"]

    anyio.run(main)


def test_fetch_approved_result_not_duplicated(tmp_path, stdio_harness_cls):
    async def main():
        async with stdio_harness_cls(tmp_path / "home") as h:
            matter_id = h.seed()
            rid = _dict(await h.call("prepare_document"))["review_id"]
            client = h.window_client()
            sha = h.drive_to_approved(client, rid, matter_id)
            result = await h.call("fetch_approved", {"review_id": rid, "wait_seconds": 5})
            assert result.structured_content is None
            assert len(result.content) == 1 and result.content[0].type == "text"
            block = result.content[0].text
            assert block.count(sha) == 1
            assert block.count("Org1") == json.loads(block)["text"].count("Org1")

    anyio.run(main)


def test_too_long_document_never_reaches_approval(tmp_path, stdio_harness_cls):
    async def main():
        async with stdio_harness_cls(tmp_path / "home") as h:
            matter_id = h.seed()
            rid = _dict(await h.call("prepare_document"))["review_id"]
            client = h.window_client()
            client.post_json(f"/api/r/{rid}/matter", {"matter_id": matter_id})
            status, _ = client.upload(rid, ".txt", ("a" * 150_001).encode())
            assert status == 200
            state = h.wait_for_status(client, rid, "failed")
            assert state["error_key"] == "too_long"
            fetched = _dict(await h.call("fetch_approved", {"review_id": rid, "wait_seconds": 5}))
            assert fetched["status"] == "failed" and "text" not in fetched
            page = client.page()
            assert STRINGS["ui.error.too_long"]["en"] in page

    anyio.run(main)


def test_fetch_after_cancel_is_neutral(tmp_path, stdio_harness_cls):
    async def main():
        async with stdio_harness_cls(tmp_path / "home") as h:
            h.seed()
            rid = _dict(await h.call("prepare_document"))["review_id"]
            client = h.window_client()
            status, obj = client.post_json(f"/api/r/{rid}/cancel", {})
            assert status == 200 and obj == {"status": "cancelled", "outcome": None}
            result = await h.call("fetch_approved", {"review_id": rid, "wait_seconds": 5})
            body = _dict(result)
            assert not result.is_error
            assert body == {
                "review_id": rid, "status": "cancelled", "next": STRINGS["next.final"]["en"],
            }

    anyio.run(main)


def test_unknown_review_static_error(tmp_path, stdio_harness_cls):
    async def main():
        async with stdio_harness_cls(tmp_path / "home") as h:
            bogus = str(uuid.uuid4())
            result = await h.call("fetch_approved", {"review_id": bogus, "wait_seconds": 5})
            assert result.is_error
            message = _text(result)
            assert message.endswith(STRINGS["err.unknown_review"]["en"])
            assert bogus not in message
            result = await h.call("show_answer", {"review_id": bogus, "text": "Org1"})
            assert result.is_error and bogus not in _text(result)
            assert _text(result).endswith(STRINGS["err.unknown_review"]["en"])

    anyio.run(main)


def test_show_answer_bound_to_review(tmp_path, stdio_harness_cls):
    async def main():
        async with stdio_harness_cls(tmp_path / "home") as h:
            matter_id = h.seed("Thonnard / Kestrel")
            rid = _dict(await h.call("prepare_document"))["review_id"]
            result = await h.call("show_answer", {"review_id": rid, "text": "Org1 is fine."})
            assert result.is_error and _text(result).endswith(STRINGS["err.not_released"]["en"])
            client = h.window_client()
            h.drive_to_approved(client, rid, matter_id)
            fetched = _dict(await h.call("fetch_approved", {"review_id": rid, "wait_seconds": 5}))
            assert fetched["status"] == "released"
            result = await h.call("show_answer", {"review_id": rid, "text": "Org1 is fine."})
            assert not result.is_error
            assert _dict(result) == {"status": "shown", "chars": len("Org1 is fine.")}
            assert ORG not in _text(result)
            status, _, body = client.request("GET", f"/api/r/{rid}/answers")
            assert status == 200 and ORG in body.decode("utf-8")

    anyio.run(main)


def test_stdio_wire_stays_clean_with_noisy_detector(tmp_path, stdio_harness_cls):
    home = tmp_path / "home"

    async def main():
        async with stdio_harness_cls(home, mode="noisy") as h:
            matter_id = h.seed()
            rid = _dict(await h.call("prepare_document"))["review_id"]
            client = h.window_client()
            h.drive_to_approved(client, rid, matter_id)
            fetched = _dict(await h.call("fetch_approved", {"review_id": rid, "wait_seconds": 5}))
            assert fetched["status"] == "released" and "Org1" in fetched["text"]
            await h.call("show_answer", {"review_id": rid, "text": "Org1."})
            assert (await h.session.list_tools()).tools
            return h

    h = anyio.run(main)
    assert h.errors == [], [repr(e) for e in h.errors]
    # fd 1 is diverted to fd 2, and fd 2 to the trace: the noise is in the trace,
    # not on the wire and not in Claude Desktop's log.
    trace = h.trace()
    assert "noise from a chatty library" in trace and "raw noise" in trace
    err = h.stderr()
    assert "noise from a chatty library" not in err and "raw noise" not in err


def test_fd1_is_claimed(tmp_path, stdio_harness_cls):
    async def main():
        async with stdio_harness_cls(tmp_path / "home", debug_fds=True) as h:
            value = _dict(await h.call("debug_fds"))
            if "result" in value and isinstance(value["result"], dict):
                value = value["result"]
            assert value["fd1_is_fd2"] is True

    anyio.run(main)


def test_fd2_points_at_trace_file(tmp_path, stdio_harness_cls):
    async def main():
        async with stdio_harness_cls(tmp_path / "home", debug_fds=True) as h:
            value = _dict(await h.call("debug_fds"))
            if "result" in value and isinstance(value["result"], dict):
                value = value["result"]
            assert value == {"fd1_is_fd2": True, "fd2_is_trace": True}

    anyio.run(main)


def test_netguard_installed_in_server_process(tmp_path, stdio_harness_cls):
    async def main():
        async with stdio_harness_cls(tmp_path / "home", debug_net=True) as h:
            value = _dict(await h.call("debug_net"))
            if "result" in value and isinstance(value["result"], dict):
                value = value["result"]
            assert value == {"gethostbyname": "NetworkRefused", "connect": "NetworkRefused"}

    anyio.run(main)


def test_stderr_has_no_confidential_content(tmp_path, stdio_harness_cls):
    home = tmp_path / "home"

    async def main():
        async with stdio_harness_cls(home, mode="raise_validation") as h:
            matter_id = h.seed("Thonnard / Kestrel")
            # 1. The detector raises a pydantic ValidationError carrying a canary.
            rid = _dict(await h.call("prepare_document"))["review_id"]
            client = h.window_client()
            client.post_json(f"/api/r/{rid}/matter", {"matter_id": matter_id})
            client.upload(rid, ".txt", f"Hello {CANARY_NAME} and {ORG}.".encode())
            state = h.wait_for_status(client, rid, "failed")
            assert state["error_key"] == "internal"
            # 2. The .docx adapter raises with the temp path in its message.
            rid = _dict(await h.call("prepare_document"))["review_id"]
            client.post_json(f"/api/r/{rid}/matter", {"matter_id": matter_id})
            client.upload(rid, ".docx", b"this is not a zip file " + os.urandom(64))
            state = h.wait_for_status(client, rid, "failed")
            assert state["error_key"] == "unreadable"
            fetched = _dict(await h.call("fetch_approved", {"review_id": rid, "wait_seconds": 5}))
            assert fetched["status"] == "failed" and "text" not in fetched
            return h

    h = anyio.run(main)
    err = h.stderr()
    for forbidden in (CANARY_NAME, CANARY_FILE, "/Users", "Thonnard", "Kestrel"):
        assert forbidden not in err, forbidden
    trace = home / "mcp" / "trace.log"
    content = trace.read_text(encoding="utf-8", errors="replace")
    assert content.startswith("# Jude MCP trace. May contain document text. Never share this file.")
    assert "Traceback" in content and "ValidationError" in content
    assert stat.S_IMODE(trace.stat().st_mode) == 0o600

    # 3. A library that warns, prints to sys.stderr, writes to fd 2 and writes
    #    to fd 2 from C: everything lands in the trace, nothing in stderr.
    home2 = tmp_path / "home2"

    async def noisy():
        async with stdio_harness_cls(home2, mode="noisy_stderr") as h:
            matter_id = h.seed("Thonnard / Kestrel")
            rid = _dict(await h.call("prepare_document"))["review_id"]
            client = h.window_client()
            h.drive_to_approved(client, rid, matter_id)
            fetched = _dict(await h.call("fetch_approved", {"review_id": rid, "wait_seconds": 5}))
            assert fetched["status"] == "released"
            if pytest.importorskip("pymupdf", reason="damaged-PDF check") is not None:
                rid2 = _dict(await h.call("prepare_document"))["review_id"]
                client.post_json(f"/api/r/{rid2}/matter", {"matter_id": matter_id})
                client.upload(rid2, ".pdf", b"%PDF-1.4 " + CANARY_NAME.encode() + os.urandom(64))
                h.wait_for_status(client, rid2, "failed")
            return h

    h2 = anyio.run(noisy)
    err2 = h2.stderr()
    assert CANARY_NAME not in err2 and "Thonnard" not in err2 and "/Users" not in err2
    trace2 = h2.trace()
    for channel in ("warned from a library", "written to sys.stderr", "written to fd 2",
                    "written from C"):
        assert f"{CANARY_NAME} {channel}" in trace2, channel


def test_tool_calls_return_under_budget(tmp_path, stdio_harness_cls):
    async def main():
        async with stdio_harness_cls(tmp_path / "home") as h:
            matter_id = h.seed()
            timings: dict[str, float] = {}

            async def timed(name, args=None):
                t0 = time.monotonic()
                result = await h.call(name, args)
                timings[name + str(len(timings))] = time.monotonic() - t0
                return result

            rid = _dict(await timed("prepare_document"))["review_id"]
            await timed("fetch_approved", {"review_id": rid, "wait_seconds": 5})
            await timed("show_answer", {"review_id": rid, "text": "x"})
            client = h.window_client()
            h.drive_to_approved(client, rid, matter_id)
            await timed("fetch_approved", {"review_id": rid, "wait_seconds": 5})
            await timed("show_answer", {"review_id": rid, "text": "Org1"})
            await timed("fetch_approved", {"review_id": str(uuid.uuid4()), "wait_seconds": 5})
            return timings

    timings = anyio.run(main)
    assert all(t < 8.0 for t in timings.values()), timings


def test_sigterm_exits_cleanly_and_removes_window_json(tmp_path, stdio_harness_cls):
    from jude.mcp.launch import pid_alive

    home = tmp_path / "home"

    async def main():
        async with stdio_harness_cls(home) as h:
            info = h.window_info()
            pid = int(info["pid"])
            path = home / "mcp" / f"window-{pid}.json"
            assert path.exists()
            os.kill(pid, signal.SIGTERM)
            deadline = time.time() + 15
            while pid_alive(pid) and time.time() < deadline:
                await anyio.sleep(0.05)
            assert not pid_alive(pid)
            assert not path.exists()
            return h

    h = anyio.run(main)
    assert "Traceback" not in h.stderr()


def test_sigterm_mid_preparation_recovers_on_restart(tmp_path, stdio_harness_cls):
    from jude.mcp.launch import pid_alive

    home = tmp_path / "home"

    async def first_run():
        async with stdio_harness_cls(home, mode="slow") as h:
            matter_id = h.seed()
            rid = _dict(await h.call("prepare_document"))["review_id"]
            client = h.window_client()
            client.post_json(f"/api/r/{rid}/matter", {"matter_id": matter_id})
            client.upload(rid, ".txt", h.TEXT.encode())
            # The first pass has persisted provisional entities; the second detect sleeps.
            deadline = time.time() + 15
            while time.time() < deadline:
                if _rows(home, "SELECT id FROM entities WHERE provisional_review_id IS NOT NULL"):
                    break
                time.sleep(0.05)
            else:
                raise AssertionError("no provisional entity appeared")
            assert client.state(rid)["status"] == "preparing"
            pid = int(h.window_info()["pid"])
            os.kill(pid, signal.SIGTERM)
            deadline = time.time() + 20
            while pid_alive(pid) and time.time() < deadline:
                await anyio.sleep(0.05)
            assert not pid_alive(pid)

    anyio.run(first_run)
    assert _rows(home, "SELECT id FROM entities WHERE provisional_review_id IS NOT NULL")

    async def second_run():
        async with stdio_harness_cls(home) as h:
            assert (await h.session.list_tools()).tools

    anyio.run(second_run)
    assert _rows(home, "SELECT id FROM entities WHERE provisional_review_id IS NOT NULL") == []
    actions = [r["action"] for r in _rows(home, "SELECT action FROM audit_log ORDER BY id")]
    assert "mcp.recover" in actions
    assert len(_rows(home, "SELECT id FROM entities")) == 1  # the seeded entity survives


def test_sigterm_exits_within_deadline_when_shutdown_wedges(tmp_path, stdio_harness_cls):
    """The watchdog: ``Window.stop`` is patched to block for ever (the fake's
    ``wedged_stop`` mode, STOP_DEADLINE lowered to 3 s). SIGTERM must still
    end the process, with one static line in the trace and on stderr and no
    traceback anywhere."""

    from jude.mcp.launch import pid_alive
    from jude.mcp.server import WATCHDOG_LINE

    home = tmp_path / "home"

    async def main():
        async with stdio_harness_cls(home, mode="wedged_stop") as h:
            assert (await h.session.list_tools()).tools
            pid = int(h.window_info()["pid"])
            t0 = time.monotonic()
            os.kill(pid, signal.SIGTERM)
            deadline = time.time() + 15
            while pid_alive(pid) and time.time() < deadline:
                await anyio.sleep(0.05)
            assert not pid_alive(pid)
            assert time.monotonic() - t0 < 12
            assert WATCHDOG_LINE.strip() in h.trace()
            assert "signal received" in h.trace()
            err = h.stderr()
            assert WATCHDOG_LINE.strip() in err
            assert "Traceback" not in err and "Traceback" not in h.trace()

    anyio.run(main)


def test_second_instance_exits(tmp_path, stdio_harness_cls):
    from jude.mcp.server import DUPLICATE_LINE
    from tests.conftest import FAKE_SERVER

    home = tmp_path / "home"

    async def main():
        async with stdio_harness_cls(home) as h:
            env = {**os.environ, **h.env}
            t0 = time.monotonic()
            proc = subprocess.run(
                [sys.executable, str(FAKE_SERVER)], env=env, stdin=subprocess.DEVNULL,
                capture_output=True, text=True, timeout=60,
            )
            assert proc.returncode == 0
            assert DUPLICATE_LINE.strip() in proc.stderr
            assert proc.stdout == ""
            assert time.monotonic() - t0 < 30
            assert len(list((home / "mcp").glob("window-*.json"))) == 1
            assert (await h.session.list_tools()).tools

    anyio.run(main)


def test_trace_rotates_and_has_header(tmp_path):
    from jude.mcp.logfilter import TRACE_HEADER, RotatingSecureFileHandler

    path = tmp_path / "trace.log"
    handler = RotatingSecureFileHandler(str(path))
    logger = logging.getLogger("jude.mcp.test_rotation")
    logger.propagate = False
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    try:
        line = "x" * 1000
        for _ in range(2300):  # > 2 MiB
            logger.info(line)
    finally:
        logger.removeHandler(handler)
        handler.close()
    assert (tmp_path / "trace.log.1").exists()
    for p in (path, tmp_path / "trace.log.1"):
        assert stat.S_IMODE(p.stat().st_mode) == 0o600
        assert p.read_text(encoding="utf-8").startswith(TRACE_HEADER)
        assert p.stat().st_size <= 2 * 1024 * 1024 + 2000
    assert not (tmp_path / "trace.log.4").exists()
