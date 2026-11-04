"""The local review window: one HTTP server bound to 127.0.0.1, one tab.

Hardening (threat table I3):

* bound to ``127.0.0.1:0`` — an ephemeral port, loopback only; the exact
  ``Host`` header is required (DNS rebinding);
* the only way in is a one-shot URL (``/open/<otp>``) minted by the
  server and consumed within ten minutes (two minutes for the terminal
  fallback); it answers a tiny landing page that sets a ``SameSite=Strict``
  ``HttpOnly`` session cookie, hands the session's second secret to the
  page's own origin (``sessionStorage``, which IS scheme+host+port scoped)
  and replaces itself with a clean ``/``, so neither the browser history
  nor a transcript ever carries a token; ``HEAD`` never consumes a token;
* the cookie alone is NOT a credential. Cookies are host-scoped, not
  port-scoped: on a navigation to any other ``127.0.0.1:<port>`` listener
  (``jude ui``, a notebook, a dev server) the browser attaches
  ``jude_session`` to it. So ``GET /`` returns a static shell with no name,
  no review and no token, and every ``/api/*`` request, GET included,
  needs ``X-Jude-CSRF`` — the per-origin secret a bare cookie holder never
  receives; the page fetches its content through those calls;
* every other route answers ``404`` with an empty body unless the cookie
  is valid; ``Sec-Fetch-Site`` is REQUIRED and must be ``same-origin`` or
  ``none`` (``same-site`` is what a page on another loopback port sends);
  ``Origin``, when present, must match; GETs never mutate — a page load is
  not an interaction and never extends a review's clock;
* availability: a small listen backlog, a ceiling on live connections
  (extra ones are closed at accept) and a two-second limit for a connection
  to send its request line, so a local process holding hundreds of idle
  sockets cannot exhaust the server's descriptors; the soft fd limit is
  raised at start as defence in depth;
* the ``Cookie`` header is scanned for the exact ``jude_session`` pair, so
  a malformed sibling cookie stored for 127.0.0.1 by another listener
  cannot hide a valid session;
* nonce'd ``Content-Security-Policy: default-src 'none'``, ``no-store``,
  ``no-referrer``, ``nosniff``, ``DENY`` on every response, including the
  errors the stdlib generates; no ``Server`` header; no inline handlers,
  no inline styles, no external resource; model text is escaped into a
  labelled ``<pre>``;
* ``<title>`` is the static word "Jude"; translate, spellcheck,
  autocomplete and password managers are turned off by markup;
* uploads are raw bodies with the suffix in ``X-Jude-Suffix`` (the file
  name never reaches the server): suffix checked before the body,
  exact-length read, 50 MiB cap, ``413`` closes the connection;
* ``window-<pid>.json`` (mode 0600) lets ``jude mcp open`` find a live
  window and prove it is Jude's through an HMAC challenge
  (``/api/ping``) before asking for a one-shot URL (``/api/mint``);
* ``log_message`` is a no-op: request lines carry the one-shot token.

The sweep (expiry, best-effort prunes, pipeline unload) runs on its own
thread, never on the accept loop.
"""

from __future__ import annotations

import contextlib
import hmac
import html
import json
import logging
import os
import re
import secrets
import socket
import threading
import time
import urllib.parse
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any

from .reviews import (
    MAX_UPLOAD_BYTES,
    PRE_APPROVAL,
    SUPPORTED_SUFFIXES,
    MatterRow,
    Review,
    ReviewError,
    ReviewManager,
    ReviewStatus,
)
from .strings import STRINGS
from .strings import text as _s

log = logging.getLogger("jude.mcp.window")

OTP_TTL = 600.0
OTP_SHORT_TTL = 120.0
SWEEP_INTERVAL = 15.0
STOP_TIMEOUT = 5.0  # seconds stop() gives the serve loop before forcing it
MAX_JSON_BODY = 1024 * 1024
SESSION_COOKIE = "jude_session"
LANG_COOKIE = "jude_lang"
# The sessionStorage key under which the page keeps its per-origin secret.
SESSION_KEY = "jude_csrf"
# Availability (threat table I3 / I7): a connection has IDLE_TIMEOUT seconds
# to send its request line; headers and body reads then get REQUEST_TIMEOUT
# per recv; at most MAX_CONNECTIONS are served at once (the browser uses six
# per host) and the kernel queues at most REQUEST_QUEUE_SIZE more.
IDLE_TIMEOUT = 2.0
REQUEST_TIMEOUT = 10.0
MAX_CONNECTIONS = 32
REQUEST_QUEUE_SIZE = 16
FD_LIMIT_FLOOR = 4096
UI_LANGS: tuple[str, ...] = ("en", "fr")
COUNTDOWN_BELOW = 300

_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_REVIEW_ROUTE = re.compile(
    rf"^/api/r/(?P<id>{_UUID})/"
    r"(?P<action>state|fragment|answers|heartbeat|matter|file|decide|mark|approve|cancel)$"
)
_NONCE_RE = re.compile(r"^[0-9a-f]{16,64}$")
_GET_ACTIONS = frozenset({"state", "fragment", "answers"})

_STATUS_FOR_KEY: dict[str, int] = {
    "unknown_review": 404,
    "unknown_entity": 404,
    "unknown_matter": 404,
    "not_found": 404,
    "illegal_transition": 409,
    "text_changed": 409,
    "expired": 409,
    "not_released": 409,
    "already_released": 409,
    "busy": 409,
    "attestation_required": 400,
    "bad_request": 400,
    "unsupported_suffix": 415,
    "oversize": 413,
    "rate_limited": 429,
}


@dataclass(frozen=True)
class Session:
    token: str
    csrf: str
    created_at: float


def security_headers(nonce: str) -> list[tuple[str, str]]:
    """The headers every response carries. The CSP names no scheme and no
    host: only the keywords and the per-response nonce."""

    csp = (
        "default-src 'none'; "
        f"script-src 'nonce-{nonce}'; "
        f"style-src 'nonce-{nonce}'; "
        "connect-src 'self'; "
        "form-action 'none'; "
        "base-uri 'none'; "
        "frame-ancestors 'none'"
    )
    return [
        ("Content-Security-Policy", csp),
        ("Cache-Control", "no-store"),
        ("Referrer-Policy", "no-referrer"),
        ("X-Content-Type-Options", "nosniff"),
        ("X-Frame-Options", "DENY"),
        ("Cross-Origin-Opener-Policy", "same-origin"),
        ("Cross-Origin-Resource-Policy", "same-origin"),
    ]


