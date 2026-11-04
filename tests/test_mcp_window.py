"""The local review window over real HTTP on an ephemeral loopback port."""

from __future__ import annotations

import contextlib
import html
import http.client
import json
import re
import socket
import threading
import time
import uuid

import pytest

from jude.mcp.reviews import ReviewStatus
from jude.mcp.strings import STRINGS
from jude.mcp.window import Window
from jude.types import Mode

ORG = "Thonnard SA"
PERSON = "Marie-Claire Lefèvre"
TEXT = f"Our client {ORG} met {PERSON} on 3 March. {ORG} will file by Friday.\n"
CANARY_MATTER = "CANARY-MATTER-9f1e"
CANARY_FILE = "CANARY-FILE-77ab.txt"


@pytest.fixture
def window(mcp_manager, clock):
    w = Window(mcp_manager, now=clock.now, state_dir=None)
    w.start()
    mcp_manager.url_factory = w.mint_url
    yield w
    w.stop()


@pytest.fixture
def client(window, window_client_cls):
    return window_client_cls(window.port)


def _session(window, client) -> str:
    """Open a one-shot URL (the landing page yields the cookie and the
    per-origin secret), then load the page as the browser composes it."""

    status, _, _ = client.open(window.mint_url())
    assert status == 200
    return client.page()


def _review(mgr, matter_id, text: str = TEXT, suffix: str = ".txt") -> str:
    outcome = mgr.create()
    if outcome.already_open:
        mgr.cancel(outcome.review.id)
        outcome = mgr.create()
    rid = outcome.review.id
    mgr.choose_matter(rid, matter_id)
    mgr.attach_file(rid, suffix, text.encode("utf-8"))
    assert mgr.wait_prepared(rid, timeout=20) == ReviewStatus.AWAITING_REVIEW
    return rid


def _approved(mgr, matter_id) -> str:
    rid = _review(mgr, matter_id)
    mgr.approve(rid, mgr.render(rid).sha256, attest=True)
    return rid


def _released(mgr, matter_id) -> str:
    rid = _approved(mgr, matter_id)
    mgr.release(rid)
    return rid


def _s(key: str, lang: str = "en") -> str:
    """A UI string as it appears in the page (HTML-escaped)."""

    return html.escape(STRINGS[key][lang])


def _status_line(page: str) -> str:
    m = re.search(r'<span id="status-line"[^>]*>(.*?)</span>', page)
    assert m, "no status line"
    return m.group(1)


def _body(page: str) -> str:
    """The page without the inlined script (which carries the JS strings)."""

    return page.split("<script", 1)[0]


def _raw(port: int, request: bytes) -> bytes:
    s = socket.create_connection(("127.0.0.1", port), timeout=10)
    try:
        s.sendall(request)
        s.shutdown(socket.SHUT_WR)
        data = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
    finally:
        s.close()
    return data


# ----- one-shot URL and sessions -----


def test_one_shot_url_sets_cookie_and_redirects(window, client):
    """The one-shot URL answers a landing page: it sets the cookie, hands
    the per-origin secret to sessionStorage (scoped to this port, unlike
    the cookie) and replaces itself with a clean ``/``."""

    url = window.mint_url()
    assert "?" not in url and url.startswith(f"http://127.0.0.1:{window.port}/open/")
    status, headers, body = client.open(url)
    assert status == 200
    cookie = headers["set-cookie"]
    assert "jude_session=" in cookie and "HttpOnly" in cookie and "SameSite=Strict" in cookie
    assert client.cookie and client.csrf
    page = body.decode("utf-8")
    assert f'data-csrf="{client.csrf}"' in page
    assert 'sessionStorage.setItem("jude_csrf"' in page and 'location.replace("/")' in page
    assert "/open/" not in page and client.cookie not in page
    assert "<title>Jude</title>" in page
    _assert_secure(headers)
    # The secret never appears on the shell that GET / returns.
    shell = client.shell()
    assert client.csrf not in shell and "data-csrf" not in shell


def test_one_shot_consumed_once(window, client):
    url = window.mint_url()
    path = url.split(str(window.port), 1)[1]
    assert client.request("GET", path, with_cookie=False)[0] == 200
    status, _, body = client.request("GET", path, with_cookie=False)
    assert status == 404 and body == b""


def test_one_shot_expires_after_10_min(window, client, clock):
    url = window.mint_url()
    clock.advance(601)
    status, _, body = client.open(url)
    assert status == 404 and body == b"" and client.cookie is None


def test_head_does_not_consume_otp(window, client):
    url = window.mint_url()
    path = url.split(str(window.port), 1)[1]
    status, headers, body = client.request("HEAD", path, with_cookie=False)
    assert status == 405 and headers.get("allow") == "GET" and body == b""
    assert client.request("GET", path, with_cookie=False)[0] == 200  # still valid


def test_mint_short_ttl_for_terminal_fallback(window, client, clock):
    import hashlib
    import hmac as hm

    nonce = "cd" * 16
    mac = hm.new(window.local_secret.encode(), f"mint:{nonce}".encode(), hashlib.sha256).hexdigest()
    status, obj = client.post_json(
        "/api/mint", {"nonce": nonce, "mac": mac, "ttl": "short"}, with_csrf=False
    )
    assert status == 200
    clock.advance(121)
    assert client.open(obj["url"])[0] == 404  # two minutes, not ten


def test_invalid_otp_with_valid_cookie_redirects(window, client):
    _session(window, client)
    status, headers, _ = client.request("GET", "/open/not-a-real-token")
    assert status == 303 and headers["location"] == "/"


def test_no_cookie_404_everywhere(window, client):
    _session(window, client)
    rid = str(uuid.uuid4())
    routes = [
        "/", "/api/lang", "/api/ping", "/api/mint", "/api/current", "/open/x", "/favicon.ico",
        "/nope",
        *(f"/api/r/{rid}/{a}" for a in (
            "state", "fragment", "answers", "heartbeat", "matter", "file", "decide", "mark",
            "approve", "cancel",
        )),
    ]
    good = client.cookie
    assert good
    flipped = ("a" if good[0] != "a" else "b") + good[1:]
    for path in routes:
        for method in ("GET", "POST"):
            status, _, body = client.request(method, path, with_cookie=False, body=b"{}")
            assert (status, body) == (404, b""), (method, path, status)
            client.cookie = flipped
            status, _, body = client.request(method, path, body=b"{}")
            client.cookie = good
            assert (status, body) == (404, b""), (method, path, status, "flipped cookie")


