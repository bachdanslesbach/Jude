"""The MCP server: three tools over stdio, nothing else.

``prepare_document`` opens the local window and returns a review id;
``fetch_approved`` waits a little and hands the approved text out once,
as one text block; ``show_answer`` displays the model's answer with the
real names in the window and returns a character count. No tool takes a
matter, a path or a name; no tool result carries one. Every error the
model can see is one of the static strings in ``strings.py``.

``main()`` runs in a load-bearing order: normalise the environment,
install the network tripwire (before any detector is imported), take the
instance lock, point fd 2 at the 0600 trace file (so no library, warning
or C-level message can reach Claude Desktop's log — only the filtered
StreamHandler writes to the saved original fd 2), sweep stale files,
open the store and recover what a previous abrupt stop left, then start
the window and the SDK.

Protocol hygiene (I7): the SDK's ``stdio_server()`` claims fd 1 and
points it at ``os.dup(2)`` — i.e. at the trace file — for the whole run,
so a library that prints cannot tear a JSON-RPC frame. Logging is
configured before the server object exists so the SDK's ``basicConfig``
(a RichHandler with tracebacks) never installs. The process ends with
``os._exit`` after the window is closed, so no interpreter-shutdown
message can reach the wire once fd 1 is restored — and, whatever a
thread is doing, within ``STOP_DEADLINE`` seconds of a stop request: a
watchdog thread exits for a step that wedges (a serve loop stuck in
``accept()`` once held a SIGTERM for ever).

This module imports the SDK and the standard library only; the
detection stack is imported by ``build_server`` (through ``reviews``),
after ``netguard.install()``.
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import os
import signal
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import anyio
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations
from pydantic import ConfigDict

from ..paths import default_db_path, jude_home
from ..store import Store
from . import env, netguard
from .launch import sweep_stale_files
from .logfilter import configure_logging
from .strings import INSTRUCTIONS, TOOL_DESCRIPTIONS
from .strings import text as _s

if TYPE_CHECKING:
    from .reviews import ReviewManager

log = logging.getLogger("jude.mcp.server")

# Re-exported for callers that predate ``env``.
OFFLINE_ENV = env.OFFLINE_ENV

FETCH_MIN_WAIT = 5
FETCH_MAX_WAIT = 30
DEFAULT_IDLE_TTL = 1200
DEFAULT_APPROVED_HOLD = 1800
DUPLICATE_LINE = (
    "jude-mcp WARNING another jude mcp server is already running for this JUDE_HOME; exiting\n"
)
# stop() ends in os._exit by then, whatever its threads are doing: 5 s for a
# running preparation, 5 s for the window, and margin for the rest.
STOP_DEADLINE = 15.0
WATCHDOG_LINE = "jude-mcp WARNING shutdown did not finish in time; exiting\n"


class _JudeServer(MCPServer):
    """``MCPServer`` that refuses unknown arguments with a static sentence.

    The SDK's argument models ignore extra keys by default, so a model that
    typed a matter or a file name into ``prepare_document`` would get a
    normal result and learn nothing. Here the schemas say
    ``additionalProperties: false`` (``forbid_extra_arguments``) and, before
    the SDK validates, any key outside the schema answers ``err.unknown_
    argument`` — static text, never the rejected value, so the error itself
    cannot echo a name the model typed."""

    lang = "en"

    async def call_tool(self, name: str, arguments: dict[str, Any], context: Any = None) -> Any:
        tool = self._tool_manager.get_tool(name)
        if tool is not None and arguments:
            allowed = set(tool.parameters.get("properties", {}))
            if set(arguments) - allowed:
                raise ToolError(_s("err.unknown_argument", self.lang))
        return await super().call_tool(name, arguments, context)


def forbid_extra_arguments(mcp: MCPServer) -> None:
    """Make every registered tool's argument model reject unknown keys and
    publish ``additionalProperties: false`` in its input schema."""

    for tool in mcp._tool_manager.list_tools():
        base = tool.fn_metadata.arg_model
        strict = type(
            base.__name__,
            (base,),
            {"model_config": ConfigDict(extra="forbid", arbitrary_types_allowed=True)},
        )
        tool.fn_metadata.arg_model = strict
        tool.parameters = strict.model_json_schema(by_alias=True)


def build_server(manager: ReviewManager, *, lang: str = "en") -> MCPServer:
    """Register the three tools on an ``MCPServer``. Store and manager calls
    run off the event loop thread (``anyio.to_thread``) so a slow disk
    never stalls the protocol. Every tool is registered with
    ``structured_output=False``: the SDK then emits ONE text block and no
    ``structuredContent``, so the released text crosses the pipe once.
    Every tool rejects arguments outside its schema (``err.unknown_argument``)."""

    from .reviews import (
        TERMINAL,
        AlreadyReleased,
        AnswerTooLong,
        Busy,
        NotReleased,
        RateLimited,
        ReleaseRefused,
        ReviewStatus,
        UnknownReview,
        sha256_hex,
    )

    mcp = _JudeServer(name="jude", instructions=INSTRUCTIONS, log_level="WARNING")
    mcp.lang = lang

    def err(key: str) -> ToolError:
        return ToolError(_s(key, lang))

    @mcp.tool(
        name="prepare_document",
        description=TOOL_DESCRIPTIONS["prepare_document"],
        annotations=ToolAnnotations(
            title="Prepare a document in Jude",
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        ),
        structured_output=False,
    )
    async def prepare_document() -> dict[str, Any]:
        try:
            outcome = await anyio.to_thread.run_sync(manager.create)
        except Busy:
            raise err("err.busy") from None
        except Exception:
            log.error("prepare_document failed", exc_info=True)
            raise err("err.internal_tool") from None
        if outcome.already_open:
            # The conversation that started the review has its id; nobody
            # else gets it.
            return {"status": "other_review_open", "next": _s("next.already_open", lang)}
        key = "next.prepared" if outcome.browser_opened else "next.no_browser"
        return {
            "review_id": outcome.review.id,
            "status": outcome.review.status.value,
            "next": _s(key, lang),
        }

    @mcp.tool(
        name="fetch_approved",
        description=TOOL_DESCRIPTIONS["fetch_approved"],
        annotations=ToolAnnotations(
            title="Collect the approved text",
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=False,
        ),
        structured_output=False,
    )
    async def fetch_approved(review_id: str, wait_seconds: int = 15) -> dict[str, Any]:
        wait = min(FETCH_MAX_WAIT, max(FETCH_MIN_WAIT, int(wait_seconds)))
        deadline = time.monotonic() + wait
        while True:
            try:
                status = await anyio.to_thread.run_sync(manager.status_of, review_id)
            except UnknownReview:
                raise err("err.unknown_review") from None
            except Exception:
                log.error("fetch_approved failed", exc_info=True)
                raise err("err.internal_tool") from None
            if status == ReviewStatus.APPROVED:
                try:
                    text = await anyio.to_thread.run_sync(manager.release, review_id)
                except AlreadyReleased:
                    break
                except ReleaseRefused:
                    raise err("err.refused") from None
                except NotReleased:
                    break
                except Exception:
                    log.error("release failed", exc_info=True)
                    raise err("err.internal_tool") from None
                return {
                    "review_id": review_id,
                    "status": ReviewStatus.RELEASED.value,
                    "sha256": sha256_hex(text),
                    "chars": len(text),
                    "text": text,
                }
            if status in TERMINAL:
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            await anyio.sleep(min(1.0, remaining))
        try:
            return await anyio.to_thread.run_sync(manager.public_status, review_id, lang)
        except UnknownReview:
            raise err("err.unknown_review") from None

    @mcp.tool(
        name="show_answer",
        description=TOOL_DESCRIPTIONS["show_answer"],
        annotations=ToolAnnotations(
            title="Show the answer in Jude",
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=False,
        ),
        structured_output=False,
    )
    async def show_answer(review_id: str, text: str) -> dict[str, Any]:
        try:
            await anyio.to_thread.run_sync(manager.show_answer, review_id, text)
        except UnknownReview:
            raise err("err.unknown_review") from None
        except NotReleased:
            raise err("err.not_released") from None
        except AnswerTooLong:
            raise err("err.too_long_answer") from None
        except RateLimited:
            raise err("err.busy") from None
        except Exception:
            log.error("show_answer failed", exc_info=True)
            raise err("err.internal_tool") from None
        return {"status": "shown", "chars": len(text)}

    forbid_extra_arguments(mcp)
    return mcp


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="jude mcp", add_help=True)
    parser.add_argument(
        "--idle-ttl",
        type=int,
        default=DEFAULT_IDLE_TTL,
        help="Seconds a review stays open without the lawyer interacting with the window "
        "(polls do not count).",
    )
    parser.add_argument(
        "--approved-hold",
        type=int,
        default=DEFAULT_APPROVED_HOLD,
        help="Seconds an approved text waits for Claude before the approval lapses.",
    )
    parser.add_argument("--lang", choices=("en", "fr"), default="en")
    return parser.parse_args(argv)


def _chmod(path: Path, mode: int) -> None:
    with contextlib.suppress(OSError):
        os.chmod(path, mode)


def acquire_instance_lock(mcp_dir: Path) -> int | None:
    """One server per JUDE_HOME. Returns the lock fd, or None when another
    process holds it. POSIX ``flock``, Windows ``msvcrt.locking``."""

    fd = os.open(mcp_dir / "server.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if sys.platform == "win32":  # pragma: no cover — not exercised on this machine
            import msvcrt

            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return None
    return fd


def release_instance_lock(fd: int | None) -> None:
    if fd is None:
        return
    with contextlib.suppress(OSError):
        if sys.platform == "win32":  # pragma: no cover
            import msvcrt

            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_UN)
    with contextlib.suppress(OSError):
        os.close(fd)


def capture_stderr(trace_path: Path) -> int:
    """Point fd 2 at the trace file; return a duplicate of the original fd 2
    (Claude Desktop's log) for the filtered handler. From here on
    ``sys.stderr``, ``warnings``, library prints and C-level writes to
    fd 2 all land in the trace."""

    trace_fd = os.open(trace_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    saved = os.dup(2)
    os.dup2(trace_fd, 2)
    os.close(trace_fd)
    return saved


def _arm_watchdog(code: int, deadline: float, stderr_fd: int | None) -> threading.Timer:
    """``stop()`` must end in ``os._exit``. If any step wedges — a thread
    that never returns, a lock held elsewhere — this timer writes one
    static line (raw ``os.write``: no logging lock to wait for) to the
    trace and to the saved original stderr, then exits for it. What was
    in flight is covered by ``provisional_review_id`` and
    ``lost_on_restart`` at the next start."""

    def fire() -> None:
        for fd in (2, stderr_fd):
            if fd is not None:
                with contextlib.suppress(OSError):
                    os.write(fd, WATCHDOG_LINE.encode("utf-8"))
        os._exit(code)

    timer = threading.Timer(deadline, fire)
    timer.daemon = True
    timer.name = "jude-stop-watchdog"
    timer.start()
    return timer


def _quiet_root_logging(trace_path: Path, stderr_fd: int | None) -> None:
    """Our two handlers, and only ours, on the root logger."""

    root = logging.getLogger()
    names = {type(h).__name__ for h in root.handlers}
    if names != {"RotatingSecureFileHandler", "StreamHandler"}:
        configure_logging(trace_path, stderr_fd=stderr_fd)


def main(
    argv: list[str] | None = None,
    *,
    extra_tools: Callable[[MCPServer], None] | None = None,
) -> int:
    """Entry point of ``jude mcp`` and ``python -m jude.mcp``. Never prints
    to stdout. Returns only through ``os._exit``."""

    args = _parse_args(argv)
    # 1. environment: offline flags, empty paths mean unset
    env.normalise_env(os.environ)
    # 2. network tripwire, before anything imports the detection stack
    netguard.install()
    # 3. directories and the instance lock
    home = jude_home()
    home.mkdir(parents=True, exist_ok=True)
    _chmod(home, 0o700)
    mcp_dir = home / "mcp"
    mcp_dir.mkdir(parents=True, exist_ok=True)
    _chmod(mcp_dir, 0o700)
    lock_fd = acquire_instance_lock(mcp_dir)
    if lock_fd is None:
        with contextlib.suppress(OSError):
            os.write(2, DUPLICATE_LINE.encode("utf-8"))
        os._exit(0)
    # 4. stderr capture: fd 2 -> trace (0600); the saved original gets static lines only
    trace_path = mcp_dir / "trace.log"
    saved_stderr = capture_stderr(trace_path)
    configure_logging(trace_path, stderr_fd=saved_stderr)
    logging.captureWarnings(True)
    # 5. stale window files and temp dirs
    sweep_stale_files(mcp_dir)
    # 6. the store, and what a previous abrupt stop left behind
    db_path = default_db_path()
    store = Store(db_path)
    _chmod(db_path, 0o600)
    store.recover_after_restart()
    log.info("recovered")
    # 7. manager, window, server
    from .reviews import ReviewManager
    from .window import Window

    manager = ReviewManager(
        store,
        idle_ttl=args.idle_ttl,
        approved_hold=args.approved_hold,
        lang=args.lang,
        tmp_dir=mcp_dir / "tmp",
    )
    window = Window(manager, state_dir=mcp_dir, lang_default=args.lang)
    window.start()
    manager.url_factory = window.mint_url
    server = build_server(manager, lang=args.lang)
    if extra_tools is not None:
        extra_tools(server)
    # 8. nothing else on the root logger; signals
    _quiet_root_logging(trace_path, saved_stderr)

    stopping: list[int] = []

    def stop(code: int) -> None:
        # Armed once: whatever a thread is doing, the process is gone by
        # STOP_DEADLINE. A second signal re-enters stop() (useful when the
        # first call is wedged) without arming a second timer.
        if not stopping:
            stopping.append(code)
            _arm_watchdog(code, STOP_DEADLINE, saved_stderr)
        try:
            window.stop()
        finally:
            try:
                manager.close(grace=5.0)
            finally:
                try:
                    store.close()
                finally:
                    release_instance_lock(lock_fd)
                    logging.shutdown()
                    os._exit(code)

    def on_signal(signum: int, _frame: object) -> None:
        log.info("signal received")
        stop(0)

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)

    # 9. serve
    log.info("jude mcp server starting")
    try:
        anyio.run(server.run_stdio_async)
    except BaseException:
        log.error("server stopped on error", exc_info=True)
        stop(1)
    log.info("jude mcp server stopping")
    stop(0)
    return 0  # pragma: no cover — stop() does not return


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