class Window:
    """Owns the server thread, the sweep thread, the one-shot tokens, the
    sessions and the ``window-<pid>.json`` state file."""

    def __init__(
        self,
        manager: ReviewManager,
        *,
        now: Callable[[], float] = time.time,
        lang_default: str = "en",
        state_dir: Path | None = None,
        host: str = "127.0.0.1",
        port: int = 0,
        sweep_interval: float = SWEEP_INTERVAL,
        idle_timeout: float = IDLE_TIMEOUT,
        max_connections: int = MAX_CONNECTIONS,
    ) -> None:
        self.manager = manager
        self._now = now
        self.lang_default = lang_default if lang_default in UI_LANGS else "en"
        self._state_dir = state_dir
        self._host = host
        self._port = port
        self.sweep_interval = float(sweep_interval)
        self.idle_timeout = float(idle_timeout)
        self.max_connections = int(max_connections)
        self.local_secret = secrets.token_hex(32)
        self.instance_id = secrets.token_hex(8)
        self._lock = threading.Lock()
        self._otps: dict[str, float] = {}
        self._sessions: dict[str, Session] = {}
        self._used_nonces: set[str] = set()
        self._server: _Server | None = None
        self._thread: threading.Thread | None = None
        self._sweep_thread: threading.Thread | None = None
        self._sweep_stop = threading.Event()
        self._state_file: Path | None = None
        self.sweeps = 0

    # ----- lifecycle -----

    def start(self) -> None:
        if self._server is not None:
            return
        raise_fd_limit()
        self._server = _Server(
            (self._host, self._port),
            _Handler,
            window=self,
            idle_timeout=self.idle_timeout,
            max_connections=self.max_connections,
        )
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            kwargs={"poll_interval": 0.5},
            daemon=True,
            name="jude-window",
        )
        self._thread.start()
        self._write_state_file()
        self._sweep_stop.clear()
        self._sweep_thread = threading.Thread(
            target=self._sweep_loop, daemon=True, name="jude-sweep"
        )
        self._sweep_thread.start()

    def stop(self, timeout: float = STOP_TIMEOUT) -> None:
        """Stop serving; never blocks for more than about ``timeout`` seconds.

        ``BaseServer.shutdown()`` waits for the serve loop with no limit,
        and that loop can wedge inside ``accept()``: ``poll`` reported a
        connection that was gone before ``accept`` ran (BSD/macOS drop it
        from the queue and ``accept`` blocks for the next one). That once
        held a SIGTERM for ever. The shutdown request therefore runs on a
        helper thread; when it has not returned in time, one loopback
        connect completes the blocked ``accept`` so the loop sees the
        request, and the listening socket is closed regardless."""

        self._sweep_stop.set()
        server, self._server = self._server, None
        forced = False
        if server is not None:
            helper = threading.Thread(
                target=server.shutdown, daemon=True, name="jude-window-stop"
            )
            helper.start()
            helper.join(timeout=max(0.0, timeout))
            if helper.is_alive():
                forced = True
                log.warning("window serve loop did not stop in time; forcing")
                _poke(server.server_address)
                helper.join(timeout=1.0)
            server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=1.0 if forced else 5.0)
            self._thread = None
        if self._sweep_thread is not None:
            self._sweep_thread.join(timeout=5)
            self._sweep_thread = None
        if self._state_file is not None:
            with contextlib.suppress(OSError):
                self._state_file.unlink()
            self._state_file = None

    @property
    def server(self) -> _Server:
        assert self._server is not None, "window not started"
        return self._server

    @property
    def port(self) -> int:
        return int(self.server.server_address[1])

    @property
    def host_header(self) -> str:
        return f"{self._host}:{self.port}"

    @property
    def origin(self) -> str:
        return f"http://{self.host_header}"

    def _write_state_file(self) -> None:
        if self._state_dir is None:
            return
        self._state_dir.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(OSError):
            os.chmod(self._state_dir, 0o700)
        path = self._state_dir / f"window-{os.getpid()}.json"
        payload = json.dumps(
            {
                "pid": os.getpid(),
                "port": self.port,
                "local_secret": self.local_secret,
                "started_at": self._now(),
                "instance_id": self.instance_id,
            }
        ).encode("utf-8")
        tmp = path.with_suffix(".json.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(fd, payload)
        finally:
            os.close(fd)
        os.replace(tmp, path)
        os.chmod(path, 0o600)
        self._state_file = path

    @property
    def state_file(self) -> Path | None:
        return self._state_file

    # ----- tokens and sessions -----

    def mint_url(self, ttl: float = OTP_TTL) -> str:
        otp = secrets.token_urlsafe(32)
        now = self._now()
        with self._lock:
            self._otps = {k: v for k, v in self._otps.items() if v > now}
            self._otps[otp] = now + float(ttl)
        return f"{self.origin}/open/{otp}"

    def consume_otp(self, otp: str) -> bool:
        now = self._now()
        with self._lock:
            expires = self._otps.pop(otp, None)
        return expires is not None and expires > now

    def new_session(self) -> Session:
        session = Session(
            token=secrets.token_urlsafe(32),
            csrf=secrets.token_urlsafe(32),
            created_at=self._now(),
        )
        with self._lock:
            self._sessions[session.token] = session
        return session

    def session_from_cookie(self, cookie_header: str | None) -> Session | None:
        presented = cookie_value(cookie_header, SESSION_COOKIE)
        if presented is None:
            return None
        with self._lock:
            for token, session in self._sessions.items():
                if hmac.compare_digest(token, presented):
                    return session
        return None

    def ping_mac(self, nonce: str) -> str:
        return hmac.new(self.local_secret.encode(), b"ping:" + nonce.encode(), sha256).hexdigest()

    def query_mac(self, nonce: str) -> str:
        """What a caller must present with its ping nonce to learn
        ``has_review``: proof that it holds ``local_secret``."""

        return hmac.new(self.local_secret.encode(), b"query:" + nonce.encode(), sha256).hexdigest()

    def check_query(self, nonce: str, proof: str | None) -> bool:
        if not isinstance(proof, str) or not proof:
            return False
        return hmac.compare_digest(self.query_mac(nonce), proof)

    def mint_mac(self, nonce: str) -> str:
        return hmac.new(self.local_secret.encode(), b"mint:" + nonce.encode(), sha256).hexdigest()

    def check_mint(self, nonce: str, mac: str) -> bool:
        if not isinstance(nonce, str) or not isinstance(mac, str) or not _NONCE_RE.match(nonce):
            return False
        expected = self.mint_mac(nonce)
        with self._lock:
            if nonce in self._used_nonces:
                return False
            ok = hmac.compare_digest(expected, mac)
            if ok:
                self._used_nonces.add(nonce)
                if len(self._used_nonces) > 10_000:
                    self._used_nonces.clear()
        return ok

    def has_review(self) -> bool:
        """A boolean for an authenticated ``/api/ping``: is there a review
        the lawyer may want to see (pre-approval or approved)? Nothing else,
        and never to a caller that has not proven it holds the local
        secret — otherwise any local process could poll it and learn when a
        confidential document is under review."""

        return any(
            r.status in PRE_APPROVAL or r.status == ReviewStatus.APPROVED
            for r in self.manager.reviews()
        )

    # ----- periodic -----

    def sweep_once(self) -> None:
        try:
            self.manager.sweep()
            self.sweeps += 1
        except Exception:
            log.error("sweep failed", exc_info=True)

    def _sweep_loop(self) -> None:
        while not self._sweep_stop.wait(self.sweep_interval):
            self.sweep_once()


def cookie_value(cookie_header: str | None, name: str) -> str | None:
    """The value of cookie ``name`` from a raw ``Cookie`` header, found by a
    tolerant scan: split on ``;`` and match the exact name. The loopback
    cookie jar is shared by every 127.0.0.1 port, so one malformed sibling
    cookie stored by another listener must not hide a valid session (the
    stdlib's ``SimpleCookie.load`` rejects the whole header)."""

    if not cookie_header:
        return None
    for part in cookie_header.split(";"):
        key, sep, value = part.strip().partition("=")
        if sep and key.strip() == name:
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] == '"':
                value = value[1:-1]
            return value or None
    return None


