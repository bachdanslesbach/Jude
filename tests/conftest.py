from __future__ import annotations

import html
import http.client
import json
import re
from pathlib import Path
from typing import Any

import pytest

from jude.store import Store
from jude.types import Detection, DetectionSource, EntityType, Mode

__all__ = ["FakeClock", "FakePipeline", "StdioHarness", "WindowClient"]


@pytest.fixture
def store(tmp_path: Path) -> Store:
    s = Store(tmp_path / "test.db")
    yield s
    s.close()


@pytest.fixture
def matter_id(store: Store) -> str:
    m = store.create_matter("test matter", mode=Mode.STRICT)
    return m.id


@pytest.fixture
def smart_matter_id(store: Store) -> str:
    """A smart matter whose zero-retention attestation names Claude Desktop:
    the only kind the plugin processes in smart mode."""

    m = store.create_matter(
        "smart matter",
        mode=Mode.SMART,
        llm_endpoint="claude-desktop",
        zero_retention_attested=True,
    )
    return m.id


# ----- MCP plugin fixtures (offline: no spaCy, no GLiNER) -----

FAKE_ORG = "Thonnard SA"
FAKE_PERSON = "Marie-Claire Lefèvre"
FAKE_TEXT = (
    f"Re: {FAKE_ORG} — note to file\n\n"
    f"Our client {FAKE_ORG} met {FAKE_PERSON} on 3 March. "
    f"{FAKE_PERSON} confirmed that {FAKE_ORG} will file by Friday.\n"
)


class FakePipeline:
    """Stands in for DetectionPipeline: finds every occurrence of two fixed
    surfaces, counts its calls, never loads a model. Accepts the real
    pipeline's constructor keywords (``redact_codenames`` included) so it
    can replace the class wholesale, and reports one English paragraph."""

    surfaces: tuple[tuple[str, EntityType], ...] = (
        (FAKE_ORG, EntityType.ORG),
        (FAKE_PERSON, EntityType.PERSON),
    )

    def __init__(self, *args: Any, redact_codenames: bool | None = None, **kwargs: Any) -> None:
        self.calls = 0
        self.redact_codenames = bool(redact_codenames)

    def detect(self, text: str) -> list[Detection]:
        self.calls += 1
        out: list[Detection] = []
        for surface, etype in self.surfaces:
            for m in re.finditer(re.escape(surface), text):
                out.append(
                    Detection(
                        text=surface,
                        start=m.start(),
                        end=m.end(),
                        entity_type=etype,
                        source=DetectionSource.SPACY,
                    )
                )
        return sorted(out, key=lambda d: d.start)

    def language_report(self) -> tuple[dict[str, int], tuple[str, ...]]:
        return {"en": 1}, ()