# ----- host, fetch metadata, origin, CSRF, methods -----


def test_host_header_mismatch_400(window, client):
    _session(window, client)
    for host in (f"localhost:{window.port}", "evil.test", "127.0.0.1:1"):
        status, _, body = client.request("GET", "/", host=host)
        assert (status, body) == (400, b""), host


def test_origin_mismatch_403(window, client, mcp_manager, matter_id):
    _session(window, client)
    rid = _review(mcp_manager, matter_id)
    status, _, _ = client.request(
        "POST", f"/api/r/{rid}/cancel", body=b"{}",
        headers={"Content-Type": "application/json", "Origin": "http://evil.test"},
    )
    assert status == 403
    status, _, _ = client.request("GET", "/", headers={"Sec-Fetch-Site": "cross-site"})
    assert status == 403
    status, _, _ = client.request("GET", "/", headers={"Origin": window.origin})
    assert status == 200
    assert mcp_manager.get(rid).status == ReviewStatus.AWAITING_REVIEW


def test_same_site_other_port_403(window, client, mcp_manager, matter_id):
    """A page on 127.0.0.1:<other port> (jude ui, Jupyter) shares the cookie
    jar — cookies are not port-scoped — and sends ``same-site``."""

    _session(window, client)
    rid = _review(mcp_manager, matter_id)
    status, _, body = client.request(
        "POST", f"/api/r/{rid}/cancel", body=b"{}",
        headers={
            "Content-Type": "application/json",
            "Sec-Fetch-Site": "same-site",
            "Origin": "http://127.0.0.1:1",
        },
    )
    assert (status, body) == (403, b"")
    status, _, _ = client.request("GET", "/", headers={"Sec-Fetch-Site": "same-site"})
    assert status == 403
    assert mcp_manager.get(rid).status == ReviewStatus.AWAITING_REVIEW


def test_missing_sec_fetch_site_403(window, client, mcp_manager, matter_id):
    _session(window, client)
    rid = _review(mcp_manager, matter_id)
    status, _, body = client.request("GET", "/", with_fetch_site=False)
    assert (status, body) == (403, b"")
    status, _, _ = client.request(
        "POST", f"/api/r/{rid}/cancel", body=b"{}",
        headers={"Content-Type": "application/json"}, with_fetch_site=False,
    )
    assert status == 403
    status, _, _ = client.request("GET", "/", headers={"Sec-Fetch-Site": "none"})
    assert status == 200  # a typed address or a bookmark
    assert mcp_manager.get(rid).status == ReviewStatus.AWAITING_REVIEW


def test_post_without_csrf_403(window, client, mcp_manager, matter_id):
    _session(window, client)
    rid = _review(mcp_manager, matter_id)
    status, _ = client.post_json(f"/api/r/{rid}/cancel", {}, with_csrf=False)
    assert status == 403
    assert mcp_manager.get(rid).status == ReviewStatus.AWAITING_REVIEW


def test_api_get_without_csrf_403(window, client, mcp_manager, matter_id):
    _session(window, client)
    rid = _review(mcp_manager, matter_id)
    for path in (f"/api/r/{rid}/state", f"/api/r/{rid}/fragment", f"/api/r/{rid}/answers",
                 "/api/current"):
        status, _, body = client.request("GET", path, with_csrf=False)
        assert (status, body) == (403, b""), path
        assert client.request("GET", path)[0] == 200, path
    assert client.request("GET", "/", with_csrf=False)[0] == 200  # a navigation has no header


def test_csrf_wrong_403(window, client, mcp_manager, matter_id):
    _session(window, client)
    rid = _review(mcp_manager, matter_id)
    client.csrf = "not-the-token"
    status, _ = client.post_json(f"/api/r/{rid}/cancel", {})
    assert status == 403
    assert mcp_manager.get(rid).status == ReviewStatus.AWAITING_REVIEW


def test_get_on_post_route_405(window, client, mcp_manager, matter_id):
    _session(window, client)
    rid = _review(mcp_manager, matter_id)
    status, headers, _ = client.request("GET", f"/api/r/{rid}/approve")
    assert status == 405 and "POST" in headers.get("allow", "")
    status, _, _ = client.request("POST", "/", body=b"{}")
    assert status == 405
    status, _, _ = client.request("POST", f"/api/r/{rid}/state", body=b"{}")
    assert status == 405
    status, _, _ = client.request("POST", "/api/current", body=b"{}")
    assert status == 405


# ----- uploads -----


def test_oversize_file_413_connection_close(window, client, mcp_manager, matter_id):
    _session(window, client)
    rid = mcp_manager.create().review.id
    mcp_manager.choose_matter(rid, matter_id)
    status, headers, _ = client.request(
        "POST", f"/api/r/{rid}/file", body=b"x",
        headers={
            "Content-Type": "application/octet-stream",
            "X-Jude-Suffix": ".txt",
            "Content-Length": str(50 * 1024 * 1024 + 1),
        },
    )
    assert status == 413 and headers.get("connection") == "close"
    assert mcp_manager.get(rid).status == ReviewStatus.AWAITING_FILE


def test_unsupported_suffix_rejected_before_body(window, client, mcp_manager, matter_id):
    _session(window, client)
    rid = mcp_manager.create().review.id
    mcp_manager.choose_matter(rid, matter_id)
    status, headers, body = client.request(
        "POST", f"/api/r/{rid}/file", body=b"x",
        headers={
            "Content-Type": "application/octet-stream",
            "X-Jude-Suffix": ".exe",
            "Content-Length": str(10 * 1024 * 1024),
        },
    )
    assert status == 415 and headers.get("connection") == "close"
    assert json.loads(body) == {"error": "unsupported_suffix"}
    assert mcp_manager.get(rid).status == ReviewStatus.AWAITING_FILE


