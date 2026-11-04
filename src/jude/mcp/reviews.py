"""Review state machine for the MCP plugin.

One ``ReviewManager`` per server process. A review is the unit of work:
the lawyer picks a matter and a document in the local window, Jude
redacts the document, the lawyer reads the exact text that will leave,
decides what to keep visible, marks what Jude missed, and approves. The
approval writes a record on disk (hash, counts, confirmations,
deletions) in ONE transaction before the status flips; the model then
collects the text once, through ``release()``, which re-hashes it
against that record.

States::

    awaiting_matter → awaiting_file → preparing → awaiting_review → approved → released
                                      ↘ failed                     ↘ cancelled (withdrawn)
                                                                   ↘ expired

Invariants enforced here (see the design's threat table):

* nothing confidential is ever placed in an exception message or in
  ``public_status()``: errors carry a static ``key`` only;
* a review prunes the entities it created and the surface forms it
  added when it is cancelled, expires before approval or fails — never
  entities that existed before it; entities it creates carry
  ``provisional_review_id`` until an approval confirms them, and every
  store lookup the review makes passes its own id, so those rows are
  visible to this review alone: another ``Store`` connection (the CLI,
  the Streamlit UI) never sees or reuses a pseudonym that a cancel or a
  restart may still delete, and a crash leaves nothing that looks like a
  known entity;
* one review at a time: while a review is open or approved-but-not-
  collected, ``create()`` reports it as already open instead of starting
  another, so no second conversation can displace the Withdraw screen;
* decisions re-apply ``redact()`` to the stored spans; detectors never
  run twice for one document;
* ``release()`` is single-shot and fails closed on a hash mismatch;
  every approval row ends with an ``outcome``;
* smart mode runs the offline context chain only (bundled + EUR-Lex)
  and only for a matter whose zero-retention attestation names Claude
  Desktop; anything else is processed in strict mode;
* the review's clock is the lawyer's: polls never extend it.

Locking. ``_lock`` (RLock) guards review state and is held briefly,
never across I/O. ``_db`` (RLock) guards the store writers and the
approval/release path: it is held around ``redact()``, entity creation,
``approve``, ``release``, ``cancel``, prunes and audit lines — and
NEVER around ``pipeline.detect()``, the pipeline constructor (model
loading) or an adapter read, so the window and the tools stay
responsive while a long document is being read. Order: ``_db`` then
``_lock``; never the reverse. ``_reapply`` requires both.

Detectors may read the store without ``_db``: they only SELECT, the
connection is shared and SQLite serialises statements on it; all
writers hold ``_db``, so no two transactions are ever open at once.
"""

from __future__ import annotations

import contextlib
import getpass
import hashlib
import json
import logging
import os
import re
import secrets
import shutil
import tempfile
import threading
import time
import unicodedata
import uuid
import webbrowser
from collections import Counter
from collections.abc import Callable, Iterable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from ..adapters import DocxAdapter, PdfAdapter, TextAdapter, XlsxAdapter
from ..context import ContextProvider, make_provider
from ..detect import DetectionPipeline
from ..paths import jude_home
from ..redact import redact
from ..risk import RiskAssessment, assess_risks
from ..store import Store
from ..types import Detection, DetectionSource, Entity, EntityType, Matter, Mode, RedactionResult
from . import env, models
from .strings import text as _s

log = logging.getLogger("jude.mcp.reviews")

SUPPORTED_SUFFIXES: frozenset[str] = frozenset({".txt", ".md", ".docx", ".pdf", ".xlsx"})
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
# About 45 000 tokens of French legal prose, roughly 50 pages: leaves room
# for the answer in a 200 k context. A decision to be measured (design E.4).
MAX_TEXT_CHARS = 150_000
MAX_ANSWER_CHARS = 400_000
MAX_APPROVED_HELD = 5
BROWSER_MIN_INTERVAL = 15.0
RECENT_POLL_WINDOW = 15.0
ANSWER_RATE_LIMIT = 20
ANSWER_RATE_WINDOW = 60.0
DEFAULT_IDLE_TTL = 1200.0
DEFAULT_APPROVED_HOLD = 1800.0
DEFAULT_MAX_AGE = 28800.0
DEFAULT_UNLOAD_AFTER = 7200.0
DEFAULT_GLINER = env.DEFAULT_GLINER
ENDPOINT = "claude-desktop"
ENDPOINT_HOST = "stdio:"

PHASES: tuple[str, ...] = ("reading", "loading_models", "detecting", "rendering")
WARNING_KEYS: tuple[str, ...] = ("comments", "tracked_changes", "metadata", "image_pages")

_PSEUDONYM_RE = re.compile(
    r"(?<!\w)(?:Person|Org|Loc|Email|Phone|Iban|Case|Url|Secret|X)\d+(?!\w)"
)
_VISIBLE_CONTROLS = frozenset({"\n", "\t"})


class ReviewStatus(StrEnum):
    AWAITING_MATTER = "awaiting_matter"
    AWAITING_FILE = "awaiting_file"
    PREPARING = "preparing"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    RELEASED = "released"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    FAILED = "failed"


PRE_APPROVAL: frozenset[ReviewStatus] = frozenset(
    {
        ReviewStatus.AWAITING_MATTER,
        ReviewStatus.AWAITING_FILE,
        ReviewStatus.PREPARING,
        ReviewStatus.AWAITING_REVIEW,
    }
)
TERMINAL: frozenset[ReviewStatus] = frozenset(
    {ReviewStatus.RELEASED, ReviewStatus.CANCELLED, ReviewStatus.EXPIRED, ReviewStatus.FAILED}
)

_NEXT_KEY: dict[ReviewStatus, str] = {
    ReviewStatus.AWAITING_MATTER: "next.not_yet",
    ReviewStatus.AWAITING_FILE: "next.not_yet",
    ReviewStatus.PREPARING: "next.not_yet",
    ReviewStatus.AWAITING_REVIEW: "next.not_yet",
    ReviewStatus.APPROVED: "next.approved",
    ReviewStatus.RELEASED: "next.already_released",
    ReviewStatus.CANCELLED: "next.final",
    ReviewStatus.EXPIRED: "next.final",
    ReviewStatus.FAILED: "next.final",
}


# ----- errors: a static key, never content -----


class ReviewError(Exception):
    """Base class. ``key`` is the only payload; it is one of a closed set."""

    key: str = "internal"

    def __init__(self, key: str | None = None) -> None:
        if key is not None:
            self.key = key
        super().__init__(self.key)


class UnknownReview(ReviewError):  # noqa: N818
    key = "unknown_review"


class IllegalTransition(ReviewError):  # noqa: N818
    key = "illegal_transition"


class Busy(ReviewError):  # noqa: N818
    key = "busy"


class TextChanged(ReviewError):  # noqa: N818
    key = "text_changed"


class AttestationRequired(ReviewError):  # noqa: N818
    key = "attestation_required"


class ReviewExpired(ReviewError):  # noqa: N818
    key = "expired"


class AlreadyReleased(ReviewError):  # noqa: N818
    key = "already_released"


class NotReleased(ReviewError):  # noqa: N818
    key = "not_released"