class FakeClock:
    def __init__(self, start: float = 1_700_000_000.0) -> None:
        self.t = start

    def now(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


@pytest.fixture
def fake_pipeline_cls() -> type[FakePipeline]:
    return FakePipeline


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def mcp_manager(store: Store, matter_id: str, clock: FakeClock, tmp_path: Path, monkeypatch):
    from jude.mcp.reviews import ReviewManager

    monkeypatch.setenv("JUDE_HOME", str(tmp_path / "home"))
    opens: list[str] = []

    def open_browser(url: str) -> bool:
        opens.append(url)
        return True

    mgr = ReviewManager(
        store,
        pipeline_factory=lambda s, m, c: FakePipeline(redact_codenames=c),
        idle_ttl=60,
        approved_hold=120,
        now=clock.now,
        open_browser=open_browser,
        tmp_dir=tmp_path / "home" / "mcp" / "tmp",  # never the real ~/.jude
    )
    mgr.test_opens = opens  # type: ignore[attr-defined]
    yield mgr
    mgr.close(grace=1.0)


class WindowClient:
    """A tiny http.client driver for the review window used by the window
    and server tests. Keeps the session cookie and the per-origin secret
    (the CSRF token, which the one-shot landing page hands to the browser's
    sessionStorage), and sends what a browser sends: ``Sec-Fetch-Site:
    same-origin`` on every request and ``X-Jude-CSRF`` on every API call,
    GETs included. ``page()`` composes what the lawyer sees the way
    ``window.js`` does: the shell ``GET /`` returns, filled with the
    current review's fragment and status line fetched through ``/api/*``."""

    def __init__(self, port: int, host: str = "127.0.0.1") -> None:
        self.host = host
        self.port = port
        self.cookie: str | None = None
        self.csrf: str | None = None
        self.extra_cookies: dict[str, str] = {}

    def request(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        *,
        with_cookie: bool = True,
        with_csrf: bool = True,
        with_fetch_site: bool = True,
        host: str | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        conn = http.client.HTTPConnection(self.host, self.port, timeout=10)
        h: dict[str, str] = {}
        if host is not None:
            h["Host"] = host
        cookies = []
        if with_cookie and self.cookie:
            cookies.append(f"jude_session={self.cookie}")
        for k, v in self.extra_cookies.items():
            cookies.append(f"{k}={v}")
        if cookies:
            h["Cookie"] = "; ".join(cookies)
        if with_fetch_site:
            h["Sec-Fetch-Site"] = "same-origin"
        if with_csrf and self.csrf and (method == "POST" or path.startswith("/api/")):
            h["X-Jude-CSRF"] = self.csrf
        if headers:
            h.update(headers)
        try:
            conn.request(method, path, body=body, headers=h)
            resp = conn.getresponse()
            data = resp.read()
            return resp.status, {k.lower(): v for k, v in resp.getheaders()}, data
        finally:
            conn.close()

    def open(self, url: str) -> tuple[int, dict[str, str], bytes]:
        """Follow a one-shot URL: store the cookie from the landing page's
        Set-Cookie and the per-origin secret from its body (what the page's
        script puts in sessionStorage)."""

        path = url.split(f"{self.port}", 1)[1]
        status, headers, body = self.request(
            "GET", path, with_cookie=False, headers={"Sec-Fetch-Site": "none"}
        )
        set_cookie = headers.get("set-cookie", "")
        m = re.search(r"jude_session=([^;]+)", set_cookie)
        if m:
            self.cookie = m.group(1)
        m = re.search(r'data-csrf="([^"]+)"', body.decode("utf-8", "replace"))
        if m:
            self.csrf = html.unescape(m.group(1))
        return status, headers, body

    def shell(self, headers: dict[str, str] | None = None) -> str:
        """``GET /`` as the server returns it: the shell, nothing filled in."""

        status, _, body = self.request("GET", "/", headers=headers)
        assert status == 200, status
        return body.decode("utf-8")

    def page(self, headers: dict[str, str] | None = None) -> str:
        """The page as the lawyer sees it once ``window.js`` has bootstrapped:
        the shell with the current review's fragment in ``<main>`` and the
        status line set from the review's state."""

        from jude.mcp.strings import text as _s

        page = self.shell(headers=headers)
        if not self.csrf:
            return page
        lang = re.search(r'<html lang="([a-z]+)"', page).group(1)
        status, cur = self.get_json("/api/current", headers=headers)
        assert status == 200, status
        rid = cur.get("review_id") if isinstance(cur, dict) else None
        line = _s("ui.nothing_left", lang)
        if rid:
            st = self.state(rid, headers=headers)
            frag = self.fragment(rid, headers=headers)
            page = re.sub(
                r'<main id="screen">.*?</main>',
                lambda _m: f'<main id="screen">{frag}</main>',
                page,
                count=1,
                flags=re.S,
            )
            if st["status"] == "released":
                line = f"{_s('ui.status.handed_once', lang)} #{st['approval_id']}."
        return page.replace(
            '<span id="status-line" class="status-line"></span>',
            f'<span id="status-line" class="status-line">{html.escape(line)}</span>',
            1,
        )

    def get_json(self, path: str, **kw: Any) -> tuple[int, Any]:
        status, _, body = self.request("GET", path, **kw)
        return status, (json.loads(body) if body else None)

    def post_json(self, path: str, obj: Any, **kw: Any) -> tuple[int, Any]:
        status, _, body = self.request(
            "POST",
            path,
            body=json.dumps(obj).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            **kw,
        )
        try:
            parsed = json.loads(body) if body else None
        except ValueError:
            parsed = body.decode("utf-8", "replace")
        return status, parsed

    def upload(self, review_id: str, suffix: str, data: bytes) -> tuple[int, Any]:
        """Send the bytes with the suffix only: the file name never travels."""

        status, _, body = self.request(
            "POST",
            f"/api/r/{review_id}/file",
            body=data,
            headers={
                "Content-Type": "application/octet-stream",
                "X-Jude-Suffix": suffix,
                "Content-Length": str(len(data)),
            },
        )
        return status, (json.loads(body) if body else None)

    def fragment(self, review_id: str, headers: dict[str, str] | None = None) -> str:
        status, _, body = self.request("GET", f"/api/r/{review_id}/fragment", headers=headers)
        assert status == 200, status
        return body.decode("utf-8")

    def state(self, review_id: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
        status, obj = self.get_json(f"/api/r/{review_id}/state", headers=headers)
        assert status == 200, status
        return obj


@pytest.fixture
def window_client_cls() -> type[WindowClient]:
    return WindowClient


# ----- stdio harness: the real server process with the fake detector -----

FAKE_SERVER = Path(__file__).parent / "mcp_fake_server.py"


def tool_result_dict(result: Any) -> dict[str, Any]:
    """The structured result of a tool call (or the JSON of its text block)."""

    if getattr(result, "structured_content", None) is not None:
        return dict(result.structured_content)
    text = "".join(getattr(c, "text", "") for c in result.content)
    return json.loads(text) if text else {}


def tool_result_text(result: Any) -> str:
    """Everything a model could read in a result: text blocks and the
    structured content, serialised."""

    parts = [getattr(c, "text", "") for c in result.content]
    if getattr(result, "structured_content", None) is not None:
        parts.append(json.dumps(result.structured_content, ensure_ascii=False))
    return "\n".join(parts)


class StdioHarness:
    """Spawn ``tests/mcp_fake_server.py`` over stdio with ``JUDE_HOME`` set
    to a temporary directory; seed its database; drive its window over
    HTTP; collect transport-level parse errors and the server's stderr."""

    TEXT = FAKE_TEXT

    def __init__(
        self,
        home: Path,
        *,
        mode: str = "normal",
        debug_fds: bool = False,
        debug_net: bool = False,
        extra_env: dict[str, str] | None = None,
        args: tuple[str, ...] = (),
    ) -> None:
        import sys

        self.home = Path(home)
        self.home.mkdir(parents=True, exist_ok=True)
        self.stderr_path = self.home / "stderr.log"
        self.errors: list[Exception] = []
        self.session: Any = None
        self.init: Any = None
        self._stack: Any = None
        self._errlog: Any = None
        self.env = {
            "JUDE_HOME": str(self.home),
            "JUDE_MCP_NO_BROWSER": "1",
            "JUDE_MCP_FAKE_MODE": mode,
            "JUDE_MCP_FAKE_DEBUG_FDS": "1" if debug_fds else "0",
            "JUDE_MCP_FAKE_DEBUG_NET": "1" if debug_net else "0",
            "PYTHONWARNINGS": "default",
            "PYTHONUNBUFFERED": "1",
            **(extra_env or {}),
        }
        self.command = sys.executable
        self.args = [str(FAKE_SERVER), *args]

    def seed(
        self,
        matter_name: str = "Thonnard / Kestrel",
        entity: tuple[str, EntityType] | None = ("Someone Unrelated", EntityType.PERSON),
    ) -> str:
        with Store(self.home / "jude.db") as s:
            m = s.create_matter(matter_name)
            if entity is not None:
                s.create_entity(m.id, entity[0], entity[1])
        return m.id

    async def __aenter__(self) -> StdioHarness:
        from contextlib import AsyncExitStack

        from mcp.client.session import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        self._errlog = self.stderr_path.open("a", encoding="utf-8")
        params = StdioServerParameters(command=self.command, args=self.args, env=self.env)
        self._stack = AsyncExitStack()
        read, write = await self._stack.enter_async_context(
            stdio_client(params, errlog=self._errlog)
        )
        self.session = await self._stack.enter_async_context(
            ClientSession(read, write, message_handler=self._on_message)
        )
        self.init = await self.session.initialize()
        return self

    async def __aexit__(self, *exc: object) -> None:
        try:
            await self._stack.aclose()
        finally:
            self._errlog.close()

    async def _on_message(self, message: Any) -> None:
        if isinstance(message, Exception):
            self.errors.append(message)

    async def call(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        return await self.session.call_tool(name, arguments or {})

    def stderr(self) -> str:
        if self._errlog is not None and not self._errlog.closed:
            self._errlog.flush()
        return self.stderr_path.read_text(encoding="utf-8", errors="replace")

    def trace(self) -> str:
        path = self.home / "mcp" / "trace.log"
        return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""

    def window_info(self, timeout: float = 15.0) -> dict[str, Any]:
        import time

        from jude.mcp.launch import read_window_file

        deadline = time.time() + timeout
        while time.time() < deadline:
            for path in (self.home / "mcp").glob("window-*.json"):
                info = read_window_file(path)
                if info is not None:
                    return info
            time.sleep(0.05)
        raise AssertionError("the server wrote no window-<pid>.json")

    def window_client(self) -> WindowClient:
        from jude.mcp.launch import challenge_and_mint

        info = self.window_info()
        url = challenge_and_mint(int(info["port"]), str(info["local_secret"]))
        assert url, "ping/mint challenge failed"
        client = WindowClient(int(info["port"]))
        status, _, _ = client.open(url)
        assert status == 200, status
        assert client.cookie and client.csrf
        return client

    @staticmethod
    def drive_to_approved(
        client: WindowClient,
        review_id: str,
        matter_id: str,
        *,
        suffix: str = ".txt",
        text: str | bytes = FAKE_TEXT,
        timeout: float = 20.0,
        text_read: bool = False,
    ) -> str:
        """Choose the matter, upload, wait for awaiting_review, approve the
        displayed text. Returns the approved sha256."""

        import time

        status, _ = client.post_json(f"/api/r/{review_id}/matter", {"matter_id": matter_id})
        assert status == 200, status
        data = text.encode("utf-8") if isinstance(text, str) else text
        status, _ = client.upload(review_id, suffix, data)
        assert status == 200, status
        deadline = time.time() + timeout
        while True:
            state = client.state(review_id)
            if state["status"] == "awaiting_review":
                break
            assert state["status"] == "preparing", state
            assert time.time() < deadline, state
            time.sleep(0.05)
        frag = client.fragment(review_id)
        sha = re.search(r'data-sha256="([0-9a-f]{64})"', frag).group(1)
        status, obj = client.post_json(
            f"/api/r/{review_id}/approve",
            {"sha256": sha, "attest": True, "text_read": text_read},
        )
        assert status == 200, (status, obj)
        return sha

    @staticmethod
    def wait_for_status(client: WindowClient, review_id: str, wanted: str, timeout: float = 20.0):
        import time

        deadline = time.time() + timeout
        while True:
            state = client.state(review_id)
            if state["status"] == wanted:
                return state
            assert time.time() < deadline, state
            time.sleep(0.05)


@pytest.fixture
def stdio_harness_cls() -> type[StdioHarness]:
    pytest.importorskip("mcp")
    return StdioHarness