def test_upload_uses_suffix_header_only(window, client, mcp_manager, matter_id, monkeypatch):
    _session(window, client)
    rid = mcp_manager.create().review.id
    mcp_manager.choose_matter(rid, matter_id)
    seen: list[tuple[str, str]] = []
    original = mcp_manager.attach_file

    def spy(review_id, suffix, data):
        seen.append((review_id, suffix))
        return original(review_id, suffix, data)

    monkeypatch.setattr(mcp_manager, "attach_file", spy)
    # A legacy file-name header is ignored; only the suffix header counts.
    status, _, body = client.request(
        "POST", f"/api/r/{rid}/file", body=TEXT.encode(),
        headers={
            "Content-Type": "application/octet-stream",
            "X-Jude-Suffix": ".txt",
            "X-Jude-Filename": CANARY_FILE,
            "Content-Length": str(len(TEXT.encode())),
        },
    )
    assert status == 200 and json.loads(body) == {"status": "preparing"}
    assert seen == [(rid, ".txt")]
    assert mcp_manager.wait_prepared(rid) == ReviewStatus.AWAITING_REVIEW
    assert CANARY_FILE not in client.page()
    status, _, _ = client.request(
        "POST", f"/api/r/{mcp_manager.create().review.id}/file", body=b"x",
        headers={"Content-Type": "application/octet-stream", "X-Jude-Filename": "memo.txt",
                 "Content-Length": "1"},
    )
    assert status == 415  # no suffix header: refused before the body


def test_raw_body_upload_exact_length(window, client, mcp_manager, matter_id):
    _session(window, client)
    rid = mcp_manager.create().review.id
    mcp_manager.choose_matter(rid, matter_id)
    head = (
        f"POST /api/r/{rid}/file HTTP/1.1\r\nHost: 127.0.0.1:{window.port}\r\n"
        f"Cookie: jude_session={client.cookie}\r\nX-Jude-CSRF: {client.csrf}\r\n"
        "Sec-Fetch-Site: same-origin\r\n"
        "Content-Type: application/octet-stream\r\nX-Jude-Suffix: .txt\r\n"
        "Content-Length: 100\r\n\r\n"
    )
    data = _raw(window.port, head.encode() + b"only ten!!")
    assert data.startswith(b"HTTP/1.1 400")
    assert mcp_manager.get(rid).status == ReviewStatus.AWAITING_FILE


# ----- headers and markup -----


_CSP_RE = re.compile(
    r"^default-src 'none'; script-src 'nonce-([A-Za-z0-9_-]+)'; style-src 'nonce-\1'; "
    r"connect-src 'self'; form-action 'none'; base-uri 'none'; frame-ancestors 'none'$"
)


def _assert_secure(headers: dict[str, str]) -> str:
    m = _CSP_RE.match(headers["content-security-policy"])
    assert m, headers["content-security-policy"]
    assert "http" not in headers["content-security-policy"]
    assert headers["cache-control"] == "no-store"
    assert headers["referrer-policy"] == "no-referrer"
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert "content-length" in headers
    assert "server" not in headers
    return m.group(1)


def _parse_raw(data: bytes) -> tuple[int, dict[str, str], bytes]:
    head, _, body = data.partition(b"\r\n\r\n")
    lines = head.decode("latin-1").split("\r\n")
    status = int(lines[0].split()[1])
    headers = {k.lower(): v for k, v in (ln.split(": ", 1) for ln in lines[1:] if ": " in ln)}
    return status, headers, body


def test_security_headers_on_every_response(window, client, mcp_manager, matter_id):
    import http.client

    _session(window, client)
    rid = _review(mcp_manager, matter_id)
    responses = [
        client.request("GET", "/"),
        client.request("GET", f"/api/r/{rid}/state"),
        client.request("GET", f"/api/r/{rid}/fragment"),
        client.request("GET", "/", with_cookie=False),
        client.request("GET", f"/api/r/{rid}/approve"),
        client.request("POST", f"/api/r/{rid}/cancel", body=b"{}", with_csrf=False),
        client.request("GET", "/", host="evil.test"),
    ]
    for _status, headers, _ in responses:
        _assert_secure(headers)
    assert [r[0] for r in responses] == [200, 200, 200, 404, 405, 403, 400]
    conn = http.client.HTTPConnection("127.0.0.1", window.port, timeout=5)
    conn.request("GET", "/", headers={"Cookie": f"jude_session={client.cookie}",
                                      "Sec-Fetch-Site": "same-origin"})
    resp = conn.getresponse()
    assert resp.version == 11 and resp.getheader("Server") is None
    resp.read()
    conn.close()
    # Errors the stdlib generates itself carry the same headers and no HTML body.
    for line, expected in ((b"GET / HTTP/1.1 extra\r\n\r\n", 400), (b"GET / HTTP/9.9\r\n\r\n", 505),
                           (b"BREW / HTTP/1.1\r\nHost: x\r\n\r\n", 501)):
        status, headers, body = _parse_raw(_raw(window.port, line))
        assert status == expected, line
        _assert_secure(headers)
        assert body == b"" and "server" not in headers


def test_title_is_static(window, client, mcp_manager, store):
    m = store.create_matter(CANARY_MATTER)
    _session(window, client)
    rid = mcp_manager.create().review.id
    mcp_manager.choose_matter(rid, m.id)
    pages = [client.page()]
    mcp_manager.attach_file(rid, ".txt", TEXT.encode())
    assert mcp_manager.wait_prepared(rid) == ReviewStatus.AWAITING_REVIEW
    pages.append(client.page())
    for page in pages:
        assert "<title>Jude</title>" in page
        head = page.split("</head>", 1)[0]
        assert CANARY_MATTER not in head and CANARY_FILE not in head
    assert CANARY_MATTER in pages[0]  # the chooser shows it, in the body, locally
    assert CANARY_FILE not in pages[1]  # the file name never reaches the server