def raise_fd_limit(floor: int = FD_LIMIT_FLOOR) -> None:
    """Defence in depth against descriptor exhaustion: a server spawned by
    Claude Desktop inherits launchd's soft limit (256 on macOS). Raise the
    soft limit towards ``floor``, never above the hard limit; silently keep
    what we have when the platform refuses."""

    try:
        import resource
    except ImportError:  # pragma: no cover — Windows
        return
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        if soft == resource.RLIM_INFINITY or soft >= floor:
            return
        target = floor if hard == resource.RLIM_INFINITY else min(floor, hard)
        if target > soft:
            resource.setrlimit(resource.RLIMIT_NOFILE, (target, hard))
    except (ValueError, OSError):
        pass


def _poke(address: Any) -> None:
    """Connect once to the listening socket and close: a serve loop blocked
    in ``accept()`` returns and re-reads the shutdown flag. Loopback only,
    so the network tripwire lets it through."""

    host, port = address[0], int(address[1])
    with contextlib.suppress(OSError), socket.create_connection((host, port), timeout=1.0):
        pass


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False
    request_queue_size = REQUEST_QUEUE_SIZE

    def __init__(
        self,
        addr: tuple[str, int],
        handler: type[BaseHTTPRequestHandler],
        *,
        window: Window,
        idle_timeout: float = IDLE_TIMEOUT,
        max_connections: int = MAX_CONNECTIONS,
    ) -> None:
        self.window = window
        self.idle_timeout = float(idle_timeout)
        self.max_connections = int(max_connections)
        self._live = 0
        self._live_lock = threading.Lock()
        super().__init__(addr, handler)

    @property
    def live_connections(self) -> int:
        with self._live_lock:
            return self._live

    # ----- the connection ceiling -----
    # verify_request runs on the accept loop before a handler thread exists:
    # beyond the ceiling the socket is closed at once (shutdown_request) and
    # pins nothing. The slot is given back when the handler thread ends.

    def verify_request(self, request: Any, client_address: Any) -> bool:
        with self._live_lock:
            if self._live >= self.max_connections:
                return False
            self._live += 1
        return True

    def _release_slot(self) -> None:
        with self._live_lock:
            self._live = max(0, self._live - 1)

    def process_request(self, request: Any, client_address: Any) -> None:
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._release_slot()
            raise

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._release_slot()

    def handle_error(self, request: Any, client_address: Any) -> None:
        # The stdlib prints the client address and a traceback to stderr;
        # ours goes to the trace through the logger, like every other error.
        log.error("connection handler failed", exc_info=True)


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = ""
    sys_version = ""
    timeout = REQUEST_TIMEOUT

    # A connection that sends no request line within the server's
    # idle_timeout is dropped (the stdlib turns the TimeoutError into
    # close_connection); once the request line is in, the regular per-recv
    # timeout applies to headers and body.
    def handle_one_request(self) -> None:
        self.connection.settimeout(self.server.idle_timeout)  # type: ignore[attr-defined]
        super().handle_one_request()

    def parse_request(self) -> bool:
        self.connection.settimeout(self.timeout)
        return super().parse_request()

    # Request lines carry the one-shot token; nothing about a request is
    # logged, to stderr or anywhere else.
    def log_message(self, format: str, *args: Any) -> None:
        return

    def log_error(self, format: str, *args: Any) -> None:
        return

    # No ``Server`` header on any response: a port scan does not learn
    # what listens here.
    def version_string(self) -> str:
        return ""

    def send_response(self, code: int, message: str | None = None) -> None:
        self.send_response_only(code, message)
        self.send_header("Date", self.date_time_string())

    def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
        """The stdlib's errors (malformed request line, 414, 501, 505) go
        through ``_respond``: security headers, empty body, never the HTML
        page that reflects request tokens."""

        self._nonce = getattr(self, "_nonce", None) or secrets.token_urlsafe(16)
        if getattr(self, "request_version", "HTTP/0.9") == "HTTP/0.9":
            # The stdlib answers a malformed request line in HTTP/0.9, i.e.
            # without any header; answer in 1.1 so the headers go out.
            self.request_version = "HTTP/1.1"
        self._respond(int(code), close=True)

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_HEAD(self) -> None:
        self._dispatch("HEAD")

    def do_PUT(self) -> None:
        self._dispatch("PUT")

    def do_DELETE(self) -> None:
        self._dispatch("DELETE")

    def do_PATCH(self) -> None:
        self._dispatch("PATCH")

    def do_OPTIONS(self) -> None:
        self._dispatch("OPTIONS")

    # ----- plumbing -----

    @property
    def window(self) -> Window:
        return self.server.window  # type: ignore[attr-defined]

    def _respond(
        self,
        status: int,
        body: bytes = b"",
        ctype: str | None = None,
        *,
        close: bool = False,
        headers: list[tuple[str, str]] | None = None,
    ) -> None:
        self.send_response(status)
        for name, value in security_headers(self._nonce):
            self.send_header(name, value)
        if ctype:
            self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if close:
            self.send_header("Connection", "close")
            self.close_connection = True
        for name, value in headers or []:
            self.send_header(name, value)
        self.end_headers()
        if body and self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, obj: Any, *, close: bool = False) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._respond(status, body, "application/json; charset=utf-8", close=close)

    def _html(self, status: int, markup: str) -> None:
        self._respond(status, markup.encode("utf-8"), "text/html; charset=utf-8")

    def _error(self, exc: ReviewError) -> None:
        self._json(_STATUS_FOR_KEY.get(exc.key, 400), {"error": exc.key})

    def _content_length(self) -> int | None:
        raw = self.headers.get("Content-Length")
        if raw is None:
            return None
        try:
            n = int(raw)
        except ValueError:
            return None
        return n if n >= 0 else None

    def _read_exact(self, n: int) -> bytes | None:
        buf = bytearray()
        while len(buf) < n:
            chunk = self.rfile.read(n - len(buf))
            if not chunk:
                return None
            buf.extend(chunk)
        return bytes(buf)

    def _read_json(self) -> dict[str, Any] | None:
        ctype = self.headers.get("Content-Type", "")
        if not ctype.lower().startswith("application/json"):
            self._respond(415, close=True)
            return None
        length = self._content_length()
        if length is None:
            self._respond(411, close=True)
            return None
        if length > MAX_JSON_BODY:
            self._respond(413, close=True)
            return None
        body = self._read_exact(length)
        if body is None:
            self._respond(400, close=True)
            return None
        try:
            obj = json.loads(body.decode("utf-8")) if body else {}
        except (ValueError, UnicodeDecodeError):
            self._respond(400)
            return None
        if not isinstance(obj, dict):
            self._respond(400)
            return None
        return obj

    def _lang(self) -> str:
        value = cookie_value(self.headers.get("Cookie"), LANG_COOKIE)
        if value in UI_LANGS:
            return value
        return negotiate_lang(self.headers.get("Accept-Language"), self.window.lang_default)

    # ----- dispatch -----

    def _dispatch(self, method: str) -> None:
        self._nonce = secrets.token_urlsafe(16)
        w = self.window
        try:
            # 1. exact Host
            if self.headers.get("Host") != w.host_header:
                self._respond(400, close=True)
                return
            path, _, query = self.path.partition("?")
            # 2. unauthenticated routes
            if path.startswith("/open/"):
                self._route_open(method, path[len("/open/") :])
                return
            if path == "/api/ping":
                self._route_ping(method, query)
                return
            if path == "/api/mint":
                self._route_mint(method)
                return
            # 3. session cookie
            session = w.session_from_cookie(self.headers.get("Cookie"))
            if session is None:
                self._respond(404, close=True)
                return
            # 4. Sec-Fetch-Site required; Origin must match when present
            fetch_site = self.headers.get("Sec-Fetch-Site")
            if fetch_site not in ("same-origin", "none"):
                self._respond(403, close=True)
                return
            origin = self.headers.get("Origin")
            if origin is not None and origin != w.origin:
                self._respond(403, close=True)
                return
            # 5. CSRF on every API call, GETs included
            if path.startswith("/api/") and not self._csrf_ok(session):
                return
            # 6. method and route
            if path == "/":
                if method not in ("GET", "HEAD"):
                    self._respond(405, close=True, headers=[("Allow", "GET, HEAD")])
                    return
                self._route_page(session)
                return
            if path == "/api/current":
                if method != "GET":
                    self._respond(405, close=True, headers=[("Allow", "GET")])
                    return
                self._json(200, w.manager.current())
                return
            if path == "/api/lang":
                if method != "POST":
                    self._respond(405, close=True, headers=[("Allow", "POST")])
                    return
                self._route_lang()
                return
            m = _REVIEW_ROUTE.match(path)
            if m is None:
                self._respond(404, close=True)
                return
            review_id, action = m.group("id"), m.group("action")
            if action in _GET_ACTIONS:
                if method != "GET":
                    self._respond(405, close=True, headers=[("Allow", "GET")])
                    return
            elif method != "POST":
                self._respond(405, close=True, headers=[("Allow", "POST")])
                return
            try:
                getattr(self, f"_route_{action}")(session, review_id)
            except ReviewError as exc:
                self._error(exc)
        except (TimeoutError, ConnectionError, BrokenPipeError):
            self.close_connection = True
        except Exception:
            log.error("request failed", exc_info=True)
            try:
                self._respond(500, close=True)
            except Exception:
                self.close_connection = True

    def _csrf_ok(self, session: Session) -> bool:
        presented = self.headers.get("X-Jude-CSRF", "")
        if not hmac.compare_digest(presented, session.csrf):
            self._respond(403, close=True)
            return False
        return True

    # ----- unauthenticated routes -----

    def _route_open(self, method: str, otp: str) -> None:
        w = self.window
        if method == "HEAD":
            # Link checkers and antivirus scanners issue HEAD: never burn the token.
            self._respond(405, close=True, headers=[("Allow", "GET")])
            return
        if method != "GET":
            self._respond(404, close=True)
            return
        if otp and w.consume_otp(otp):
            session = w.new_session()
            cookie = f"{SESSION_COOKIE}={session.token}; Path=/; HttpOnly; SameSite=Strict"
            # The landing page: it stores the per-origin secret in this
            # origin's sessionStorage and replaces itself with "/". The
            # secret travels once, in this body, to this origin only — never
            # in a cookie (shared across loopback ports) nor in a URL.
            self._respond(
                200,
                render_landing(self._nonce, session.csrf).encode("utf-8"),
                "text/html; charset=utf-8",
                headers=[("Set-Cookie", cookie)],
            )
            return
        if w.session_from_cookie(self.headers.get("Cookie")) is not None:
            self._respond(303, headers=[("Location", "/")])
            return
        self._respond(404, close=True)

    def _route_ping(self, method: str, query: str) -> None:
        if method != "GET":
            self._respond(404, close=True)
            return
        params = urllib.parse.parse_qs(query)
        nonce = (params.get("nonce") or [""])[0]
        if not _NONCE_RE.match(nonce):
            self._respond(404, close=True)
            return
        answer: dict[str, Any] = {"mac": self.window.ping_mac(nonce)}
        # has_review only for a caller that proves it holds the local secret
        # (jude mcp open); a bare nonce learns the server's identity, no more.
        if self.window.check_query(nonce, (params.get("proof") or [None])[0]):
            answer["has_review"] = self.window.has_review()
        self._json(200, answer)

    def _route_mint(self, method: str) -> None:
        if method != "POST":
            self._respond(404, close=True)
            return
        ctype = self.headers.get("Content-Type", "")
        length = self._content_length()
        if not ctype.lower().startswith("application/json") or length is None or length > 4096:
            self._respond(404, close=True)
            return
        body = self._read_exact(length)
        try:
            obj = json.loads(body.decode("utf-8")) if body else None
        except (ValueError, UnicodeDecodeError):
            obj = None
        if not isinstance(obj, dict) or not self.window.check_mint(
            obj.get("nonce", ""), obj.get("mac", "")
        ):
            self._respond(404, close=True)
            return
        ttl = OTP_SHORT_TTL if obj.get("ttl") == "short" else OTP_TTL
        self._json(200, {"url": self.window.mint_url(ttl)})

    # ----- authenticated routes -----

    def _route_page(self, session: Session) -> None:
        # The shell only: no review, no name, no token, no manager call. The
        # page fetches its content through /api/* with the per-origin
        # secret, so a bare cookie (which every loopback port receives)
        # yields nothing, and a page load never touches a review's clock.
        self._html(200, render_page(self._lang(), self._nonce))

    def _route_lang(self) -> None:
        obj = self._read_json()
        if obj is None:
            return
        lang = obj.get("lang")
        if lang not in UI_LANGS:
            self._respond(400)
            return
        cookie = f"{LANG_COOKIE}={lang}; Path=/; SameSite=Strict"
        body = json.dumps({"lang": lang}).encode("utf-8")
        self._respond(
            200, body, "application/json; charset=utf-8", headers=[("Set-Cookie", cookie)]
        )

    def _route_state(self, session: Session, review_id: str) -> None:
        self._json(200, self.window.manager.window_state(review_id))

    def _route_fragment(self, session: Session, review_id: str) -> None:
        self._html(200, self._fragment(review_id))

    def _route_answers(self, session: Session, review_id: str) -> None:
        review = self.window.manager.get(review_id)
        self._html(200, render_answers(self._lang(), review))

    def _route_heartbeat(self, session: Session, review_id: str) -> None:
        obj = self._read_json()
        if obj is None:
            return
        self._json(200, self.window.manager.heartbeat(review_id))

    def _route_matter(self, session: Session, review_id: str) -> None:
        obj = self._read_json()
        if obj is None:
            return
        matter_id = obj.get("matter_id")
        if not isinstance(matter_id, str) or not matter_id:
            self._respond(400)
            return
        self.window.manager.choose_matter(review_id, matter_id)
        self._html(200, self._fragment(review_id))

    def _route_file(self, session: Session, review_id: str) -> None:
        w = self.window
        ctype = self.headers.get("Content-Type", "")
        if not ctype.lower().startswith("application/octet-stream"):
            self._respond(415, close=True)
            return
        # The page derives the suffix from file.name client-side; the file
        # name itself never reaches the server, not even in a header.
        suffix = self.headers.get("X-Jude-Suffix", "").strip().lower()
        if suffix not in SUPPORTED_SUFFIXES:
            # Refused before the body is read.
            self._json(415, {"error": "unsupported_suffix"}, close=True)
            return
        length = self._content_length()
        if length is None:
            self._respond(411, close=True)
            return
        if length > MAX_UPLOAD_BYTES:
            self._json(413, {"error": "oversize"}, close=True)
            return
        data = self._read_exact(length)
        if data is None:
            self._respond(400, close=True)
            return
        w.manager.attach_file(review_id, suffix, data)
        self._json(200, {"status": ReviewStatus.PREPARING.value})

    def _route_decide(self, session: Session, review_id: str) -> None:
        obj = self._read_json()
        if obj is None:
            return
        entity_id = obj.get("entity_id")
        action = obj.get("action")
        if not isinstance(entity_id, int) or action not in ("keep", "hide"):
            self._respond(400)
            return
        self.window.manager.decide(review_id, entity_id, action)
        self._html(200, self._fragment(review_id))

    def _route_mark(self, session: Session, review_id: str) -> None:
        obj = self._read_json()
        if obj is None:
            return
        surface = obj.get("surface")
        etype = obj.get("type")
        if not isinstance(surface, str) or not isinstance(etype, str):
            self._respond(400)
            return
        try:
            self.window.manager.mark(review_id, surface, etype)
        except ValueError:
            self._respond(400)
            return
        self._html(200, self._fragment(review_id))

    def _route_approve(self, session: Session, review_id: str) -> None:
        obj = self._read_json()
        if obj is None:
            return
        digest = obj.get("sha256")
        attest = obj.get("attest")
        text_read = obj.get("text_read")
        if not isinstance(digest, str):
            self._respond(400)
            return
        review = self.window.manager.approve(
            review_id,
            digest,
            attest=attest is True,
            text_read=text_read is True,
            ui_lang=self._lang(),
        )
        self._json(200, {"status": review.status.value, "sha256": review.payload_sha256})

    def _route_cancel(self, session: Session, review_id: str) -> None:
        obj = self._read_json()
        if obj is None:
            return
        review = self.window.manager.cancel(review_id)
        self._json(200, {"status": review.status.value, "outcome": review.outcome})

    def _fragment(self, review_id: str) -> str:
        w = self.window
        review = w.manager.get(review_id)
        matters: list[MatterRow] = []
        if review.status in (ReviewStatus.AWAITING_MATTER, ReviewStatus.AWAITING_FILE):
            matters = w.manager.matters_for_window()
        return render_fragment(self._lang(), review, matters)


