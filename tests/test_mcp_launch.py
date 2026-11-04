"""`jude mcp open` and the window-file sweep."""

from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import time

import pytest

from jude.mcp import launch


def _write(directory, pid, port, *, started_at, secret="s" * 64, name=None):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (name or f"window-{pid}.json")
    path.write_text(json.dumps({
        "pid": pid, "port": port, "local_secret": secret, "started_at": started_at,
    }))
    return path


@pytest.fixture
def sleeper():
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        yield proc
    finally:
        proc.kill()
        proc.wait()


def test_pid_alive_never_calls_os_kill_on_win32(monkeypatch):
    calls: list[tuple[int, int]] = []

    class FakeK32:
        def __init__(self):
            self.handles: dict[int, int] = {}

        def OpenProcess(self, access, inherit, pid):  # noqa: N802
            assert access == 0x1000
            if pid == 4242:
                return 7
            if pid == 5555:
                FakeK32.last_error = 5  # ERROR_ACCESS_DENIED: exists, not ours
                return 0
            FakeK32.last_error = 87
            return 0

        def GetExitCodeProcess(self, handle, code_ref):  # noqa: N802
            code_ref._obj.value = 259 if handle == 7 else 0
            return 1

        def CloseHandle(self, handle):  # noqa: N802
            return 1

    FakeK32.last_error = 0
    fake = FakeK32()
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(ctypes, "WinDLL", lambda name, use_last_error=False: fake, raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: FakeK32.last_error, raising=False)

    def boom(pid, sig):
        calls.append((pid, sig))
        raise AssertionError("os.kill(pid, 0) is TerminateProcess on Windows")

    monkeypatch.setattr(os, "kill", boom)
    assert launch.pid_alive(4242) is True
    assert launch.pid_alive(5555) is True
    assert launch.pid_alive(6666) is False
    assert launch.pid_alive(0) is False
    assert calls == []


def test_pid_alive_posix(sleeper):
    assert launch.pid_alive(sleeper.pid) is True
    assert launch.pid_alive(-1) is False
    sleeper.kill()
    sleeper.wait()
    assert launch.pid_alive(sleeper.pid) is False


def test_sweep_keeps_young_live_window_file(tmp_path, sleeper):
    now = time.time()
    young = _write(tmp_path, sleeper.pid, 1, started_at=now - 5)
    removed = launch.sweep_stale_files(tmp_path, now=lambda: now, pinger=lambda port, s: None)
    assert removed == [] and young.exists()
    old = _write(tmp_path, sleeper.pid, 2, started_at=now - 120, name="window-old.json")
    removed = launch.sweep_stale_files(tmp_path, now=lambda: now, pinger=lambda port, s: None)
    assert removed == [old] and young.exists() and not old.exists()
    old2 = _write(tmp_path, sleeper.pid, 3, started_at=now - 120, name="window-old2.json")
    removed = launch.sweep_stale_files(
        tmp_path, now=lambda: now, pinger=lambda port, s: {"mac": "ok", "has_review": False}
    )
    assert removed == [] and old2.exists()  # old but answering: live


def test_sweep_removes_file_of_dead_pid(tmp_path):
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    now = time.time()
    dead = _write(tmp_path, proc.pid, 1, started_at=now)
    unreadable = tmp_path / "window-99.json"
    unreadable.write_text("not json")
    own = _write(tmp_path, os.getpid(), 2, started_at=now)
    tmp = tmp_path / "tmp" / "r-old"
    tmp.mkdir(parents=True)
    os.utime(tmp, (now - 7200, now - 7200))
    removed = launch.sweep_stale_files(tmp_path, now=lambda: now, pinger=lambda port, s: None)
    assert set(removed) == {dead, unreadable, own, tmp}
    assert not dead.exists() and not unreadable.exists() and not tmp.exists()


def test_open_window_prefers_listener_with_review(tmp_path, monkeypatch, sleeper):
    now = time.time()
    _write(tmp_path, sleeper.pid, 1001, started_at=now, secret="a" * 64)
    _write(tmp_path, sleeper.pid + 100000, 1002, started_at=now, secret="b" * 64)
    monkeypatch.setattr(launch, "pid_alive", lambda pid: True)
    pings = {1001: {"mac": "x", "has_review": False}, 1002: {"mac": "x", "has_review": True}}
    monkeypatch.setattr(launch, "ping", lambda port, secret, timeout=3.0: pings.get(port))
    minted: list[tuple[int, str | None]] = []

    def fake_mint(port, secret, *, timeout=3.0, ttl=None):
        minted.append((port, ttl))
        return f"http://127.0.0.1:{port}/open/tok"

    monkeypatch.setattr(launch, "mint", fake_mint)
    opened: list[str] = []
    echoed: list[str] = []
    code = launch.open_window(
        directory=tmp_path, open_browser=lambda url: opened.append(url) or True,
        echo=echoed.append,
    )
    assert code == 0 and minted == [(1002, None)]
    assert opened == ["http://127.0.0.1:1002/open/tok"]
    assert echoed == [launch.OPENED_MESSAGE]


def test_open_window_fallback_prints_short_url(tmp_path, monkeypatch, sleeper):
    now = time.time()
    _write(tmp_path, sleeper.pid, 1001, started_at=now, secret="a" * 64)
    monkeypatch.setattr(launch, "ping", lambda port, secret, timeout=3.0: {"mac": "x",
                                                                           "has_review": True})
    minted: list[str | None] = []

    def fake_mint(port, secret, *, timeout=3.0, ttl=None):
        minted.append(ttl)
        return f"http://127.0.0.1:{port}/open/{'short' if ttl else 'long'}"

    monkeypatch.setattr(launch, "mint", fake_mint)
    echoed: list[str] = []
    code = launch.open_window(directory=tmp_path, open_browser=lambda url: False,
                              echo=echoed.append)
    assert code == 0 and minted == [None, "short"]
    assert echoed == [f"{launch.SHORT_URL_MESSAGE} http://127.0.0.1:1001/open/short"]
    assert "long" not in echoed[0]


def test_open_window_no_listener(tmp_path, monkeypatch):
    now = time.time()
    stale = _write(tmp_path, 1, 1001, started_at=now - 120)
    monkeypatch.setattr(launch, "pid_alive", lambda pid: True)
    monkeypatch.setattr(launch, "ping", lambda port, secret, timeout=3.0: None)
    echoed: list[str] = []
    assert launch.open_window(directory=tmp_path, echo=echoed.append) == 1
    assert echoed == [launch.NO_WINDOW_MESSAGE] and not stale.exists()