def test_notranslate_and_no_spellcheck_attributes(window, client, mcp_manager, matter_id):
    _session(window, client)
    rid = mcp_manager.create().review.id
    mcp_manager.choose_matter(rid, matter_id)
    pages = [client.page()]
    mcp_manager.attach_file(rid, ".txt", TEXT.encode())
    mcp_manager.wait_prepared(rid)
    pages.append(client.page())
    for page in pages:
        assert re.search(r"<html[^>]*\btranslate=\"no\"", page)
        assert '<meta name="google" content="notranslate">' in page
        tags = re.findall(r"<(?:input|textarea)\b[^>]*>", page)
        assert tags, "the review screen has inputs"
        for tag in tags:
            assert 'spellcheck="false"' in tag and 'autocomplete="off"' in tag, tag


def test_no_inline_handlers_no_inline_style_only_nonced(window, client, mcp_manager, matter_id):
    _session(window, client)
    _review(mcp_manager, matter_id)
    _status, headers, body = client.request("GET", "/")
    page = body.decode("utf-8")
    nonce = _assert_secure(headers)
    assert "onclick=" not in page and "javascript:" not in page and " style=" not in page
    assert page.count("<script") == 1 and page.count(f'<script nonce="{nonce}">') == 1
    assert page.count("<style") == 1 and page.count(f'<style nonce="{nonce}">') == 1
    assert "http://" not in page.split("<body", 1)[0]


def test_gets_do_not_mutate(window, client, mcp_manager, matter_id, clock):
    """No GET — the page load included — changes a review or its clock: a
    repeated or auto-refreshing ``GET /`` must not keep a review that holds
    real names in RAM alive past the idle fail-safe."""

    _session(window, client)
    rid = _review(mcp_manager, matter_id)

    def snapshot():
        r = mcp_manager.get(rid)
        return (
            r.status, r.rendering.sha256, tuple(e.entity_id for e in r.rendering.entities),
            frozenset(r.kept), mcp_manager.expires_at(rid), len(r.answers), r.last_interaction,
        )

    before = snapshot()
    for _ in range(2):
        clock.advance(10)  # a moving clock: a touch would show as a later expiry
        for path in ("/", f"/api/r/{rid}/state", f"/api/r/{rid}/fragment",
                     f"/api/r/{rid}/answers", "/api/current"):
            status, _, _ = client.request("GET", path)
            assert status == 200, path
        client.page()
    assert snapshot() == before
    clock.advance(41)  # 61 s since the last interaction: expired despite the page loads
    assert client.state(rid)["status"] == "expired"


def test_bare_cookie_yields_no_names_and_no_token(window, client, mcp_manager, matter_id,
                                                  window_client_cls):
    """Cookies are host-scoped, not port-scoped: every 127.0.0.1 listener the
    browser visits receives ``jude_session``. A client holding the cookie
    alone (a co-resident listener, forging Sec-Fetch-Site) must read no
    name, no CSRF token and no review, and must not be able to approve."""

    _session(window, client)
    rid = _review(mcp_manager, matter_id)
    sha = mcp_manager.render(rid).sha256
    thief = window_client_cls(window.port)
    thief.cookie = client.cookie  # the leaked cookie, and nothing else
    for fetch_site in ("same-origin", "none"):
        status, _, body = thief.request("GET", "/", headers={"Sec-Fetch-Site": fetch_site})
        page = body.decode("utf-8")
        assert status == 200
        assert ORG not in page and PERSON not in page and rid not in page
        assert "data-csrf" not in page and client.csrf not in page
        assert 'data-status="none"' in page
    for path in (f"/api/r/{rid}/fragment", f"/api/r/{rid}/state", "/api/current",
                 f"/api/r/{rid}/answers"):
        status, _, body = thief.request("GET", path)
        assert (status, body) == (403, b""), path
    status, _, body = thief.request(
        "POST", f"/api/r/{rid}/approve",
        body=json.dumps({"sha256": sha, "attest": True}).encode(),
        headers={"Content-Type": "application/json"},
    )
    assert (status, body) == (403, b"")
    assert mcp_manager.get(rid).status == ReviewStatus.AWAITING_REVIEW
    # The rightful tab, holding the per-origin secret, still works.
    frag = client.fragment(rid)
    assert ORG in frag and "Org1" in frag


def test_malformed_sibling_cookie_does_not_hide_session(window, client, mcp_manager, matter_id):
    """The loopback jar is shared across ports: one odd cookie stored by
    another listener must not lock the lawyer out of the window."""

    _session(window, client)
    rid = _review(mcp_manager, matter_id)
    for jar in (
        f"jude_session={client.cookie}; bad name=1",
        f"weird=a=b; jude_session={client.cookie}; ; =; x",
        f'other="unterminated; jude_session={client.cookie}',
        f"jude_session={client.cookie}; jude_lang=xx",
        f"jude_sessionx=nope; jude_session={client.cookie}",
    ):
        status, _, _ = client.request(
            "GET", f"/api/r/{rid}/state", with_cookie=False, headers={"Cookie": jar}
        )
        assert status == 200, jar
        assert client.request("GET", "/", with_cookie=False, headers={"Cookie": jar})[0] == 200
    for jar in ("jude_sessio=x", f"notjude_session={client.cookie}", "jude_session=", "a=b"):
        status, _, _ = client.request("GET", "/", with_cookie=False, headers={"Cookie": jar})
        assert status == 404, jar


def test_idle_connections_dropped_and_connection_ceiling(mcp_manager, clock):
    """A local process holding hundreds of idle sockets must not exhaust
    the window: connections beyond the ceiling are closed at accept, a
    connection that sends no request line is dropped after the idle
    timeout, and a legitimate request then succeeds."""

    import select

    w = Window(mcp_manager, now=clock.now, state_dir=None, idle_timeout=0.5, max_connections=8)
    w.start()
    socks: list[socket.socket] = []
    try:
        assert type(w.server).request_queue_size == 16
        for _ in range(40):
            sk = socket.create_connection(("127.0.0.1", w.port), timeout=5)
            socks.append(sk)
        time.sleep(0.2)
        assert w.server.live_connections <= 8
        # Beyond the ceiling the server closed the socket at once: recv gives EOF.
        closed_now = 0
        for sk in socks:
            readable, _, _ = select.select([sk], [], [], 0)
            if readable and sk.recv(1) == b"":
                closed_now += 1
        assert closed_now >= 40 - 8
        # The idle ones are dropped once the idle timeout has elapsed.
        time.sleep(1.0)
        for sk in socks:
            sk.settimeout(2)
            assert sk.recv(1) == b""
        deadline = time.time() + 5
        while w.server.live_connections and time.time() < deadline:
            time.sleep(0.02)
        assert w.server.live_connections == 0
        nonce = "ab" * 16
        conn = http.client.HTTPConnection("127.0.0.1", w.port, timeout=5)
        conn.request("GET", f"/api/ping?nonce={nonce}", headers={"Host": w.host_header})
        resp = conn.getresponse()
        assert resp.status == 200 and json.loads(resp.read())["mac"] == w.ping_mac(nonce)
        conn.close()
    finally:
        for sk in socks:
            with contextlib.suppress(OSError):
                sk.close()
        w.stop()