# ----- language -----


def negotiate_lang(accept_language: str | None, default: str) -> str:
    """Pick ``fr`` or ``en`` from an Accept-Language header by q-value;
    anything else falls back to ``default``."""

    if not accept_language:
        return default
    best: tuple[float, str] | None = None
    for item in accept_language.split(","):
        parts = [p.strip() for p in item.split(";")]
        tag = parts[0].lower().split("-")[0]
        q = 1.0
        for p in parts[1:]:
            if p.startswith("q="):
                try:
                    q = float(p[2:])
                except ValueError:
                    q = 0.0
        if tag in UI_LANGS and q > 0 and (best is None or q > best[0]):
            best = (q, tag)
    return best[1] if best else default


# ----- rendering -----

_E = html.escape


def _t(key: str, lang: str) -> str:
    return _E(_s(key, lang))


_ASSETS = files("jude.mcp") / "assets"


@cache
def _asset(name: str) -> str:
    """The page's stylesheet and script, shipped as package data and inlined
    behind the per-response nonce (no external resource is ever loaded)."""

    return (_ASSETS / name).read_text(encoding="utf-8")


_JS_KEYS = (
    "banner.server_gone",
    "ui.no_session",
    "ui.text_changed",
    "ui.nothing_left",
    "ui.status.handed_once",
    "ui.show_original",
    "ui.show_leaving",
    "ui.show_invisible",
    "ui.hide_invisible",
    "ui.expires_in",
    "ui.too_late",
)


