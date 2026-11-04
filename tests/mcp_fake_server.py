"""Test-only entry point: the real ``jude.mcp.server`` with a fake detector.

Spawned by ``tests/test_mcp_server.py`` and ``tests/test_mcp_invariants.py``
over stdio. It never loads a model and never opens a browser. Knobs are
environment variables read only here:

* ``JUDE_MCP_FAKE_MODE``: ``normal`` | ``noisy`` (the detector prints to
  stdout and writes raw bytes to fd 1) | ``noisy_stderr`` (the detector
  warns, writes to ``sys.stderr``, to fd 2 and, on POSIX, to fd 2 from C,
  every line carrying a canary) | ``raise_validation`` (the detector
  raises a pydantic ``ValidationError`` carrying a canary) | ``slow``
  (the second ``detect()`` call sleeps 10 s) | ``wedged_stop``
  (``Window.stop`` blocks for ever and ``STOP_DEADLINE`` is 3 s: only the
  watchdog can end the process);
* ``JUDE_MCP_NO_BROWSER=1``: record ``webbrowser.open`` calls in
  ``$JUDE_HOME/browser_opens.log`` instead of opening anything;
* ``JUDE_MCP_FAKE_DEBUG_FDS=1``: register one extra tool, ``debug_fds``;
* ``JUDE_MCP_FAKE_DEBUG_NET=1``: register one extra tool, ``debug_net``.
"""

from __future__ import annotations

import os
import re
import sys
import time
import warnings
import webbrowser
from pathlib import Path
from typing import Any

from jude.mcp import netguard

netguard.install()

import jude.mcp.reviews as reviews  # noqa: E402
import jude.mcp.server as server  # noqa: E402
from jude.types import Detection, DetectionSource, EntityType  # noqa: E402

MODE = os.environ.get("JUDE_MCP_FAKE_MODE", "normal")
CANARY = "CANARY-NAME-3c4d"
SURFACES: tuple[tuple[str, EntityType], ...] = (
    ("Thonnard SA", EntityType.ORG),
    ("Marie-Claire Lefèvre", EntityType.PERSON),
    (CANARY, EntityType.PERSON),
)


class FakePipeline:
    def __init__(self, *args: Any, redact_codenames: bool | None = None, **kwargs: Any) -> None:
        self.calls = 0
        self.redact_codenames = bool(redact_codenames)

    def detect(self, text: str) -> list[Detection]:
        self.calls += 1
        if MODE == "noisy":
            print("noise from a chatty library")
            sys.stdout.flush()
            os.write(1, b"raw noise\n")
        if MODE == "noisy_stderr":
            warnings.simplefilter("always")
            warnings.warn(f"{CANARY} warned from a library", stacklevel=1)
            sys.stderr.write(f"{CANARY} written to sys.stderr\n")
            sys.stderr.flush()
            os.write(2, f"{CANARY} written to fd 2\n".encode())
            if sys.platform != "win32":
                import ctypes

                payload = f"{CANARY} written from C\n".encode()
                ctypes.CDLL(None).write(2, payload, len(payload))
        if MODE == "raise_validation":
            import pydantic

            pydantic.TypeAdapter(int).validate_python(CANARY)
        if MODE == "slow" and self.calls == 2:
            time.sleep(10)
        out: list[Detection] = []
        for surface, etype in SURFACES:
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


reviews.DetectionPipeline = FakePipeline  # type: ignore[misc,assignment]
reviews.check_models = lambda langs=None: None  # type: ignore[assignment]

if MODE == "wedged_stop":
    import threading

    import jude.mcp.window as window

    def _wedged_stop(self: Any, timeout: float | None = None) -> None:
        threading.Event().wait()  # never returns: stands for a serve loop that never ends

    window.Window.stop = _wedged_stop  # type: ignore[method-assign]
    server.STOP_DEADLINE = 3.0

if os.environ.get("JUDE_MCP_NO_BROWSER") == "1":
    _log = Path(os.environ["JUDE_HOME"]) / "browser_opens.log"

    def _record_open(url: str, *args: Any, **kwargs: Any) -> bool:
        with _log.open("a", encoding="utf-8") as fh:
            fh.write(url + "\n")
        return True

    webbrowser.open = _record_open  # type: ignore[assignment]


def _same_file(a: int, b: int) -> bool:
    sa, sb = os.fstat(a), os.fstat(b)
    return sa.st_ino == sb.st_ino and sa.st_dev == sb.st_dev


def _extra_tools(mcp: Any) -> None:
    if os.environ.get("JUDE_MCP_FAKE_DEBUG_FDS") == "1":

        @mcp.tool(name="debug_fds", description="test only: where do fd 1 and fd 2 point?")
        def debug_fds() -> dict[str, bool]:
            trace = Path(os.environ["JUDE_HOME"]) / "mcp" / "trace.log"
            fd2_is_trace = False
            if trace.exists():
                st = trace.stat()
                s2 = os.fstat(2)
                fd2_is_trace = st.st_ino == s2.st_ino and st.st_dev == s2.st_dev
            return {"fd1_is_fd2": _same_file(1, 2), "fd2_is_trace": fd2_is_trace}

    if os.environ.get("JUDE_MCP_FAKE_DEBUG_NET") == "1":

        @mcp.tool(name="debug_net", description="test only: what does an outbound call raise?")
        def debug_net() -> dict[str, str]:
            import socket

            out: dict[str, str] = {}
            try:
                socket.gethostbyname("example.invalid")
                out["gethostbyname"] = "allowed"
            except Exception as exc:
                out["gethostbyname"] = type(exc).__name__
            try:
                socket.create_connection(("192.0.2.1", 80), timeout=1).close()
                out["connect"] = "allowed"
            except Exception as exc:
                out["connect"] = type(exc).__name__
            return out


if __name__ == "__main__":
    server.main(sys.argv[1:], extra_tools=_extra_tools)