def test_kept_occurrences_marked_in_leaving_text(window, client, mcp_manager, matter_id):
    """A Keep puts a real name back in the text that leaves; every such
    occurrence (alias forms included) is shaded, so an un-redaction is never
    indistinguishable from prose in the text the lawyer attests."""

    _session(window, client)
    rid = _review(mcp_manager, matter_id)
    org = next(e for e in mcp_manager.render(rid).entities if e.canonical == ORG)
    frag = client.fragment(rid)
    assert '<mark class="kept">' not in frag
    status, frag = client.post_json(f"/api/r/{rid}/decide", {"entity_id": org.entity_id,
                                                                "action": "keep"})
    assert status == 200
    leaving = re.search(r'<pre class="leaving"[^>]*>(.*?)</pre>', frag, re.S).group(1)
    original = re.search(r'<pre class="original hidden" id="original">(.*?)</pre>', frag,
                         re.S).group(1)
    assert leaving.count(f'<mark class="kept">{ORG}</mark>') == TEXT.count(ORG) == 2
    assert original.count(f'<mark class="kept">{ORG}</mark>') == 2
    assert "Org1" not in leaving and '<mark class="h">Person1</mark>' in leaving
    assert f'<mark class="raw">{PERSON}</mark>' in original
    assert '<mark class="raw">' + ORG not in original
    # The marks are display only: the hash is over the plain text.
    plain = html.unescape(re.sub(r"<[^>]+>", "", leaving))
    assert plain == mcp_manager.render(rid).text
    assert "mark.kept" in client.shell()


def test_approved_uncollected_keeps_withdraw_screen(window, client, mcp_manager, matter_id):
    """A second conversation's prepare_document must not displace the
    Approved screen (the only place with Withdraw) while the text is still
    collectable."""

    _session(window, client)
    rid = _approved(mcp_manager, matter_id)
    outcome = mcp_manager.create()  # another conversation
    assert outcome.already_open and outcome.review.id == rid
    assert client.get_json("/api/current")[1] == {"review_id": rid, "status": "approved"}
    page = client.page()
    assert 'data-status="approved"' in page and 'data-action="cancel" class="withdraw"' in page
    status, obj = client.post_json(f"/api/r/{rid}/cancel", {})
    assert status == 200 and obj == {"status": "cancelled", "outcome": "withdrawn"}
    assert mcp_manager.create().already_open is False  # now a new review can start


def test_closing_never_approves(window, client, mcp_manager, matter_id, clock, monkeypatch):
    _session(window, client)
    rid = _review(mcp_manager, matter_id)
    calls: list[str] = []
    original = mcp_manager.approve
    monkeypatch.setattr(
        mcp_manager, "approve", lambda *a, **k: (calls.append("approve"), original(*a, **k))[1]
    )
    client.page()  # the lawyer opens the page and closes the tab
    clock.advance(61)
    mcp_manager.sweep()
    assert mcp_manager.get(rid).status == ReviewStatus.EXPIRED
    assert calls == []


def test_full_flow_over_http(window, client, mcp_manager, matter_id, store):
    _session(window, client)
    rid = mcp_manager.create().review.id
    page = client.page()
    assert 'data-status="awaiting_matter"' in page
    status, frag = client.post_json(f"/api/r/{rid}/matter", {"matter_id": matter_id})
    assert status == 200 and 'data-status="awaiting_file"' in frag
    status, obj = client.upload(rid, ".txt", TEXT.encode("utf-8"))
    assert status == 200 and obj == {"status": "preparing"}
    deadline = time.time() + 20
    while client.state(rid)["status"] != "awaiting_review":
        assert time.time() < deadline, client.state(rid)
        time.sleep(0.05)
    frag = client.fragment(rid)
    sha_old = re.search(r'data-sha256="([0-9a-f]{64})"', frag).group(1)
    assert "Org1" in frag and ORG in frag  # pseudonym in the text, real name in the table
    entity_id = int(re.search(r'data-entity="(\d+)" data-decision="keep"', frag).group(1))
    status, frag2 = client.post_json(
        f"/api/r/{rid}/decide", {"entity_id": entity_id, "action": "keep"}
    )
    assert status == 200 and frag2 != frag
    sha_new = re.search(r'data-sha256="([0-9a-f]{64})"', frag2).group(1)
    assert sha_new != sha_old
    status, obj = client.post_json(f"/api/r/{rid}/approve", {"sha256": sha_old, "attest": True})
    assert status == 409 and obj == {"error": "text_changed"}
    status, obj = client.post_json(f"/api/r/{rid}/approve", {"sha256": sha_new})
    assert status == 400 and obj == {"error": "attestation_required"}
    status, obj = client.post_json(f"/api/r/{rid}/approve", {"sha256": sha_new, "attest": True})
    assert status == 200 and obj["status"] == "approved" and obj["sha256"] == sha_new
    assert client.state(rid)["status"] == "approved"
    assert store.get_approval(mcp_manager.get(rid).approval_id).payload_sha256 == sha_new
    page = client.page()
    assert 'data-status="approved"' in page and "Approved in Jude." in page