def _js_strings(lang: str) -> str:
    keys = [k for k in STRINGS if k.startswith("ui.error.") or k in _JS_KEYS]
    table = {k: _s(k, lang) for k in keys}
    table["ui.error.text_changed"] = _s("ui.text_changed", lang)
    return json.dumps(table, ensure_ascii=False).replace("</", "<\\/")


def render_landing(nonce: str, csrf: str) -> str:
    """The one-shot URL's answer: a static page that hands the session's
    per-origin secret to ``sessionStorage`` of this origin (scheme, host AND
    port) and replaces itself with ``/``. Nothing else is on it."""

    return (
        "<!doctype html>\n"
        '<html lang="en" translate="no">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="referrer" content="no-referrer">\n'
        '<meta name="robots" content="noindex, nofollow">\n'
        "<title>Jude</title>\n"
        "</head>\n"
        f'<body data-csrf="{_E(csrf)}">\n'
        "<p>Jude</p>\n"
        f'<script nonce="{nonce}">(function(){{var k=document.body.getAttribute("data-csrf");'
        f'try{{sessionStorage.setItem("{SESSION_KEY}",k);}}catch(e){{}}'
        'document.body.removeAttribute("data-csrf");location.replace("/");})();</script>\n'
        "</body>\n</html>\n"
    )


