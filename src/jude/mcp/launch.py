"""Finding a running window from outside the server process.

The server writes ``<jude_home>/mcp/window-<pid>.json`` (mode 0600) with
its port and a per-run ``local_secret``. ``jude mcp open`` reads those
files, proves each listener is Jude's (HMAC challenge over ``/api/ping``;
the pid check is only a cheap pre-filter), prefers the one that holds a
review, asks it for a one-shot URL (``/api/mint``) and opens the browser.
When the browser cannot be opened, a two-minute URL is printed instead of
the ten-minute one.

Files whose process is dead, or whose listener fails the challenge once
the file is older than a minute, are stale and removed; a file younger
than a minute whose pid is alive is never touched (its server may still
be binding).
"""

from __future__ import annotations

import hashlib
import hmac
import http.client
import json
import logging
import os
import secrets
import shutil
import sys
import time
import webbrowser
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..paths import jude_home

log = logging.getLogger("jude.mcp.launch")

NO_WINDOW_MESSAGE = "no Jude window is running; start a review from Claude"
OPENED_MESSAGE = "Opened the Jude window in your browser."
SHORT_URL_MESSAGE = "Open this single-use address within 2 minutes:"
STALE_TMP_AGE = 3600.0
STALE_WINDOW_AGE = 60.0

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_ERROR_ACCESS_DENIED = 5
_STILL_ACTIVE = 259


def state_dir() -> Path:
    return jude_home() / "mcp"