class ReleaseRefused(ReviewError):  # noqa: N818
    key = "refused"


class UnknownEntity(ReviewError):  # noqa: N818
    key = "unknown_entity"


class BadRequest(ReviewError):  # noqa: N818
    key = "bad_request"


class BadUpload(ReviewError):  # noqa: N818
    """``key`` is ``unsupported_suffix`` or ``oversize``."""

    key = "unsupported_suffix"


class AnswerTooLong(ReviewError):  # noqa: N818
    key = "too_long_answer"


class RateLimited(ReviewError):  # noqa: N818
    key = "rate_limited"


class ModelsMissing(ReviewError):  # noqa: N818
    """``missing`` lists the component ids (``spacy_fr``, ``gliner``, …)."""

    key = "models_missing"

    def __init__(self, missing: Iterable[str] = ()) -> None:
        super().__init__()
        self.missing: tuple[str, ...] = tuple(missing)


class _PrepareFailure(Exception):  # noqa: N818
    """Internal: carries the error_key of a failed preparation."""

    def __init__(self, key: str, missing: Iterable[str] = ()) -> None:
        self.key = key
        self.missing = tuple(missing)
        super().__init__(key)


# ----- data -----


@dataclass(frozen=True)
class Segment:
    red_start: int
    red_end: int
    raw_start: int
    raw_end: int
    entity_id: int


@dataclass(frozen=True)
class EntityRow:
    """One line of the review table. ``canonical`` is the real name — it is
    shown in the local window only and never leaves this process."""

    entity_id: int
    pseudonym: str
    entity_type: str
    canonical: str = field(repr=False)
    count: int = 0
    kept: bool = False
    is_new: bool = False
    user_marked: bool = False


@dataclass(frozen=True)
class Rendering:
    text: str = field(repr=False)
    sha256: str = ""
    segments: tuple[Segment, ...] = field(default=(), repr=False)
    entities: tuple[EntityRow, ...] = field(default=(), repr=False)
    risks: tuple[RiskAssessment, ...] = field(default=(), repr=False)
    # (offset in the leaving text, "U+XXXX") for every invisible character.
    invisible: tuple[tuple[int, str], ...] = ()
    # The occurrences the lawyer keeps in clear (alias forms included):
    # red_* in the leaving text, raw_* in the original. The window shades
    # them so an un-redaction is never indistinguishable from prose.
    kept: tuple[Segment, ...] = field(default=(), repr=False)

    @property
    def n_hidden(self) -> int:
        return len(self.segments)

    @property
    def n_kept(self) -> int:
        return sum(1 for e in self.entities if e.kept)

    @property
    def n_pseudonyms(self) -> int:
        return len({s.entity_id for s in self.segments})


@dataclass(frozen=True)
class Answer:
    redacted: str = field(repr=False)
    rehydrated: str = field(repr=False)
    legend: tuple[tuple[str, str, str], ...] = field(repr=False)  # (pseudonym, real name, type)
    unknown: tuple[str, ...] = ()
    shown_at: float = 0.0


@dataclass(frozen=True)
class MatterRow:
    id: str
    name: str = field(repr=False)
    mode: str = "strict"
    attested: bool = False
    last_used: str = ""


@dataclass
class Review:
    id: str
    status: ReviewStatus
    created_at: float
    last_interaction: float
    matter_id: str | None = None
    mode: Mode = Mode.STRICT
    mode_notice: str | None = None
    suffix: str | None = None
    phase: str | None = None
    phase_history: list[str] = field(default_factory=list)
    raw_text: str = field(default="", repr=False)
    base_detections: list[Detection] = field(default_factory=list, repr=False)
    user_detections: list[Detection] = field(default_factory=list, repr=False)
    created_entity_ids: list[int] = field(default_factory=list)
    added_surface_forms: list[tuple[int, str]] = field(default_factory=list, repr=False)
    kept: set[int] = field(default_factory=set)
    rendering: Rendering | None = field(default=None, repr=False)
    warnings: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    languages: dict[str, int] = field(default_factory=dict)
    unmodelled: tuple[str, ...] = ()
    n_invisible: int = 0
    error_key: str | None = None
    approved_at: float | None = None
    released_at: float | None = None
    approval_id: int | None = None
    payload_sha256: str | None = None
    frozen_text: str | None = field(default=None, repr=False)
    released_entities: list[Entity] = field(default_factory=list, repr=False)
    answers: list[Answer] = field(default_factory=list, repr=False)
    text_read: bool = False
    outcome: str | None = None
    last_poll_at: float | None = None
    generation: int = 0
    future: Future[None] | None = field(default=None, repr=False)

    def __repr__(self) -> str:  # never let a repr carry content into a log
        return f"Review(id={self.id!r}, status={self.status.value!r})"


@dataclass(frozen=True)
class CreateOutcome:
    review: Review
    already_open: bool
    browser_opened: bool


# ----- helpers -----


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def effective_mode(matter: Matter) -> tuple[Mode, str | None]:
    """Smart mode through the plugin requires a matter whose zero-retention
    attestation names Claude Desktop (``jude matter create --endpoint
    claude-desktop --zr``). Any other smart matter is processed in strict
    mode, with a one-line notice in the window."""

    if matter.mode != Mode.SMART:
        return Mode.STRICT, None
    if matter.zero_retention_attested and matter.llm_endpoint == ENDPOINT:
        return Mode.SMART, None
    return Mode.STRICT, "smart_fallback"


def check_models(langs: tuple[str, ...] | None = None) -> None:
    """Fail closed when a language component is missing. The spaCy detector
    would otherwise skip the language silently, which for a redaction tool
    means fewer detections, not an error. Dutch is checked by default."""

    missing = models.missing_components(langs or env.langs(), env.gliner_model())
    if missing:
        raise ModelsMissing(missing)


def default_pipeline_factory(store: Store, matter_id: str, redact_codenames: bool) -> Any:
    """Build the real detection pipeline for a matter. GLiNER defaults to
    the small checkpoint (a long-lived process should stay small); set
    ``JUDE_MCP_GLINER`` to choose another cached checkpoint. Passing
    ``redact_codenames`` explicitly keeps the constructor off the store."""

    langs = env.langs()
    check_models(langs)
    return DetectionPipeline(
        store=store,
        matter_id=matter_id,
        languages=langs,
        gliner_model=env.gliner_model(),
        redact_codenames=redact_codenames,
    )


def _warning_key(message: str) -> str | None:
    m = message.strip()
    if m.startswith("Document contains review comments"):
        return "comments"
    if m.startswith("Document contains tracked changes"):
        return "tracked_changes"
    if m.startswith(("Document core properties", "PDF metadata", "Workbook properties")):
        return "metadata"
    if "pages contain no extractable text" in m:
        return "image_pages"
    return None