def render_page(lang: str, nonce: str) -> str:
    """The shell every ``GET /`` returns: ``<head>`` static apart from the
    nonce, the title the word Jude, an empty status line, the "no review"
    screen and the script. No review, no name, no token: the script reads
    the per-origin secret from ``sessionStorage`` and fetches the current
    review through ``/api/*``. A bare cookie holder gets exactly this."""

    fragment = render_fragment(lang, None, [])
    script = _asset("window.js").replace("__STRINGS__", _js_strings(lang))
    lang_buttons = "".join(
        f'<button data-action="lang" data-lang="{code}">{_t(f"ui.lang.{code}", lang)}</button>'
        for code in UI_LANGS
    )
    return (
        "<!doctype html>\n"
        f'<html lang="{_E(lang)}" translate="no">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="google" content="notranslate">\n'
        '<meta name="referrer" content="no-referrer">\n'
        '<meta name="robots" content="noindex, nofollow">\n'
        "<title>Jude</title>\n"
        f'<style nonce="{nonce}">{_asset("window.css")}</style>\n'
        "</head>\n"
        f'<body data-lang="{_E(lang)}" data-session-key="{SESSION_KEY}">\n'
        '<header class="top"><span class="brand">Jude</span>'
        '<span id="status-line" class="status-line"></span>'
        f'<span class="lang">{lang_buttons}</span></header>\n'
        '<div id="banner" class="banner hidden"></div>\n'
        f'<main id="screen">{fragment}</main>\n'
        f'<script nonce="{nonce}">{script}</script>\n'
        "</body>\n</html>\n"
    )


def render_fragment(lang: str, review: Review | None, matters: list[MatterRow]) -> str:
    if review is None:
        return (
            '<section class="screen" data-status="none">'
            f"<h1>Jude</h1><p>{_t('ui.start_from_claude', lang)}</p></section>"
        )
    status = review.status
    if status == ReviewStatus.AWAITING_MATTER:
        return _screen_matter(lang, review, matters)
    if status == ReviewStatus.AWAITING_FILE:
        return _screen_file(lang, review, matters)
    if status == ReviewStatus.PREPARING:
        return _screen_preparing(lang, review)
    if status == ReviewStatus.AWAITING_REVIEW:
        return _screen_review(lang, review)
    if status == ReviewStatus.APPROVED:
        return _screen_approved(lang, review)
    if status == ReviewStatus.RELEASED:
        return _screen_released(lang, review)
    return _screen_closed(lang, review)


_INPUT_ATTRS = (
    'spellcheck="false" autocomplete="off" autocapitalize="off" autocorrect="off" '
    'data-1p-ignore data-lpignore="true" data-bwignore'
)


def _countdown(lang: str) -> str:
    return (
        '<p id="countdown" class="countdown muted hidden">'
        f"<span>{_t('ui.expires_in', lang)}</span> <span id=\"countdown-value\"></span></p>"
    )


def _cancel_button(lang: str) -> str:
    return f'<button data-action="cancel">{_t("ui.cancel", lang)}</button>'


def _matter_select(lang: str, review: Review, matters: list[MatterRow]) -> str:
    if not matters:
        return f"<p class=\"notice\">{_t('ui.no_matters', lang)}</p>"
    options = []
    zr = _s("ui.zr_tag", lang)
    for m in matters:
        selected = " selected" if m.id == review.matter_id else ""
        label = f"{m.name} · {m.mode}" + (f" · {zr}" if m.attested else "")
        options.append(f'<option value="{_E(m.id)}"{selected}>{_E(label)}</option>')
    return (
        f'<label for="matter">{_t("ui.matter", lang)}</label> '
        f'<select id="matter" {_INPUT_ATTRS}>{"".join(options)}</select>'
    )


def _screen_matter(lang: str, review: Review, matters: list[MatterRow]) -> str:
    return (
        f'<section class="screen" data-status="{review.status.value}">'
        f"<h1>{_t('ui.choose_matter', lang)}</h1>"
        f"<p>{_matter_select(lang, review, matters)}</p>"
        '<p class="row">'
        f'<button class="primary" data-action="choose-matter">{_t("ui.continue", lang)}</button>'
        f"{_cancel_button(lang)}</p>"
        f"{_countdown(lang)}"
        '<p id="error" class="error hidden"></p>'
        "</section>"
    )


def _smart_notice(lang: str, review: Review) -> str:
    if review.mode_notice == "smart_fallback":
        return f"<p class=\"notice\">{_t('ui.smart_fallback', lang)}</p>"
    return ""


def _screen_file(lang: str, review: Review, matters: list[MatterRow]) -> str:
    return (
        f'<section class="screen" data-status="{review.status.value}">'
        f"<h1>{_t('ui.choose_file', lang)}</h1>"
        f"<p>{_matter_select(lang, review, matters)} "
        f'<button data-action="choose-matter">{_t("ui.change_matter", lang)}</button></p>'
        f"{_smart_notice(lang, review)}"
        f"<p class=\"muted\">{_t('ui.file_hint', lang)}</p>"
        f'<p><input type="file" id="file" accept=".txt,.md,.docx,.pdf,.xlsx" {_INPUT_ATTRS}></p>'
        '<p class="row">'
        f'<button class="primary" data-action="upload">{_t("ui.prepare", lang)}</button>'
        f"{_cancel_button(lang)}</p>"
        f"{_countdown(lang)}"
        '<p id="error" class="error hidden"></p>'
        "</section>"
    )


def _screen_preparing(lang: str, review: Review) -> str:
    phase = review.phase or "reading"
    phase_text = _t(f"ui.phase.{phase}", lang) if f"ui.phase.{phase}" in STRINGS else ""
    return (
        f'<section class="screen" data-status="{review.status.value}" data-phase="{_E(phase)}">'
        f"<h1>{_t('ui.preparing', lang)}</h1><div class=\"spinner\"></div>"
        f'<p class="phase muted">{phase_text}</p>'
        f'<p class="row">{_cancel_button(lang)}</p>'
        '<p id="error" class="error hidden"></p>'
        "</section>"
    )


def _escape_with_invisible(text: str, base: int, invisible: set[int]) -> str:
    """Escape ``text`` (which starts at offset ``base`` of the leaving text)
    and append a ``<mark class="inv">U+XXXX</mark>`` label after every
    invisible character. The label is display-only, shown by a CSS class."""

    if not invisible:
        return _E(text)
    parts: list[str] = []
    cursor = 0
    for i, c in enumerate(text):
        if base + i in invisible:
            parts.append(_E(text[cursor : i + 1]))
            parts.append(f'<mark class="inv">U+{ord(c):04X}</mark>')
            cursor = i + 1
    parts.append(_E(text[cursor:]))
    return "".join(parts)