def test_log_message_silenced(window, client, capfd):
    url = window.mint_url()
    otp = url.rsplit("/", 1)[1]
    _session(window, client)
    client.request("GET", "/", with_cookie=False)
    client.request("GET", "/nope")
    client.request("GET", "/", host="evil.test")
    _raw(window.port, b"GET / HTTP/9.9\r\n\r\n")
    err = capfd.readouterr().err
    assert otp not in err and (client.cookie or "x") not in err
    assert "GET /" not in err and "code 505" not in err


def test_ping_and_mint_hmac(window, client, mcp_manager):
    import hashlib
    import hmac as hm

    def mac(secret: str, prefix: str, nonce: str) -> str:
        return hm.new(secret.encode(), f"{prefix}:{nonce}".encode(), hashlib.sha256).hexdigest()

    nonce = "ab" * 16
    status, obj = client.get_json(f"/api/ping?nonce={nonce}")
    assert status == 200 and obj["mac"] == mac(window.local_secret, "ping", nonce)
    assert set(obj) == {"mac"}  # a bare nonce learns the identity, nothing else
    proof = mac(window.local_secret, "query", nonce)
    status, obj = client.get_json(f"/api/ping?nonce={nonce}&proof={proof}")
    assert status == 200 and set(obj) == {"mac", "has_review"} and obj["has_review"] is False
    mcp_manager.create()
    assert client.get_json(f"/api/ping?nonce={nonce}&proof={proof}")[1]["has_review"] is True
    assert client.request("GET", "/api/ping")[0] == 404
    wrong = {"nonce": nonce, "mac": mac("not-the-secret", "mint", nonce)}
    assert client.post_json("/api/mint", wrong, with_csrf=False)[0] == 404
    good = {"nonce": nonce, "mac": mac(window.local_secret, "mint", nonce)}
    status, obj = client.post_json("/api/mint", good, with_csrf=False)
    assert status == 200 and obj["url"].startswith(f"http://127.0.0.1:{window.port}/open/")
    assert client.post_json("/api/mint", good, with_csrf=False)[0] == 404  # replayed nonce
    assert client.open(obj["url"])[0] == 200


def test_answers_fragment_escaped_and_framed(window, client, mcp_manager, matter_id):
    _session(window, client)
    rid = _released(mcp_manager, matter_id)
    mcp_manager.show_answer(rid, "<script>alert(1)</script> Org1 instructed Person1.")
    status, _, body = client.request("GET", f"/api/r/{rid}/answers")
    frag = body.decode("utf-8")
    assert status == 200
    assert "<script>" not in frag and "&lt;script&gt;alert(1)&lt;/script&gt;" in frag
    assert ORG in frag and PERSON in frag
    assert 'class="legend"' in frag and 'class="warning"' in frag
    assert '<pre class="model-text" id="answer-1">' in frag


def test_answers_fragment_has_copy_button_per_answer(window, client, mcp_manager, matter_id):
    _session(window, client)
    rid = _released(mcp_manager, matter_id)
    mcp_manager.show_answer(rid, "Org1 first.")
    mcp_manager.show_answer(rid, "Person1 second.")
    status, _, body = client.request("GET", f"/api/r/{rid}/answers")
    frag = body.decode("utf-8")
    assert status == 200
    for i in (1, 2):
        assert f'data-action="copy-answer" data-target="answer-{i}"' in frag
        assert f'id="answer-{i}"' in frag
    page = client.page()
    assert "copy-answer" in page.split("<script", 1)[1] and "clipboard" in page


def test_pages_fr(window, client, mcp_manager, matter_id):
    _session(window, client)
    _review(mcp_manager, matter_id)
    page = client.page(headers={"Accept-Language": "fr-BE,fr;q=0.9,en;q=0.8"})
    assert 'lang="fr"' in page and "Approuver" in page
    client.extra_cookies["jude_lang"] = "en"
    page = client.page(headers={"Accept-Language": "fr-BE,fr;q=0.9,en;q=0.8"})
    assert 'lang="en"' in page and ">Approve<" in page and "Approuver" not in page
    status, obj = client.post_json("/api/lang", {"lang": "fr"})
    assert status == 200 and obj == {"lang": "fr"}


def test_ledger_ref_and_zr_tag_translated(window, client, mcp_manager, matter_id, store):
    store.create_matter(
        "zr here", mode=Mode.SMART, llm_endpoint="claude-desktop", zero_retention_attested=True
    )
    _session(window, client)
    client.extra_cookies["jude_lang"] = "fr"
    rid = mcp_manager.create().review.id
    page = client.page()
    assert "· ZR" in page and "zr here" in page
    mcp_manager.cancel(rid)
    _released(mcp_manager, matter_id)
    page = client.page()
    assert "approvals #" not in page and "enregistrement" in _body(page).lower()
    assert _status_line(page).startswith(_s("ui.status.handed_once", "fr"))


def test_server_gone_banner_in_js(window, client):
    page = _session(window, client)
    script = page.split("<script", 1)[1]
    assert "failures >= 3" in script and "banner.server_gone" in script
    assert "Jude is no longer running" in script
    assert "/api/current" in script and "heartbeat" in script and "visibilityState" in script


def test_sweep_runs_on_its_own_thread(mcp_manager, clock, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        mcp_manager, "sweep", lambda: calls.append(threading.current_thread().name)
    )
    w = Window(mcp_manager, now=clock.now, state_dir=None, sweep_interval=0.05)
    w.start()
    try:
        deadline = time.time() + 5
        while not calls and time.time() < deadline:
            time.sleep(0.02)
        assert calls and calls[0] == "jude-sweep"
        assert not hasattr(type(w.server), "service_actions") or (
            type(w.server).service_actions is type(w.server).__mro__[1].service_actions
        )
    finally:
        w.stop()
    assert not any(t.name == "jude-sweep" and t.is_alive() for t in threading.enumerate())


def _window_thread_alive() -> bool:
    return any(t.name == "jude-window" and t.is_alive() for t in threading.enumerate())