def _read_text(path: Path) -> tuple[str, tuple[str, ...], bool]:
    """Read the document through its adapter. Returns the text with line
    endings normalised (so the browser's rendering and the hashed bytes
    agree), the adapter warnings mapped to static keys, and whether the
    adapter said the PDF is image-only. An ``ImportError`` from a missing
    optional reader propagates to the caller, which maps it to
    ``component_missing``."""

    suffix = path.suffix.lower()
    raw_warnings: list[str] = []
    needs_ocr = False
    if suffix == ".docx":
        extraction = DocxAdapter.read(path)
        text = extraction.text
        raw_warnings = list(extraction.warnings)
    elif suffix == ".xlsx":
        import openpyxl  # noqa: F401  — component_missing when absent

        extraction_x = XlsxAdapter.read(path)
        text = extraction_x.text
        raw_warnings = list(extraction_x.warnings)
    elif suffix == ".pdf":
        import pymupdf  # component_missing when absent

        with contextlib.suppress(Exception):
            # MuPDF writes its diagnostics to fd 2 from C; they may quote
            # the file. Plugin scope only.
            pymupdf.TOOLS.mupdf_display_errors(False)
            pymupdf.TOOLS.mupdf_display_warnings(False)
        extraction_p = PdfAdapter.read(path, enable_ocr=False)
        text = extraction_p.text
        raw_warnings = list(extraction_p.warnings)
        needs_ocr = not extraction_p.is_text_pdf
    else:
        text = TextAdapter.read(path)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    keys: list[str] = []
    for message in raw_warnings:
        if message.strip().startswith("PDF appears to be image-only"):
            needs_ocr = True
            continue
        key = _warning_key(message)
        if key is not None and key not in keys:
            keys.append(key)
    return text, tuple(keys), needs_ocr


def _component_for(suffix: str) -> tuple[str, ...]:
    return {"pdf": ("pdf",), "xlsx": ("xlsx",)}.get(suffix.lstrip(".").lower(), ())


def _is_invisible(c: str) -> bool:
    """Characters that are invisible on screen but leave with the text:
    format characters (zero-width, direction marks, soft hyphen), the tag
    block, and control characters other than newline and tab."""

    if c in _VISIBLE_CONTROLS:
        return False
    cat = unicodedata.category(c)
    return cat in ("Cf", "Cc") or 0xE0000 <= ord(c) <= 0xE007F


def _invisible_positions(text: str) -> tuple[tuple[int, str], ...]:
    return tuple((i, f"U+{ord(c):04X}") for i, c in enumerate(text) if _is_invisible(c))


def _os_user() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


def _extend_unique(target: list[Any], items: Iterable[Any]) -> None:
    for item in items:
        if item not in target:
            target.append(item)


def rehydrate_with(text: str, entities: list[Entity]) -> Answer:
    """Replace the pseudonyms of exactly these entities (the ones released
    for this document) by their real names. Pseudonym-shaped tokens that
    were not issued for the document are left as written and listed."""

    ordered = sorted(entities, key=lambda e: -len(e.pseudonym))
    present: list[tuple[str, str, str]] = []
    out = text
    for ent in ordered:
        pattern = re.compile(rf"(?<!\w){re.escape(ent.pseudonym)}(?!\w)")
        if pattern.search(text):
            present.append((ent.pseudonym, ent.canonical, ent.entity_type.value))
            out = pattern.sub(lambda _m, c=ent.canonical: c, out)
    issued = {e.pseudonym for e in entities}
    unknown = sorted({m.group(0) for m in _PSEUDONYM_RE.finditer(text)} - issued)
    present.sort(key=lambda row: (row[2], row[0]))
    return Answer(
        redacted=text,
        rehydrated=out,
        legend=tuple(present),
        unknown=tuple(unknown),
        shown_at=time.time(),
    )


# ----- the manager -----