def _marked_text(
    text: str,
    segments: Iterable[Any],
    invisible: Iterable[int] = (),
    kept: Iterable[Any] = (),
) -> str:
    """Escape the outgoing text and wrap each emitted pseudonym in
    ``<mark class="h">`` and each occurrence the lawyer keeps in clear —
    alias forms included — in ``<mark class="kept">``, so an un-redaction
    is never indistinguishable from prose in the text that is attested.
    Offsets refer to the plain (leaving) text."""

    inv = set(invisible)
    spans = [(seg.red_start, seg.red_end, "h") for seg in segments]
    spans.extend((seg.red_start, seg.red_end, "kept") for seg in kept)
    parts: list[str] = []
    cursor = 0
    for start, end, klass in sorted(spans):
        if start < cursor:
            continue
        parts.append(_escape_with_invisible(text[cursor:start], cursor, inv))
        parts.append(f'<mark class="{klass}">{_E(text[start:end])}</mark>')
        cursor = end
    parts.append(_escape_with_invisible(text[cursor:], cursor, inv))
    return "".join(parts)


def _original_text(text: str, segments: Iterable[Any], kept: Iterable[Any] = ()) -> str:
    """The original text with the replaced spans (``raw``) and the spans
    kept in clear (``kept``) marked."""

    spans = [(seg.raw_start, seg.raw_end, "raw") for seg in segments]
    spans.extend((seg.raw_start, seg.raw_end, "kept") for seg in kept)
    parts: list[str] = []
    cursor = 0
    for start, end, klass in sorted(spans):
        if start < cursor:
            continue
        parts.append(_E(text[cursor:start]))
        parts.append(f'<mark class="{klass}">{_E(text[start:end])}</mark>')
        cursor = end
    parts.append(_E(text[cursor:]))
    return "".join(parts)


def _kind(entity_type: str, lang: str) -> str:
    key = f"ui.kind.{entity_type}"
    return _E(_s(key, lang)) if key in STRINGS else _E(entity_type.lower())


def _languages_line(lang: str, review: Review) -> str:
    if not review.languages:
        return ""
    known = {k: v for k, v in review.languages.items() if k != "und"}
    total = sum(known.values())
    bits = [
        f"{_E(code)} {round(100 * n / total)} %"
        for code, n in sorted(known.items(), key=lambda kv: -kv[1])
    ] if total else []
    und = review.languages.get("und", 0)
    if und:
        bits.append(f"{_t('ui.undetermined', lang)} {und}")
    return f"<p class=\"languages muted\">{_t('ui.languages', lang)} {' · '.join(bits)}</p>"


def _risk_block(lang: str, review: Review) -> str:
    rendering = review.rendering
    assert rendering is not None
    lines: list[str] = []
    for a in rendering.risks[:3]:
        level = a.level.value
        reasons = _E(" ".join(a.reasons))
        lines.append(
            f'<p class="risk-{level}">● {_t(f"ui.risk.{level}", lang)} — '
            f"<code>{_E(a.pseudonym)}</code>: {reasons}</p>"
        )
    if review.unmodelled:
        codes = ", ".join(_E(c) for c in review.unmodelled)
        lines.append(
            f'<p class="risk-high">● {_t("ui.risk.high", lang)} — '
            f"{_t('ui.risk.language_unmodelled', lang)} {codes}</p>"
        )
    if rendering.invisible:
        lines.append(
            f'<p class="risk-high">● {_t("ui.risk.high", lang)} — '
            f"{_t('ui.invisible_chars', lang)} ({len(rendering.invisible)}) "
            f'<button class="link" data-action="toggle-invisible" '
            f'data-label-on="{_t("ui.hide_invisible", lang)}" '
            f'data-label-off="{_t("ui.show_invisible", lang)}">'
            f"{_t('ui.show_invisible', lang)}</button></p>"
        )
    if not lines:
        lines.append(f"<p class=\"muted\">{_t('ui.risk.none', lang)}</p>")
    return f'<section class="risk"><h2>{_t("ui.risk.lead", lang)}</h2>{"".join(lines)}</section>'


def _screen_review(lang: str, review: Review) -> str:
    rendering = review.rendering
    assert rendering is not None
    rows = []
    for e in rendering.entities:
        tags = ""
        if e.is_new:
            tags += f'<span class="tag">{_t("ui.new", lang)}</span>'
        if e.user_marked:
            tags += f'<span class="tag">{_t("ui.user_marked", lang)}</span>'
        if e.kept:
            sent_as = f"<em>{_t('ui.kept_marker', lang)}</em>"
            button = (
                f'<button data-action="decide" data-entity="{e.entity_id}" '
                f'data-decision="hide">{_t("ui.hide", lang)}</button>'
            )
            klass = "kept"
        else:
            sent_as = f"<code>{_E(e.pseudonym)}</code>"
            button = (
                f'<button data-action="decide" data-entity="{e.entity_id}" '
                f'data-decision="keep">{_t("ui.keep", lang)}</button>'
            )
            klass = "hidden-row"
        rows.append(
            f'<tr class="{klass}" data-entity="{e.entity_id}">'
            f'<td class="real">{_E(e.canonical)}{tags}</td>'
            f'<td class="pseudo">{sent_as}</td>'
            f"<td>{_kind(e.entity_type, lang)}</td>"
            f"<td>{e.count}</td><td>{button}</td></tr>"
        )
    warnings = "".join(
        f"<p class=\"notice warn\">{_t(f'ui.warn.{key}', lang)}</p>"
        for key in review.warnings
        if f"ui.warn.{key}" in STRINGS
    )
    kinds = "".join(
        f'<option value="{k}">{_kind(k, lang)}</option>'
        for k in ("PERSON", "ORG", "LOC", "EMAIL", "PHONE", "IBAN", "CASE_REF", "URL", "OTHER")
    )
    counts = (
        f"{rendering.n_hidden} {_t('ui.hidden', lang)} → {rendering.n_pseudonyms} "
        f"{_t('ui.pseudonyms', lang)} · {rendering.n_kept} {_t('ui.kept_visible', lang)} · "
        f"{len(rendering.text)} {_t('ui.chars', lang)}"
    )
    invisible_offsets = [i for i, _label in rendering.invisible]
    return (
        f'<section class="screen" data-status="{review.status.value}" '
        f'data-sha256="{_E(rendering.sha256)}">'
        f"<h1>{_t('ui.what_leaves', lang)}</h1>"
        f"<p class=\"dest\">{_t('ui.destination', lang)}</p>"
        f"{warnings}"
        f"<p class=\"counts\">{counts}</p>"
        f"{_languages_line(lang, review)}"
        f"{_smart_notice(lang, review)}"
        f"{_risk_block(lang, review)}"
        '<table class="entities"><thead><tr>'
        f"<th>{_t('ui.col_in_document', lang)}</th><th>{_t('ui.col_sent_as', lang)}</th>"
        f"<th>{_t('ui.col_kind', lang)}</th><th>{_t('ui.col_count', lang)}</th><th></th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table>"
        '<p class="row mark">'
        f'<input type="text" id="mark-surface" placeholder="{_t("ui.mark_hint", lang)}" '
        f"{_INPUT_ATTRS}>"
        f'<select id="mark-type" {_INPUT_ATTRS}>{kinds}</select>'
        f'<button data-action="mark">{_t("ui.mark", lang)}</button></p>'
        f"<h2>{_t('ui.exact_text', lang)} ({len(rendering.text)} {_t('ui.chars', lang)})</h2>"
        '<p class="row toggles">'
        f'<button class="link" data-action="toggle-original" '
        f'data-label-on="{_t("ui.show_leaving", lang)}" '
        f'data-label-off="{_t("ui.show_original", lang)}">{_t("ui.show_original", lang)}</button>'
        "</p>"
        '<pre class="leaving" id="leaving" data-text-read="0">'
        f"{_marked_text(rendering.text, rendering.segments, invisible_offsets, rendering.kept)}"
        "</pre>"
        '<pre class="original hidden" id="original">'
        f"{_original_text(review.raw_text, rendering.segments, rendering.kept)}</pre>"
        f"<p class=\"sha\">{_t('ui.sha', lang)}: {_E(rendering.sha256)}</p>"
        '<p class="attest"><label>'
        f'<input type="checkbox" id="attest" {_INPUT_ATTRS}> <span>{_t("ui.attest", lang)}</span>'
        "</label></p>"
        '<p class="row">'
        f'<button class="primary" data-action="approve" disabled>{_t("ui.approve", lang)}</button>'
        f"{_cancel_button(lang)}</p>"
        f"<p class=\"muted after\">{_t('ui.after_approve', lang)}</p>"
        f"{_countdown(lang)}"
        '<p id="error" class="error hidden"></p>'
        "</section>"
    )