def test_stop_is_bounded_when_the_serve_loop_is_wedged(mcp_manager, clock):
    """``BaseServer.shutdown()`` waits for the serve loop with no limit, and
    the loop can wedge inside ``accept()`` (``poll`` reported a connection
    that vanished before ``accept`` — BSD/macOS then block). That once held
    a SIGTERM for ever. ``stop(timeout)`` must return in bounded time, and
    the loop must end once whatever blocked it lets go."""

    w = Window(mcp_manager, now=clock.now, state_dir=None)
    w.start()
    wedged = threading.Event()
    release = threading.Event()
    real_get_request = w.server.get_request

    def stuck_get_request():
        request, _addr = real_get_request()
        request.close()
        wedged.set()
        release.wait()  # the serve loop sits here, as a blocked accept() would
        raise OSError("simulated")  # serve_forever swallows get_request errors

    w.server.get_request = stuck_get_request  # instance attribute shadows the method
    try:
        with socket.create_connection(("127.0.0.1", w.port), timeout=5):
            assert wedged.wait(5)
        t0 = time.monotonic()
        w.stop(timeout=1.0)
        assert time.monotonic() - t0 < 5
        assert _window_thread_alive()  # still wedged: stop() did not wait for it
    finally:
        release.set()
    deadline = time.time() + 5
    while _window_thread_alive() and time.time() < deadline:
        time.sleep(0.02)
    assert not _window_thread_alive()


# ----- the screens -----


def test_header_status_line_matches_status(window, client, mcp_manager, matter_id):
    _session(window, client)
    rid = _review(mcp_manager, matter_id)
    assert _status_line(client.page()) == _s("ui.nothing_left")
    assert client.state(rid)["status_line"] == "nothing_left"
    mcp_manager.approve(rid, mcp_manager.render(rid).sha256, attest=True)
    assert _status_line(client.page()) == _s("ui.nothing_left")
    mcp_manager.release(rid)
    page = client.page()
    line = _status_line(page)
    assert _s("ui.nothing_left") not in line and _s("ui.nothing_left") not in _body(page)
    assert line == f"{_s('ui.status.handed_once')} #{mcp_manager.get(rid).approval_id}."
    assert client.state(rid)["status_line"] == "handed_once"


def test_approved_screen_has_visible_tell_claude_step_and_withdraw(window, client, mcp_manager,
                                                                   matter_id):
    _session(window, client)
    rid = _approved(mcp_manager, matter_id)
    page = client.page()
    for key in ("ui.approved_title", "ui.step_approved", "ui.step_tell", "ui.step_tell_why",
                "ui.step_collect", "ui.approved_window", "ui.withdraw", "ui.nudge_phrase"):
        assert _s(key) in _body(page), key
    assert 'data-action="cancel" class="withdraw"' in page
    assert 'data-action="copy" data-copy="Approved in Jude."' in page
    assert "record #" in page and "approvals #" not in page
    status, obj = client.post_json(f"/api/r/{rid}/cancel", {})
    assert status == 200 and obj == {"status": "cancelled", "outcome": "withdrawn"}
    page = client.page()
    assert _s("ui.closed_withdrawn") in _body(page)


def test_released_screen_shows_collected_time(window, client, mcp_manager, matter_id, clock):
    _session(window, client)
    rid = _released(mcp_manager, matter_id)
    page = client.page()
    assert _s("ui.released_title") in _body(page)
    m = re.search(r'<time datetime="([^"]+)"', page)
    assert m and m.group(1).startswith("2023-11-14T22")  # the fake clock, in UTC
    assert "record #" in page and _s("ui.answers_title") in page
    assert client.state(rid)["released_at"] == clock.now()


def test_cancel_after_release_reports_too_late(window, client, mcp_manager, matter_id, store):
    _session(window, client)
    rid = _released(mcp_manager, matter_id)
    status, obj = client.post_json(f"/api/r/{rid}/cancel", {})
    assert status == 200 and obj == {"status": "released", "outcome": "released"}
    page = client.page()
    assert 'id="too-late"' in page and _s("ui.too_late") in _body(page)
    assert store.get_approval(mcp_manager.get(rid).approval_id).outcome == "released"


def test_api_current_reflects_live_review(window, client, mcp_manager, matter_id):
    _session(window, client)
    status, obj = client.get_json("/api/current")
    assert status == 200 and obj == {"review_id": None, "status": None}
    page = client.page()
    assert 'data-status="none"' in page and _s("ui.start_from_claude") in page
    rid = mcp_manager.create().review.id
    assert client.get_json("/api/current")[1] == {"review_id": rid, "status": "awaiting_matter"}
    mcp_manager.cancel(rid)
    assert client.get_json("/api/current")[1] == {"review_id": rid, "status": "cancelled"}


def test_heartbeat_extends_ttl_poll_does_not(window, client, mcp_manager, matter_id, clock):
    _session(window, client)
    rid = mcp_manager.create().review.id
    client.page()
    for _ in range(5):
        clock.advance(10)
        assert client.state(rid)["status"] == "awaiting_matter"
    status, obj = client.post_json(f"/api/r/{rid}/heartbeat", {})
    assert status == 200 and obj == {"expires_in": 60}
    clock.advance(50)
    assert client.state(rid)["status"] == "awaiting_matter"
    clock.advance(11)
    assert client.state(rid)["status"] == "expired"


def test_expires_in_in_state(window, client, mcp_manager, matter_id, clock):
    _session(window, client)
    rid = mcp_manager.create().review.id
    st = client.state(rid)
    assert st["expires_in"] == 60 and st["phase"] is None and st["approval_id"] is None
    assert set(st) == {
        "review_id", "status", "phase", "sha256", "answers", "error_key", "missing",
        "mode_notice", "expires_in", "approval_id", "status_line", "released_at",
    }
    clock.advance(30)
    assert client.state(rid)["expires_in"] == 30


def test_window_state_reports_phase(window, client, mcp_manager, matter_id):
    _session(window, client)
    rid = _review(mcp_manager, matter_id)
    r = mcp_manager.get(rid)
    assert client.state(rid)["phase"] is None
    r.status = ReviewStatus.PREPARING
    r.phase = "loading_models"
    assert client.state(rid)["phase"] == "loading_models"
    frag = client.fragment(rid)
    assert 'data-phase="loading_models"' in frag
    assert _s("ui.phase.loading_models") in frag
    assert 'data-action="cancel"' in frag  # cancel is possible while preparing


