"""Keep document content out of stderr (and so out of Claude Desktop's logs).

The server logs twice: a local trace file (mode 0600, rotated, full
tracebacks, for `jude mcp doctor` and for the user) and the *original*
stderr, which Claude Desktop captures into its own log directory. By the
time ``configure_logging`` runs, ``server.main()`` has pointed fd 2 at the
trace file, so the only writer to Claude Desktop's log is the
``StreamHandler`` installed here, and it sits behind ``NoContentFilter``,
which rewrites every record so that only static text goes through:

* records with an exception attached become
  ``<suppressed> exc=<Type> at <jude/path.py:line>`` — the exception's
  text (which may quote a document or a path) never reaches stderr;
* records from loggers other than ``jude.mcp`` are replaced by
  ``<suppressed> logger=<name> at <module>`` (third-party libraries and
  ``py.warnings`` print whatever they like, including file paths and
  model inputs);
* ``jude.mcp`` records keep their message when it is at most 200
  characters long — Jude's own messages are static strings; anything
  longer is suppressed as a precaution.

The filter mutates the record, so the trace handler must run first:
``configure_logging`` installs the handlers in that order.

The trace file is the one complete local record. It starts with a header
line saying so, is created 0600, and rotates at 2 MiB keeping three
backups, so it never grows into an unbounded copy of the documents.
"""

from __future__ import annotations

import contextlib
import io
import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import IO

MAX_SAFE_MESSAGE = 200
SAFE_LOGGER_PREFIX = "jude.mcp"
TRACE_MAX_BYTES = 2 * 1024 * 1024
TRACE_BACKUPS = 3
TRACE_HEADER = "# Jude MCP trace. May contain document text. Never share this file.\n"


def _where(record: logging.LogRecord) -> str:
    """A location that never includes a home directory: the path after the
    package root when the record comes from Jude, the module name otherwise."""

    path = (record.pathname or "").replace(os.sep, "/")
    marker = "/jude/"
    idx = path.rfind(marker)
    if idx >= 0:
        return f"jude/{path[idx + len(marker):]}:{record.lineno}"
    return f"{record.module}:{record.lineno}"


class NoContentFilter(logging.Filter):
    """See the module docstring. Always returns True: the record is emitted,
    rewritten."""

    def filter(self, record: logging.LogRecord) -> bool:
        exc_name: str | None = None
        if record.exc_info and record.exc_info[0] is not None:
            exc_name = record.exc_info[0].__name__
        where = _where(record)
        safe_logger = record.name == SAFE_LOGGER_PREFIX or record.name.startswith(
            SAFE_LOGGER_PREFIX + "."
        )
        try:
            message = record.getMessage()
        except Exception:
            message = ""
            safe_logger = False
        if exc_name is not None:
            record.msg = f"<suppressed> exc={exc_name} at {where}"
        elif safe_logger and len(message) <= MAX_SAFE_MESSAGE:
            record.msg = message
        else:
            record.msg = f"<suppressed> logger={record.name} at {where}"
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True


class RotatingSecureFileHandler(logging.handlers.RotatingFileHandler):
    """A rotating file handler whose files are created 0600 and start with
    ``TRACE_HEADER``. Rotation renames the file, so backups keep the mode."""

    def __init__(self, filename: str, *, encoding: str = "utf-8") -> None:
        super().__init__(
            filename,
            maxBytes=TRACE_MAX_BYTES,
            backupCount=TRACE_BACKUPS,
            encoding=encoding,
            delay=False,
        )

    def _open(self) -> IO[str]:  # type: ignore[override]
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        fd = os.open(self.baseFilename, flags, 0o600)
        with contextlib.suppress(OSError):
            os.chmod(self.baseFilename, 0o600)
        try:
            empty = os.fstat(fd).st_size == 0
        except OSError:
            empty = False
        stream = os.fdopen(fd, "a", encoding=self.encoding or "utf-8")
        if empty:
            stream.write(TRACE_HEADER)
            stream.flush()
        return stream


# Kept as a name for callers that predate rotation.
SecureFileHandler = RotatingSecureFileHandler


def configure_logging(
    trace_path: Path | None,
    *,
    stderr_fd: int | None = None,
    stderr_level: int = logging.WARNING,
) -> None:
    """Replace the root handlers: the trace file first (full detail, local,
    0600, rotated), then the filtered stderr handler. ``stderr_fd`` is the
    saved copy of the original fd 2 (Claude Desktop's log); when it is
    None the handler writes to ``sys.stderr``. Must run before the MCP
    SDK's ``basicConfig`` (a no-op once root has handlers; otherwise it
    would install a RichHandler printing tracebacks and locals)."""

    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    if trace_path is not None:
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        trace = RotatingSecureFileHandler(str(trace_path))
        trace.setLevel(logging.INFO)
        trace.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        root.addHandler(trace)
    stream: IO[str]
    if stderr_fd is not None:
        stream = io.TextIOWrapper(
            io.FileIO(stderr_fd, "w", closefd=False), encoding="utf-8", errors="replace",
            line_buffering=True,
        )
    else:
        stream = sys.stderr
    stderr = logging.StreamHandler(stream)
    stderr.setLevel(stderr_level)
    stderr.addFilter(NoContentFilter())
    stderr.setFormatter(logging.Formatter("jude-mcp %(levelname)s %(message)s"))
    root.addHandler(stderr)
    root.setLevel(logging.INFO)
    # Chatty third parties: the trace file does not need their INFO either.
    for name in ("mcp", "anyio", "httpx", "urllib3", "huggingface_hub", "transformers", "torch"):
        logging.getLogger(name).setLevel(logging.WARNING)