class ReviewManager:
    def __init__(
        self,
        store: Store,
        pipeline_factory: Callable[[Store, str, bool], Any] | None = None,
        *,
        idle_ttl: float = DEFAULT_IDLE_TTL,
        approved_hold: float = DEFAULT_APPROVED_HOLD,
        max_age: float = DEFAULT_MAX_AGE,
        unload_after: float = DEFAULT_UNLOAD_AFTER,
        now: Callable[[], float] = time.time,
        open_browser: Callable[[str], bool] | None = None,
        url_factory: Callable[[], str] | None = None,
        tmp_dir: Path | None = None,
        lang: str = "en",
    ) -> None:
        self.store = store
        self._pipeline_factory = pipeline_factory or default_pipeline_factory
        self.idle_ttl = float(idle_ttl)
        self.approved_hold = float(approved_hold)
        self.max_age = float(max_age)
        self.unload_after = float(unload_after)
        self._now = now
        # Resolved at construction so a test (or a user) can replace
        # webbrowser.open before the manager exists.
        self._open_browser = open_browser or webbrowser.open
        self.url_factory = url_factory
        self._tmp_dir = tmp_dir
        self.lang = lang
        self._lock = threading.RLock()
        self._db = threading.RLock()
        self._reviews: dict[str, Review] = {}
        self._pipelines: dict[str, Any] = {}
        self._worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jude-prepare")
        self._last_browser_open: float | None = None
        self._last_activity_any: float = self._now()
        self._last_current_poll: float | None = None
        self._answer_times: list[float] = []
        # (matter_id, review_id, entity ids, surface forms) awaiting _db.
        self._pending_prunes: list[tuple[str, str, list[int], list[tuple[int, str]]]]
        self._pending_prunes = []
        # (approval_id, matter_id, review_id) awaiting _db.
        self._pending_closures: list[tuple[int, str, str]] = []
        self.browser_opens = 0

    # ----- lifecycle -----

    def close(self, grace: float = 5.0) -> None:
        """Stop accepting work; wait up to ``grace`` seconds for a running
        preparation. Whatever remains is covered by ``provisional_review_id``
        at the next start."""

        self._worker.shutdown(wait=False, cancel_futures=True)
        with self._lock:
            futures = [
                r.future
                for r in self._reviews.values()
                if r.future is not None and not r.future.done()
            ]
        deadline = time.monotonic() + max(0.0, grace)
        for fut in futures:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            # The worker records its own failures; a BaseException it let
            # through (SystemExit from a library) must not end stop().
            with contextlib.suppress(BaseException):
                fut.result(timeout=remaining)

    # ----- lookups -----

    def _get(self, review_id: str) -> Review:
        r = self._reviews.get(review_id)
        if r is None:
            raise UnknownReview()
        return r

    def get(self, review_id: str) -> Review:
        """The review object (local use only: window, tests)."""

        with self._lock:
            return self._get(review_id)

    def reviews(self) -> list[Review]:
        with self._lock:
            return sorted(self._reviews.values(), key=lambda r: r.created_at)

    def current_review_id(self) -> str | None:
        """What the window shows when it has no review id of its own: the
        open review, else the latest approved, released or closed one."""

        with self._lock:
            rs = sorted(self._reviews.values(), key=lambda r: r.created_at, reverse=True)
        for wanted in (PRE_APPROVAL, {ReviewStatus.APPROVED}, {ReviewStatus.RELEASED}, TERMINAL):
            for r in rs:
                if r.status in wanted:
                    return r.id
        return None

    def current(self) -> dict[str, Any]:
        """What a tab polls when it shows no live review: the current review
        id and status, so it can reload itself. Local only. Recording the
        poll lets ``create()`` skip opening a second tab."""

        now = self._now()
        with self._lock:
            self._last_current_poll = now
        rid = self.current_review_id()
        status: str | None = None
        if rid is not None:
            with contextlib.suppress(UnknownReview):
                status = self.get(rid).status.value
        return {"review_id": rid, "status": status}

    def status_of(self, review_id: str) -> ReviewStatus:
        with self._lock:
            r = self._get(review_id)
            self._expire_if_due(r)
            return r.status

    def public_status(self, review_id: str, lang: str | None = None) -> dict[str, str]:
        """The only review data a tool may return without the text: the id,
        the status and a static hint. Keys are a closed set."""

        with self._lock:
            r = self._get(review_id)
            self._expire_if_due(r)
            status = r.status
        return {
            "review_id": review_id,
            "status": status.value,
            "next": _s(_NEXT_KEY[status], lang or self.lang),
        }

    def window_state(self, review_id: str) -> dict[str, Any]:
        """What the local page polls every few seconds. Local only; may
        carry more than ``public_status`` but never a name. A poll is NOT
        an interaction: it never extends the review's clock."""

        now = self._now()
        with self._lock:
            r = self._get(review_id)
            self._expire_if_due(r)
            r.last_poll_at = now
            expires_at = self._expires_at_locked(r)
            return {
                "review_id": r.id,
                "status": r.status.value,
                "phase": r.phase,
                "sha256": r.rendering.sha256 if r.rendering else None,
                "answers": len(r.answers),
                "error_key": r.error_key,
                "missing": list(r.missing),
                "mode_notice": r.mode_notice,
                "expires_in": max(0, int(expires_at - now)) if expires_at is not None else None,
                "approval_id": r.approval_id,
                "status_line": (
                    "handed_once" if r.status == ReviewStatus.RELEASED else "nothing_left"
                ),
                "released_at": r.released_at,
            }

    def heartbeat(self, review_id: str) -> dict[str, Any]:
        """The page reports real input (a key, a click, a scroll in a visible
        tab). Extends the clock of a pre-approval review."""

        self.touch(review_id)
        with self._lock:
            r = self._get(review_id)
            expires_at = self._expires_at_locked(r)
            now = self._now()
        return {"expires_in": max(0, int(expires_at - now)) if expires_at is not None else None}

    def matters_for_window(self) -> list[MatterRow]:
        """Matters for the chooser in the local window, most recently used
        first. ``attested`` is true only when the zero-retention attestation
        names Claude Desktop. Never part of any tool result."""

        with self._db:
            matters = self.store.list_matters()
            last_used = self.store.last_used_by_matter()
        rows = [
            MatterRow(
                id=m.id,
                name=m.name,
                mode=m.mode.value,
                attested=bool(m.zero_retention_attested and m.llm_endpoint == ENDPOINT),
                last_used=(
                    last_used.get(m.id) or (m.created_at.isoformat() if m.created_at else "")
                ),
            )
            for m in matters
        ]
        rows.sort(key=lambda row: row.last_used, reverse=True)
        return rows

    # ----- creation and the window -----

    def create(self) -> CreateOutcome:
        now = self._now()
        existing: Review | None = None
        recent = False
        with self._lock:
            self._sweep_locked(now)
            for r in self._reviews.values():
                # An approved text that Claude has not collected yet is still
                # the lawyer's business (Withdraw lives on its screen): a
                # second conversation does not get to replace it.
                if r.status in PRE_APPROVAL or r.status == ReviewStatus.APPROVED:
                    existing = r
                    break
            if existing is not None:
                polls = [existing.last_poll_at, self._last_current_poll]
                last = max((t for t in polls if t is not None), default=float("-inf"))
                recent = now - last <= RECENT_POLL_WINDOW
            else:
                # Belt and braces: an approved review already counts as open
                # above, so this ceiling is reached only by hand.
                held = sum(1 for r in self._reviews.values() if r.status == ReviewStatus.APPROVED)
                if held >= MAX_APPROVED_HELD:
                    raise Busy()
                review = Review(
                    id=str(uuid.uuid4()),
                    status=ReviewStatus.AWAITING_MATTER,
                    created_at=now,
                    last_interaction=now,
                )
                self._reviews[review.id] = review
                self._last_activity_any = now
                tab_polling = (
                    self._last_current_poll is not None
                    and now - self._last_current_poll <= RECENT_POLL_WINDOW
                )
        if existing is not None:
            # No tab is looking at the open review: bring the window back.
            opened = False if recent else self._open_window()
            return CreateOutcome(review=existing, already_open=True, browser_opened=opened)
        self._flush_prunes()
        self._flush_closures()
        # A tab polling /api/current reloads itself when the review appears.
        opened = True if tab_polling else self._open_window()
        return CreateOutcome(review=review, already_open=False, browser_opened=opened)

    def _open_window(self) -> bool:
        """Open (or re-open) the local window. Rate limited: within
        ``BROWSER_MIN_INTERVAL`` of the previous open the tab is assumed to
        be there already and the call is a no-op that reports success."""

        now = self._now()
        with self._lock:
            if (
                self._last_browser_open is not None
                and now - self._last_browser_open < BROWSER_MIN_INTERVAL
            ):
                return True
            self._last_browser_open = now
        url = self.url_factory() if self.url_factory is not None else ""
        try:
            ok = bool(self._open_browser(url))
        except Exception:
            log.warning("browser open failed")
            ok = False
        if ok:
            self.browser_opens += 1
        return ok

    def open_window(self) -> bool:
        return self._open_window()

    # ----- the state machine -----

    def choose_matter(self, review_id: str, matter_id: str) -> Review:
        with self._db, self._lock:
            r = self._get(review_id)
            self._expire_if_due(r)
            if r.status not in (ReviewStatus.AWAITING_MATTER, ReviewStatus.AWAITING_FILE):
                raise IllegalTransition()
            matter = self.store.get_matter(matter_id)
            if matter is None:
                raise UnknownEntity("unknown_matter")
            r.matter_id = matter.id
            r.mode, r.mode_notice = effective_mode(matter)
            r.status = ReviewStatus.AWAITING_FILE
            self._touch_locked(r)
            return r

    def attach_file(self, review_id: str, suffix: str, data: bytes) -> Review:
        """Accept the document bytes. The caller passes the suffix only: the
        file name is confidential and never reaches this process."""

        suffix = (suffix or "").lower()
        if suffix not in SUPPORTED_SUFFIXES:
            raise BadUpload("unsupported_suffix")
        if len(data) > MAX_UPLOAD_BYTES:
            raise BadUpload("oversize")
        with self._lock:
            r = self._get(review_id)
            self._expire_if_due(r)
            if r.status != ReviewStatus.AWAITING_FILE or r.matter_id is None:
                raise IllegalTransition()
        # The temp copy is written BEFORE the review changes state: a disk
        # or permission error propagates to the caller (an HTTP 500) and the
        # review is still awaiting_file, so the lawyer can simply retry —
        # never "preparing" with no worker until the idle TTL.
        tmp_file = self._write_temp(data, suffix)
        with self._lock:
            r = self._get(review_id)
            if r.status != ReviewStatus.AWAITING_FILE or r.matter_id is None:
                shutil.rmtree(tmp_file.parent, ignore_errors=True)
                raise IllegalTransition()
            r.status = ReviewStatus.PREPARING
            r.suffix = suffix
            r.generation += 1
            generation = r.generation
            r.phase = "reading"
            r.phase_history.append("reading")
            self._touch_locked(r)
            try:
                r.future = self._worker.submit(self._prepare, r.id, generation, tmp_file)
            except RuntimeError:
                # The executor is shut down (the server is stopping): no
                # worker will ever run, so say so now rather than spin.
                r.status = ReviewStatus.FAILED
                r.error_key = "internal"
                r.phase = None
                matter_id = r.matter_id
                submit_failed = True
            else:
                submit_failed = False
        if submit_failed:
            shutil.rmtree(tmp_file.parent, ignore_errors=True)
            self._audit(
                matter_id, "mcp.fail",
                {"review_id": review_id, "error": "internal", "pruned": 0, "forms_removed": 0},
            )
            raise IllegalTransition()
        return r

    def wait_prepared(self, review_id: str, timeout: float = 30.0) -> ReviewStatus:
        """Block until the preparation worker has finished (tests, CLI)."""

        with self._lock:
            fut = self._get(review_id).future
        if fut is not None:
            # The worker records its own failures on the review.
            with contextlib.suppress(BaseException):
                fut.result(timeout=timeout)
        return self.status_of(review_id)

    def touch(self, review_id: str) -> None:
        with self._lock:
            r = self._get(review_id)
            self._expire_if_due(r)
            if r.status in PRE_APPROVAL:
                self._touch_locked(r)

    def render(self, review_id: str) -> Rendering:
        with self._lock:
            r = self._get(review_id)
            if r.rendering is None:
                raise IllegalTransition()
            return r.rendering

    def decide(self, review_id: str, entity_id: int, action: str) -> Rendering:
        """Keep an entity visible or hide it again. Re-applies ``redact()``
        to the stored spans; no detector runs."""

        if action not in ("keep", "hide"):
            raise BadRequest()
        with self._db, self._lock:
            r = self._get(review_id)
            self._expire_if_due(r)
            if r.status != ReviewStatus.AWAITING_REVIEW or r.rendering is None:
                raise IllegalTransition()
            if entity_id not in {row.entity_id for row in r.rendering.entities}:
                raise UnknownEntity()
            if action == "keep":
                r.kept.add(entity_id)
            else:
                r.kept.discard(entity_id)
            self._reapply(r)
            self._touch_locked(r)
            assert r.rendering is not None
            return r.rendering

    def decide_keep(self, review_id: str, entity_id: int) -> Rendering:
        return self.decide(review_id, entity_id, "keep")

    def decide_hide(self, review_id: str, entity_id: int) -> Rendering:
        return self.decide(review_id, entity_id, "hide")

    def mark(self, review_id: str, surface: str, entity_type: EntityType | str) -> Rendering:
        """Hide a term Jude missed: every exact occurrence becomes a USER
        detection resolved to one (possibly new, provisional) user-marked
        entity."""

        surface = surface.strip()
        if not surface or len(surface) > 200:
            raise BadRequest()
        etype = EntityType(entity_type)
        with self._db, self._lock:
            r = self._get(review_id)
            self._expire_if_due(r)
            if r.status != ReviewStatus.AWAITING_REVIEW or r.matter_id is None:
                raise IllegalTransition()
            starts = [m.start() for m in re.finditer(re.escape(surface), r.raw_text)]
            if not starts:
                raise UnknownEntity("not_found")
            existing = self.store.find_entity_by_surface_or_alias(
                r.matter_id, surface, etype, review_id=r.id
            )
            if existing is None:
                existing = self.store.create_entity(
                    matter_id=r.matter_id,
                    canonical=surface,
                    entity_type=etype,
                    user_marked=True,
                    provisional_review_id=r.id,
                )
                assert existing.id is not None
                r.created_entity_ids.append(existing.id)
            new_dets = [
                Detection(
                    text=surface,
                    start=s,
                    end=s + len(surface),
                    entity_type=etype,
                    source=DetectionSource.USER,
                )
                for s in starts
            ]
            r.base_detections = [
                d for d in r.base_detections if not any(_overlaps(d, n) for n in new_dets)
            ]
            r.user_detections = [
                d for d in r.user_detections if not any(_overlaps(d, n) for n in new_dets)
            ]
            r.user_detections.extend(new_dets)
            assert existing.id is not None
            r.kept.discard(existing.id)
            self._reapply(r)
            self._touch_locked(r)
            assert r.rendering is not None
            return r.rendering

    def approve(
        self,
        review_id: str,
        sha256: str,
        attest: bool = False,
        text_read: bool = False,
        ui_lang: str | None = None,
    ) -> Review:
        """The gate. The page sends the sha256 of the text it displayed; it
        must equal the sha256 of the current rendering, under the lock, or
        the approval is refused (``TextChanged``). The record, the
        confirmations of the provisional entities the text uses, the
        deletions of kept-new entities and the audit row are one
        transaction, committed BEFORE the status flips."""

        with self._db, self._lock:
            r = self._get(review_id)
            self._expire_if_due(r)
            if r.status == ReviewStatus.EXPIRED:
                raise ReviewExpired()
            if r.status != ReviewStatus.AWAITING_REVIEW or r.rendering is None:
                raise IllegalTransition()
            # The hash first: a stale page is refused whatever its checkbox says.
            if not isinstance(sha256, str) or sha256 != r.rendering.sha256:
                raise TextChanged()
            if not attest:
                raise AttestationRequired()
            assert r.matter_id is not None
            rendering = r.rendering
            created = set(r.created_entity_ids)
            to_delete = sorted(r.kept & created)
            used = {row.entity_id for row in rendering.entities}
            confirm = sorted((used | created) - set(to_delete))
            n_user_marked = sum(1 for e in rendering.entities if e.user_marked and not e.kept)
            # Every store READ happens before the record is committed: once
            # record_approval() returns, only attribute assignments follow,
            # so a locked database can never leave an orphan approvals row
            # that a retry would duplicate.
            emitted = {s.entity_id for s in rendering.segments}
            released_entities = [
                e
                for e in self.store.list_entities(r.matter_id, review_id=r.id)
                if e.id in emitted
            ]
            approver = _os_user()
            approval_id = self.store.record_approval(
                review_id=r.id,
                matter_id=r.matter_id,
                payload_sha256=rendering.sha256,
                chars=len(rendering.text),
                endpoint=ENDPOINT,
                endpoint_host=ENDPOINT_HOST,
                mode=r.mode.value,
                zero_retention=(r.mode == Mode.SMART),
                n_hidden=rendering.n_hidden,
                n_kept=rendering.n_kept,
                n_user_marked=n_user_marked,
                attestation=(
                    "items_reviewed_text_read" if text_read else "items_reviewed_text_opened"
                ),
                approver_os_user=approver,
                ui_lang=ui_lang,
                delete_entity_ids=to_delete,
                confirm_entity_ids=confirm,
            )
            # Committed. Only now does the review change state (no I/O below).
            r.created_entity_ids = [i for i in r.created_entity_ids if i not in to_delete]
            r.added_surface_forms = []
            r.approval_id = approval_id
            r.payload_sha256 = rendering.sha256
            r.frozen_text = rendering.text
            r.released_entities = released_entities
            r.text_read = bool(text_read)
            r.status = ReviewStatus.APPROVED
            r.phase = None
            r.approved_at = self._now()
            r.last_interaction = r.approved_at
            self._last_activity_any = r.approved_at
            return r

    def release(self, review_id: str) -> str:
        """Hand the approved text out, once. Re-hashes the frozen text
        against the approvals row; a mismatch fails the review closed."""

        with self._db, self._lock:
            r = self._get(review_id)
            if r.status == ReviewStatus.RELEASED:
                raise AlreadyReleased()
            self._expire_if_due(r)
            if r.status != ReviewStatus.APPROVED:
                raise NotReleased()
            assert r.matter_id is not None
            row = self.store.get_approval(r.approval_id) if r.approval_id is not None else None
            text = r.frozen_text
            ok = (
                row is not None
                and text is not None
                and sha256_hex(text) == row.payload_sha256 == r.payload_sha256
                and row.verified_at_send is None
                and row.outcome is None
            )
            if not ok or text is None:
                refused = (r.matter_id, "mcp.release.refused", json.dumps({"review_id": r.id}))
                if r.approval_id is not None:
                    self.store.set_approval_verified(r.approval_id, False, audit=refused)
                else:
                    self._audit(r.matter_id, "mcp.release.refused", {"review_id": r.id})
                r.status = ReviewStatus.FAILED
                r.error_key = "refused"
                r.outcome = "refused"
                r.frozen_text = None
                raise ReleaseRefused()
            assert r.approval_id is not None
            detail = {
                "review_id": r.id,
                "approval_id": r.approval_id,
                "sha256": r.payload_sha256,
                "chars": len(text),
            }
            # The verification and the audit line are ONE transaction, written
            # before the review changes state: if it fails (database locked by
            # another process) the review stays approved with its text, and the
            # next fetch_approved simply retries. The ledger never says
            # released for a text that was not handed over.
            self.store.set_approval_verified(
                r.approval_id, True, audit=(r.matter_id, "mcp.release", json.dumps(detail))
            )
            r.status = ReviewStatus.RELEASED
            r.outcome = "released"
            r.released_at = self._now()
            r.frozen_text = None  # single shot: the text lives in the model's copy now
            return text

    def cancel(self, review_id: str) -> Review:
        """Close a review that has not been released. Serialised with
        ``release`` through ``_db``, so a withdrawal either wins (the text
        never leaves and the approval is closed as ``withdrawn``) or arrives
        too late (the review is already released and is returned unchanged).
        A pre-approval cancel prunes what the review created and the
        surface forms it added; pre-existing entities are untouched."""

        with self._db, self._lock:
            r = self._get(review_id)
            if r.status in TERMINAL:
                return r
            was_approved = r.status == ReviewStatus.APPROVED
            r.status = ReviewStatus.CANCELLED
            r.generation += 1
            r.phase = None
            matter_id = r.matter_id
            if was_approved:
                r.frozen_text = None
                r.outcome = "withdrawn"
                if r.approval_id is not None and matter_id is not None:
                    self.store.close_approval(r.approval_id, "withdrawn")
                    self._audit(
                        matter_id,
                        "mcp.approved.withdrawn",
                        {"review_id": r.id, "approval_id": r.approval_id},
                    )
                return r
            ids = list(r.created_entity_ids)
            forms = list(r.added_surface_forms)
            r.created_entity_ids = []
            r.added_surface_forms = []
            r.frozen_text = None
            if matter_id is not None:
                pruned, removed = self._prune(matter_id, ids, forms)
                self._audit(
                    matter_id,
                    "mcp.cancel",
                    {"review_id": r.id, "pruned": pruned, "forms_removed": removed},
                )
            return r

    def sweep(self) -> None:
        """Expire what is due, prune and close the ledger rows best-effort,
        unload idle pipelines. Called by the window's sweep thread every
        15 s and before every ``create()``; never by the accept loop."""

        with self._lock:
            self._sweep_locked(self._now())
        self._flush_prunes()
        self._flush_closures()

    def show_answer(self, review_id: str, text: str) -> Answer:
        """Rehydrate a model answer with the entities released for this
        review only, store it for the local page, re-open the window if
        nobody is looking at it. The real names never return to the caller."""

        if len(text) > MAX_ANSWER_CHARS:
            raise AnswerTooLong()
        now = self._now()
        with self._lock:
            r = self._get(review_id)
            if r.status != ReviewStatus.RELEASED:
                raise NotReleased()
            self._answer_times = [t for t in self._answer_times if now - t < ANSWER_RATE_WINDOW]
            if len(self._answer_times) >= ANSWER_RATE_LIMIT:
                raise RateLimited()
            self._answer_times.append(now)
            answer = rehydrate_with(text, r.released_entities)
            r.answers.append(answer)
            recent_poll = r.last_poll_at is not None and now - r.last_poll_at <= RECENT_POLL_WINDOW
        if not recent_poll:
            self._open_window()
        return answer

    # ----- internals -----

    def _touch_locked(self, r: Review) -> None:
        now = self._now()
        r.last_interaction = now
        self._last_activity_any = now

    def _expires_at_locked(self, r: Review) -> float | None:
        if r.status in PRE_APPROVAL:
            return min(r.last_interaction + self.idle_ttl, r.created_at + self.max_age)
        if r.status == ReviewStatus.APPROVED and r.approved_at is not None:
            return r.approved_at + self.approved_hold
        return None

    def expires_at(self, review_id: str) -> float | None:
        with self._lock:
            return self._expires_at_locked(self._get(review_id))

    def _expire_if_due(self, r: Review) -> None:
        """Flip to ``expired`` when due. Must hold ``_lock``. Pruning and
        ledger closure are deferred to the flush methods (they need ``_db``)."""

        now = self._now()
        due = self._expires_at_locked(r)
        if due is None or now < due:
            return
        if r.status in PRE_APPROVAL:
            r.status = ReviewStatus.EXPIRED
            r.generation += 1
            r.phase = None
            if r.matter_id is not None:
                self._pending_prunes.append(
                    (r.matter_id, r.id, list(r.created_entity_ids), list(r.added_surface_forms))
                )
            r.created_entity_ids = []
            r.added_surface_forms = []
        elif r.status == ReviewStatus.APPROVED:
            # The record stays; the entities stay (they were approved).
            r.status = ReviewStatus.EXPIRED
            r.frozen_text = None
            r.outcome = "expired"
            if r.approval_id is not None and r.matter_id is not None:
                self._pending_closures.append((r.approval_id, r.matter_id, r.id))

    def _sweep_locked(self, now: float) -> None:
        for r in list(self._reviews.values()):
            self._expire_if_due(r)
        if self._pipelines and now - self._last_activity_any >= self.unload_after:
            self._pipelines.clear()
        # Forget closed reviews after twice the approved hold so memory stays flat.
        for rid, r in list(self._reviews.items()):
            if r.status not in TERMINAL:
                continue
            last = max(
                r.last_interaction,
                r.approved_at or 0.0,
                r.released_at or 0.0,
                r.answers[-1].shown_at if r.answers else 0.0,
            )
            if now - last > 2 * self.approved_hold:
                del self._reviews[rid]

    def _flush_prunes(self) -> None:
        with self._lock:
            pending, self._pending_prunes = self._pending_prunes, []
        if not pending:
            return
        if not self._db.acquire(timeout=0.5):
            with self._lock:
                self._pending_prunes = pending + self._pending_prunes
            return
        try:
            for matter_id, review_id, ids, forms in pending:
                pruned, removed = self._prune(matter_id, ids, forms)
                self._audit(
                    matter_id,
                    "mcp.expire",
                    {"review_id": review_id, "pruned": pruned, "forms_removed": removed},
                )
        finally:
            self._db.release()

    def _flush_closures(self) -> None:
        with self._lock:
            pending, self._pending_closures = self._pending_closures, []
        if not pending:
            return
        if not self._db.acquire(timeout=0.5):
            with self._lock:
                self._pending_closures = pending + self._pending_closures
            return
        try:
            for approval_id, matter_id, review_id in pending:
                self.store.close_approval(approval_id, "expired")
                self._audit(
                    matter_id,
                    "mcp.approved.expired",
                    {"review_id": review_id, "approval_id": approval_id},
                )
        finally:
            self._db.release()

    def _prune(
        self, matter_id: str, ids: list[int], forms: list[tuple[int, str]]
    ) -> tuple[int, int]:
        """Delete the entities a review created and the surface forms it
        added to pre-existing entities. Returns immediately when both lists
        are empty; writes no audit line (``_audit`` does, separately)."""

        if not ids and not forms:
            return 0, 0
        with self._db:
            for entity_id in ids:
                self.store.delete_entity(entity_id)
            for entity_id, form in forms:
                if entity_id in ids:
                    continue
                self.store.remove_surface_form(entity_id, form)
        return len(ids), len([f for f in forms if f[0] not in ids])

    def _audit(self, matter_id: str, action: str, detail: dict[str, Any]) -> None:
        with self._db:
            self.store._log(matter_id, action, json.dumps(detail))

    def _tmp_root(self) -> Path:
        root = self._tmp_dir or (jude_home() / "mcp" / "tmp")
        root.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(OSError):
            os.chmod(root, 0o700)
        return root

    def _write_temp(self, data: bytes, suffix: str) -> Path:
        tmp_dir = Path(tempfile.mkdtemp(prefix="r-", dir=self._tmp_root()))
        path = tmp_dir / f"{secrets.token_hex(8)}{suffix}"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, data)
        finally:
            os.close(fd)
        return path

    def _pipeline_for(
        self, matter_id: str, redact_codenames: bool, review_id: str | None = None
    ) -> Any:
        """The detection pipeline of a matter, built on first use OUTSIDE
        ``_db`` (model loading takes seconds and must not block the window
        or a release). Rebuilt when the matter's codename toggle changed,
        because the detectors fix that flag at construction. ``review_id``
        is handed to the pipeline so its dictionary sees this review's
        provisional entities (second pass) and nobody else's."""

        with self._lock:
            pipeline = self._pipelines.get(matter_id)
        if (
            pipeline is not None
            and getattr(pipeline, "redact_codenames", redact_codenames) != redact_codenames
        ):
            pipeline = None
        if pipeline is None:
            pipeline = self._pipeline_factory(self.store, matter_id, redact_codenames)
            with self._lock:
                self._pipelines[matter_id] = pipeline
        with contextlib.suppress(AttributeError):
            pipeline.review_id = review_id
        return pipeline

    def _provider_for(self, mode: Mode) -> ContextProvider | None:
        # Offline chain only: bundled dataset + EUR-Lex decoder. Wikipedia
        # is an outbound call and is never built here.
        return make_provider(use_wikipedia=False) if mode == Mode.SMART else None

    def _set_phase(self, review_id: str, generation: int, phase: str) -> None:
        with self._lock:
            r = self._reviews.get(review_id)
            if r is None or r.generation != generation or r.status != ReviewStatus.PREPARING:
                return
            r.phase = phase
            r.phase_history.append(phase)

    def _is_current(self, review_id: str, generation: int) -> bool:
        """Must hold ``_lock``."""

        r = self._reviews.get(review_id)
        return r is not None and r.generation == generation and r.status == ReviewStatus.PREPARING

    def _prepare(self, review_id: str, generation: int, tmp_file: Path) -> None:
        """Worker: read (no lock), delete the temp file, load the models and
        detect (no lock), redact under ``_db``, commit the rendering under
        both locks. Any failure records a key only and prunes what the
        review created."""

        matter_id: str | None = None
        created: list[int] = []
        forms: list[tuple[int, str]] = []
        try:
            try:
                text, warnings, needs_ocr = _read_text(tmp_file)
            except ImportError as exc:
                raise _PrepareFailure(
                    "component_missing", missing=_component_for(tmp_file.suffix)
                ) from exc
            except Exception as exc:
                raise _PrepareFailure("unreadable") from exc
            finally:
                shutil.rmtree(tmp_file.parent, ignore_errors=True)
            if not text.strip():
                raise _PrepareFailure("needs_ocr" if needs_ocr else "no_text")
            if len(text) > MAX_TEXT_CHARS:
                raise _PrepareFailure("too_long")
            # 3. snapshot the review (no I/O under _lock)
            with self._lock:
                if not self._is_current(review_id, generation):
                    return
                r = self._reviews[review_id]
                matter_id, mode = r.matter_id, r.mode
                r.warnings = warnings
                r.n_invisible = sum(1 for c in text if _is_invisible(c))
            assert matter_id is not None
            # 4. what the pipeline needs from the store, quickly, under _db
            with self._db:
                matter = self.store.get_matter(matter_id)
            codenames = bool(matter.redact_codenames) if matter is not None else False
            # 5. models — NO _db
            self._set_phase(review_id, generation, "loading_models")
            try:
                pipeline = self._pipeline_for(matter_id, codenames, review_id)
            except ModelsMissing as exc:
                raise _PrepareFailure("models_missing", missing=exc.missing) from exc
            except (OSError, ImportError) as exc:
                raise _PrepareFailure("models_missing") from exc
            provider = self._provider_for(mode)
            # 6. first pass — no lock
            self._set_phase(review_id, generation, "detecting")
            first = pipeline.detect(text)
            # 7. redact under _db; remember what we created
            with self._db:
                first_result = redact(
                    text, first, self.store, matter_id, mode, provider, review_id=review_id
                )
            _extend_unique(created, first_result.created_entity_ids)
            _extend_unique(forms, first_result.added_surface_forms)
            with self._lock:
                if self._is_current(review_id, generation):
                    r = self._reviews[review_id]
                    _extend_unique(r.created_entity_ids, created)
                    _extend_unique(r.added_surface_forms, forms)
            # 8. second pass: the dictionary now knows the first pass's names
            second = pipeline.detect(text)
            new = [d for d in second if not any(_overlaps(d, f) for f in first)]
            # 9. re-redact the original text with the union, under _db
            if new:
                merged = sorted([*first, *new], key=lambda d: d.start)
                with self._db:
                    result = redact(
                        text, merged, self.store, matter_id, mode, provider, review_id=review_id
                    )
                _extend_unique(created, result.created_entity_ids)
                _extend_unique(forms, result.added_surface_forms)
            else:
                result = first_result
            report = getattr(pipeline, "language_report", None)
            languages, unmodelled = report() if callable(report) else ({}, ())
            # 10. commit under both locks
            with self._db, self._lock:
                if not self._is_current(review_id, generation):
                    # Cancelled or expired while we worked: undo our creations.
                    pruned, removed = self._prune(matter_id, created, forms)
                    self._audit(
                        matter_id,
                        "mcp.discard",
                        {"review_id": review_id, "pruned": pruned, "forms_removed": removed},
                    )
                    return
                r = self._reviews[review_id]
                _extend_unique(r.created_entity_ids, created)
                _extend_unique(r.added_surface_forms, forms)
                r.raw_text = text
                r.base_detections = list(result.detections)
                r.languages = dict(languages)
                r.unmodelled = tuple(unmodelled)
                r.phase = "rendering"
                r.phase_history.append("rendering")
                self._reapply(r)
                r.status = ReviewStatus.AWAITING_REVIEW
                r.phase = None
                self._touch_locked(r)
        except _PrepareFailure as failure:
            log.warning("preparation failed", exc_info=True)
            self._fail(
                review_id, generation, failure.key,
                missing=failure.missing, matter_id=matter_id, created=created, forms=forms,
            )
        except Exception:
            log.error("preparation failed", exc_info=True)
            self._fail(
                review_id, generation, "internal",
                matter_id=matter_id, created=created, forms=forms,
            )
        except BaseException:
            # SystemExit / KeyboardInterrupt from a library (sys.exit on a
            # fatal condition): record the failure and prune, then let the
            # executor keep the exception — the review must not stay
            # "preparing" with its phase frozen until the idle TTL.
            log.error("preparation aborted", exc_info=True)
            self._fail(
                review_id, generation, "internal",
                matter_id=matter_id, created=created, forms=forms,
            )
            raise

    def _fail(
        self,
        review_id: str,
        generation: int,
        key: str,
        *,
        missing: tuple[str, ...] = (),
        matter_id: str | None = None,
        created: list[int] | None = None,
        forms: list[tuple[int, str]] | None = None,
    ) -> None:
        ids: list[int] = list(created or [])
        fs: list[tuple[int, str]] = list(forms or [])
        with self._lock:
            r = self._reviews.get(review_id)
            current = (
                r is not None
                and r.generation == generation
                and r.status == ReviewStatus.PREPARING
            )
            if current:
                assert r is not None
                r.status = ReviewStatus.FAILED
                r.error_key = key
                r.missing = tuple(missing)
                r.phase = None
                _extend_unique(ids, r.created_entity_ids)
                _extend_unique(fs, r.added_surface_forms)
                r.created_entity_ids = []
                r.added_surface_forms = []
                matter_id = matter_id or r.matter_id
        if matter_id is not None:
            pruned, removed = self._prune(matter_id, ids, fs)
            self._audit(
                matter_id,
                "mcp.fail",
                {"review_id": review_id, "error": key, "pruned": pruned, "forms_removed": removed},
            )

    def _reapply(self, r: Review) -> None:
        """Rebuild the rendering from the stored spans and the decisions.
        Must hold ``_db`` and ``_lock``. Never runs a detector."""

        assert r.matter_id is not None
        provider = self._provider_for(r.mode)
        dets = sorted([*r.base_detections, *r.user_detections], key=lambda d: d.start)
        full = redact(r.raw_text, dets, self.store, r.matter_id, r.mode, provider, review_id=r.id)
        _extend_unique(r.created_entity_ids, full.created_entity_ids)
        _extend_unique(r.added_surface_forms, full.added_surface_forms)
        kept_spans = {(s.raw_start, s.raw_end) for s in full.segments if s.entity_id in r.kept}
        if kept_spans:
            shown_dets = [d for d in dets if (d.start, d.end) not in kept_spans]
            shown = redact(
                r.raw_text, shown_dets, self.store, r.matter_id, r.mode, provider, review_id=r.id
            )
        else:
            shown = full
        r.rendering = self._rendering_from(r, full, shown)

    def _rendering_from(
        self, r: Review, full: RedactionResult, shown: RedactionResult
    ) -> Rendering:
        counts = Counter(s.entity_id for s in full.segments)
        created = set(r.created_entity_ids)
        rows = tuple(
            EntityRow(
                entity_id=e.id,
                pseudonym=e.pseudonym,
                entity_type=e.entity_type.value,
                canonical=e.canonical,
                count=counts.get(e.id, 0),
                kept=e.id in r.kept,
                is_new=e.id in created,
                user_marked=e.user_marked,
            )
            for e in sorted(full.entities_used, key=lambda e: (e.entity_type.value, e.pseudonym))
            if e.id is not None
        )
        segments = tuple(
            Segment(
                red_start=s.red_start,
                red_end=s.red_end,
                raw_start=s.raw_start,
                raw_end=s.raw_end,
                entity_id=s.entity_id,
            )
            for s in shown.segments
        )
        risks = tuple(
            a
            for a in assess_risks(shown.redacted_text, list(full.entities_used), r.mode)
            if a.score > 0
        )
        return Rendering(
            text=shown.redacted_text,
            sha256=sha256_hex(shown.redacted_text),
            segments=segments,
            entities=rows,
            risks=risks,
            invisible=_invisible_positions(shown.redacted_text),
            kept=_kept_segments(full, shown, r.kept),
        )


def _kept_segments(
    full: RedactionResult, shown: RedactionResult, kept_ids: set[int]
) -> tuple[Segment, ...]:
    """The raw spans of the kept entities (every occurrence ``full`` resolved
    to them, alias forms included) positioned in the shown text: a kept span
    moves by the length difference of every shown replacement before it."""

    if not kept_ids:
        return ()
    shown_segs = sorted(shown.segments, key=lambda s: s.raw_start)
    out: list[Segment] = []
    for seg in full.segments:
        if seg.entity_id not in kept_ids:
            continue
        delta = sum(
            (s.red_end - s.red_start) - (s.raw_end - s.raw_start)
            for s in shown_segs
            if s.raw_end <= seg.raw_start
        )
        out.append(
            Segment(
                red_start=seg.raw_start + delta,
                red_end=seg.raw_end + delta,
                raw_start=seg.raw_start,
                raw_end=seg.raw_end,
                entity_id=seg.entity_id,
            )
        )
    return tuple(sorted(out, key=lambda s: s.red_start))


def _overlaps(a: Detection, b: Detection) -> bool:
    return not (a.end <= b.start or b.end <= a.start)