def test_window_accepts_requests_while_detecting(window, client, mcp_manager, store, matter_id,
                                                 fake_pipeline_cls):
    from tests.test_mcp_reviews import _Gate

    _session(window, client)
    gate = _Gate(fake_pipeline_cls())
    mcp_manager._pipeline_factory = lambda s, m, c: gate
    other = store.create_matter("gated matter")
    rid = mcp_manager.create().review.id
    client.post_json(f"/api/r/{rid}/matter", {"matter_id": other.id})
    client.upload(rid, ".txt", TEXT.encode())
    assert gate.entered.wait(5)
    t0 = time.monotonic()
    assert client.state(rid)["status"] == "preparing"
    assert client.page()
    status, obj = client.post_json(f"/api/r/{rid}/cancel", {})
    assert status == 200 and obj["status"] == "cancelled"
    assert time.monotonic() - t0 < 1.0
    gate.gate.set()
    mcp_manager.wait_prepared(rid)
    assert store.list_entities(other.id) == []


def test_error_screen_models_missing_lists_components_and_command(window, client, mcp_manager,
                                                                   matter_id):
    _session(window, client)
    rid = mcp_manager.create().review.id
    mcp_manager.choose_matter(rid, matter_id)
    r = mcp_manager.get(rid)
    r.status = ReviewStatus.FAILED
    r.error_key = "models_missing"
    r.missing = ("spacy_nl", "gliner")
    page = client.page()
    assert _s("ui.closed_failed") in page
    assert _s("ui.error.models_missing") in page
    assert _s("ui.missing.spacy_nl") in page
    assert _s("ui.missing.gliner") in page
    assert _s("ui.missing.spacy_fr") not in page
    assert "jude mcp doctor --as-desktop --fix" in page
    assert "/Users" not in page.split("<body", 1)[1].split("<script", 1)[0]
    assert client.state(rid)["missing"] == ["spacy_nl", "gliner"]


def test_error_screen_component_missing_and_needs_ocr(window, client, mcp_manager, matter_id):
    _session(window, client)
    rid = mcp_manager.create().review.id
    mcp_manager.choose_matter(rid, matter_id)
    r = mcp_manager.get(rid)
    r.status = ReviewStatus.FAILED
    r.error_key = "component_missing"
    r.missing = ("pdf",)
    page = client.page()
    assert _s("ui.error.component_missing") in page
    assert "jude[pdf]" in page and "jude[xlsx]" not in page
    r.error_key = "needs_ocr"
    r.missing = ()
    page = client.page()
    assert _s("ui.error.needs_ocr") in page and "jude redact --ocr" in page
    r.error_key = "too_long"
    assert "150 000" in client.page()


def test_review_screen_shows_adapter_warnings(window, client, mcp_manager, matter_id):
    _session(window, client)
    rid = _review(mcp_manager, matter_id)
    assert _s("ui.warn.comments") not in client.page()
    mcp_manager.get(rid).warnings = ("comments", "metadata")
    page = client.page()
    assert _s("ui.warn.comments") in page
    assert _s("ui.warn.metadata") in page
    assert _s("ui.warn.tracked_changes") not in page


def test_review_screen_shows_after_approve_sentence(window, client, mcp_manager, matter_id):
    _session(window, client)
    _review(mcp_manager, matter_id)
    page = client.page()
    assert _s("ui.after_approve") in page
    assert _s("ui.attest") in page
    assert 'data-text-read="0"' in page and 'id="countdown"' in page


def test_review_screen_shows_risk_badge(window, client, mcp_manager, matter_id):
    _session(window, client)
    _review(mcp_manager, matter_id, text=f"{ORG} wrote a short note.\n")
    page = client.page()
    assert _s("ui.risk.lead") in page and _s("ui.risk.none") in page
    text = f"{ORG} paid EUR 1,250,000 on 13 October 2023 in Case T-123/21.\n\nUnrelated.\n"
    _review(mcp_manager, matter_id, text=text)
    page = client.page()
    assert 'class="risk-medium"' in page or 'class="risk-high"' in page
    assert "● " in page and re.search(r"<code>Org\d+</code>:", page)
    assert "currency figure" in page and _s("ui.risk.none") not in page
    rid = _review(mcp_manager, matter_id, text=f"{ORG} pay​ now.\n")
    page = client.page()
    assert _s("ui.invisible_chars") in page and "(1)" in page
    assert 'data-action="toggle-invisible"' in page
    assert '<mark class="inv">U+200B</mark>' in page
    mcp_manager.get(rid).unmodelled = ("de",)
    page = client.page()
    assert _s("ui.risk.language_unmodelled") in page and "de</p>" in page


def test_original_toggle_present_and_hidden_by_default(window, client, mcp_manager, matter_id):
    _session(window, client)
    rid = _review(mcp_manager, matter_id)
    page = client.page()
    assert '<pre class="original hidden" id="original">' in page
    assert '<mark class="raw">' + ORG + "</mark>" in page
    assert 'data-action="toggle-original"' in page
    assert _s("ui.show_original") in _body(page) and _s("ui.show_leaving") in _body(page)
    sha = mcp_manager.render(rid).sha256
    assert page.count(f'data-sha256="{sha}"') == 1  # the original view never changes the hash


def test_approve_body_carries_text_read(window, client, mcp_manager, matter_id, store):
    _session(window, client)
    rid = _review(mcp_manager, matter_id)
    sha = mcp_manager.render(rid).sha256
    status, _ = client.post_json(
        f"/api/r/{rid}/approve", {"sha256": sha, "attest": True, "text_read": True}
    )
    assert status == 200
    assert store.get_approval(mcp_manager.get(rid).approval_id).attestation == (
        "items_reviewed_text_read"
    )
    rid = _review(mcp_manager, matter_id)
    sha = mcp_manager.render(rid).sha256
    client.post_json(f"/api/r/{rid}/approve", {"sha256": sha, "attest": True})
    assert store.get_approval(mcp_manager.get(rid).approval_id).attestation == (
        "items_reviewed_text_opened"
    )
    page = client.page()
    assert "text_read" in page.split("<script", 1)[1]