def pid_alive(pid: int) -> bool:
    """Is a process with this pid alive? On Windows ``os.kill(pid, 0)`` is
    ``TerminateProcess`` — it would kill a live server — so the handle API
    is used there; POSIX uses the zero signal."""

    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
        handle = k32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return ctypes.get_last_error() == _ERROR_ACCESS_DENIED  # exists, not ours
        try:
            code = ctypes.c_ulong()
            ok = k32.GetExitCodeProcess(handle, ctypes.byref(code))
            return bool(ok) and code.value == _STILL_ACTIVE
        finally:
            k32.CloseHandle(handle)
    try:
        os.kill(pid, 0)  # POSIX only: signal 0 probes without sending
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def read_window_file(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if not all(k in data for k in ("pid", "port", "local_secret")):
        return None
    return data


def _pid_of(info: dict[str, Any]) -> int:
    try:
        return int(info["pid"])
    except (TypeError, ValueError, KeyError):
        return -1


def _started_at(info: dict[str, Any]) -> float:
    try:
        return float(info.get("started_at", 0.0))
    except (TypeError, ValueError):
        return 0.0


def sweep_stale_files(
    directory: Path,
    *,
    now: Callable[[], float] = time.time,
    pinger: Callable[[int, str], dict[str, Any] | None] | None = None,
) -> list[Path]:
    """Delete ``window-*.json`` files that are unreadable, whose pid is dead,
    or that are older than a minute and whose listener fails the HMAC
    ping; and temp directories older than an hour. A young file with a
    live pid is kept. Returns what was removed."""

    pinger = pinger or ping
    removed: list[Path] = []
    for path in sorted(directory.glob("window-*.json")):
        info = read_window_file(path)
        pid = _pid_of(info) if info is not None else -1
        stale = info is None or pid == os.getpid() or not pid_alive(pid)
        if not stale and now() - _started_at(info or {}) > STALE_WINDOW_AGE:
            try:
                port = int(info["port"])  # type: ignore[index]
            except (TypeError, ValueError, KeyError):
                port = -1
            stale = port <= 0 or pinger(port, str(info["local_secret"])) is None  # type: ignore[index]
        if stale:
            try:
                path.unlink()
                removed.append(path)
            except OSError:
                pass
    tmp = directory / "tmp"
    if tmp.is_dir():
        for child in tmp.iterdir():
            try:
                if now() - child.stat().st_mtime > STALE_TMP_AGE:
                    shutil.rmtree(child, ignore_errors=True)
                    removed.append(child)
            except OSError:
                pass
    return removed


def _mac(secret: str, prefix: str, nonce: str) -> str:
    return hmac.new(secret.encode(), f"{prefix}:{nonce}".encode(), hashlib.sha256).hexdigest()


def ping(port: int, secret: str, *, timeout: float = 3.0) -> dict[str, Any] | None:
    """Challenge the listener with a nonce. Returns its ping answer
    (``mac`` verified, ``has_review``) or None when it is not Jude's. The
    ``proof`` — an HMAC of the nonce under the secret — is what makes the
    server include ``has_review``: a caller without the secret learns only
    that the listener is Jude's, never whether a document is under review."""

    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        nonce = secrets.token_hex(16)
        proof = _mac(secret, "query", nonce)
        conn.request("GET", f"/api/ping?nonce={nonce}&proof={proof}")
        resp = conn.getresponse()
        body = resp.read()
        if resp.status != 200:
            return None
        obj = json.loads(body.decode("utf-8"))
        mac = obj.get("mac", "") if isinstance(obj, dict) else ""
        if not isinstance(mac, str) or not hmac.compare_digest(mac, _mac(secret, "ping", nonce)):
            return None
        return obj
    except (OSError, ValueError):
        return None
    finally:
        conn.close()


def mint(port: int, secret: str, *, timeout: float = 3.0, ttl: str | None = None) -> str | None:
    """Ask a verified listener for a one-shot URL (``ttl="short"`` for the
    two-minute terminal fallback)."""

    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        nonce = secrets.token_hex(16)
        payload: dict[str, str] = {"nonce": nonce, "mac": _mac(secret, "mint", nonce)}
        if ttl:
            payload["ttl"] = ttl
        conn.request(
            "POST", "/api/mint", body=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        body = resp.read()
        if resp.status != 200:
            return None
        url = json.loads(body.decode("utf-8")).get("url")
        return url if isinstance(url, str) and url.startswith("http://127.0.0.1:") else None
    except (OSError, ValueError):
        return None
    finally:
        conn.close()


def challenge_and_mint(
    port: int, secret: str, *, timeout: float = 3.0, ttl: str | None = None
) -> str | None:
    """Ping first (liveness and identity), then mint. Returns the URL or
    None when the listener is not Jude's."""

    if ping(port, secret, timeout=timeout) is None:
        return None
    return mint(port, secret, timeout=timeout, ttl=ttl)


def open_window(
    *,
    directory: Path | None = None,
    open_browser: Callable[[str], bool] = webbrowser.open,
    echo: Callable[[str], None] = print,
    now: Callable[[], float] = time.time,
) -> int:
    """``jude mcp open``. Exit code 0 when a window was opened (or its
    address printed), 1 when no live window answers."""

    directory = directory or state_dir()
    if not directory.is_dir():
        echo(NO_WINDOW_MESSAGE)
        return 1
    candidates: list[tuple[bool, int, str]] = []
    for path in sorted(directory.glob("window-*.json")):
        info = read_window_file(path)
        if info is None:
            path.unlink(missing_ok=True)
            continue
        try:
            pid, port = int(info["pid"]), int(info["port"])
        except (TypeError, ValueError):
            path.unlink(missing_ok=True)
            continue
        if not pid_alive(pid):
            path.unlink(missing_ok=True)
            continue
        secret = str(info["local_secret"])
        pong = ping(port, secret)
        if pong is None:
            if now() - _started_at(info) > STALE_WINDOW_AGE:
                path.unlink(missing_ok=True)
            continue
        candidates.append((bool(pong.get("has_review")), port, secret))
    if not candidates:
        echo(NO_WINDOW_MESSAGE)
        return 1
    candidates.sort(key=lambda c: not c[0])  # the listener with a review first
    _, port, secret = candidates[0]
    url = mint(port, secret)
    if url is None:
        echo(NO_WINDOW_MESSAGE)
        return 1
    try:
        opened = bool(open_browser(url))
    except Exception:
        opened = False
    if opened:
        echo(OPENED_MESSAGE)
        return 0
    short = mint(port, secret, ttl="short")
    echo(f"{SHORT_URL_MESSAGE} {short or url}")
    return 0