def _screen_approved(lang: str, review: Review) -> str:
    phrase = _s("ui.nudge_phrase", lang)
    sha = review.payload_sha256 or ""
    ref = f"{_t('ui.ledger_ref', lang)} #{review.approval_id}"
    return (
        f'<section class="screen" data-status="{review.status.value}" data-sha256="{_E(sha)}">'
        f"<h1>{_t('ui.approved_title', lang)}</h1>"
        '<ol class="steps">'
        f"<li class=\"done\">{_t('ui.step_approved', lang)} <b>{ref}</b>"
        f"<span class=\"sha\"> · sha256 {_E(sha)}</span></li>"
        f"<li class=\"now\">{_t('ui.step_tell', lang)} "
        f'<code id="nudge">{_E(phrase)}</code> '
        f'<button data-action="copy" data-copy="{_E(phrase)}">{_t("ui.copy", lang)}</button>'
        f"<br><span class=\"muted\">{_t('ui.step_tell_why', lang)}</span></li>"
        f"<li>{_t('ui.step_collect', lang)}</li>"
        "</ol>"
        f"<p class=\"muted\">{_t('ui.approved_window', lang)} "
        '<span id="approved-countdown"></span></p>'
        '<p class="row">'
        f'<button data-action="cancel" class="withdraw">{_t("ui.withdraw", lang)}</button></p>'
        '<p id="error" class="error hidden"></p>'
        "</section>"
    )


def _format_time(ts: float | None) -> tuple[str, str]:
    if ts is None:
        return "", ""
    dt = datetime.fromtimestamp(ts, tz=UTC)
    return dt.isoformat(timespec="seconds"), dt.astimezone().strftime("%H:%M")


def _screen_released(lang: str, review: Review) -> str:
    sha = review.payload_sha256 or ""
    iso, clock = _format_time(review.released_at)
    ref = f"{_t('ui.ledger_ref', lang)} #{review.approval_id}"
    return (
        f'<section class="screen" data-status="{review.status.value}" data-sha256="{_E(sha)}" '
        f'data-answers="{len(review.answers)}">'
        f"<h1>{_t('ui.released_title', lang)} "
        f'<time datetime="{_E(iso)}" data-ts="{review.released_at or ""}">{_E(clock)}</time></h1>'
        f'<p id="too-late" class="notice hidden">{_t("ui.too_late", lang)}</p>'
        f"<p class=\"sha\">{_t('ui.sha', lang)}: {_E(sha)} · {ref}</p>"
        f"<h2>{_t('ui.answers_title', lang)}</h2>"
        f'<div id="answers">{render_answers(lang, review)}</div>'
        "</section>"
    )


def _missing_list(lang: str, ids: Iterable[str]) -> str:
    items = "".join(
        f"<li>{_t(f'ui.missing.{m}', lang)}</li>" for m in ids if f"ui.missing.{m}" in STRINGS
    )
    return f'<ul class="missing">{items}</ul>' if items else ""


def _screen_closed(lang: str, review: Review) -> str:
    if review.status == ReviewStatus.CANCELLED:
        withdrawn = review.approval_id is not None
        title_key = "ui.closed_withdrawn" if withdrawn else "ui.closed_cancelled"
    elif review.status == ReviewStatus.EXPIRED:
        title_key = "ui.closed_expired"
    else:
        title_key = "ui.closed_failed"
    detail = ""
    key = review.error_key
    if key and f"ui.error.{key}" in STRINGS:
        detail = f"<p class=\"error\">{_t(f'ui.error.{key}', lang)}</p>"
        if key == "models_missing":
            detail += _missing_list(lang, review.missing)
            detail += f"<p>{_t('ui.missing.command', lang)}</p>"
        elif key == "component_missing":
            detail += _missing_list(lang, review.missing)
    return (
        f'<section class="screen" data-status="{review.status.value}">'
        f"<h1>{_t(title_key, lang)}</h1>{detail}"
        f"<p class=\"muted\">{_t('ui.start_from_claude', lang)}</p></section>"
    )


def render_answers(lang: str, review: Review) -> str:
    """Model answers with the real names, escaped, each in a labelled frame
    with a Copy button. The legend lists only the pseudonyms that appear in
    that answer."""

    if not review.answers:
        return f"<p class=\"muted\">{_t('ui.no_answer_yet', lang)}</p>"
    out = []
    for i, a in enumerate(review.answers, 1):
        legend = "; ".join(
            f"<code>{_E(p)}</code> → {_E(name)} ({_kind(kind, lang)})" for p, name, kind in a.legend
        )
        unknown = (
            f"<p class=\"unknown\">{_t('ui.unknown_pseudonym', lang)} "
            f"{', '.join(f'<code>{_E(u)}</code>' for u in a.unknown)}</p>"
            if a.unknown
            else ""
        )
        out.append(
            f'<article class="answer" data-index="{i}">'
            f"<p class=\"warning\">{_t('ui.answer_warning', lang)}</p>"
            f'<p class="row"><button data-action="copy-answer" data-target="answer-{i}">'
            f"{_t('ui.copy_answer', lang)}</button></p>"
            f'<pre class="model-text" id="answer-{i}">{_E(a.rehydrated)}</pre>'
            f"<p class=\"legend\"><b>{_t('ui.legend', lang)}:</b> {legend or '—'}</p>"
            f"{unknown}</article>"
        )
    return "".join(out)
