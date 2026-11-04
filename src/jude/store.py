from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from .types import (
    Approval,
    Conversation,
    Entity,
    EntityType,
    Matter,
    Message,
    MessageRole,
    Mode,
    normalize_surface,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS matters (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'strict',
    llm_endpoint TEXT NOT NULL DEFAULT 'anthropic',
    zero_retention_attested INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    matter_id TEXT NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    canonical TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    pseudonym TEXT NOT NULL,
    public_context TEXT,
    user_marked INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE(matter_id, pseudonym)
);

CREATE TABLE IF NOT EXISTS surface_forms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    form TEXT NOT NULL,
    normalized TEXT NOT NULL,
    UNIQUE(entity_id, normalized)
);

CREATE INDEX IF NOT EXISTS idx_surface_normalized
    ON surface_forms(normalized);

CREATE INDEX IF NOT EXISTS idx_entities_matter
    ON entities(matter_id);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    matter_id TEXT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT,
    ts TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pseudonym_counters (
    matter_id TEXT NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL,
    next_n INTEGER NOT NULL,
    PRIMARY KEY (matter_id, entity_type)
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    matter_id TEXT NOT NULL REFERENCES matters(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_conversations_matter
    ON conversations(matter_id, created_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    redacted_text TEXT NOT NULL,
    display_text TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id, id ASC);

-- The approval ledger (docs/review-ux.md §7, trimmed to what the MCP
-- plugin records today). Written BEFORE any text leaves; re-verified at
-- release time. One row per approved document.
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id TEXT,
    matter_id TEXT NOT NULL,
    purpose TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    chars INTEGER,
    endpoint TEXT NOT NULL,
    endpoint_host TEXT NOT NULL,
    model TEXT,
    mode TEXT,
    zero_retention INTEGER,
    n_hidden INTEGER,
    n_kept INTEGER,
    n_user_marked INTEGER,
    attestation TEXT NOT NULL,
    approver_os_user TEXT NOT NULL,
    ui_lang TEXT,
    verified_at_send INTEGER,
    approved_at TEXT NOT NULL,
    released_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_approvals_matter
    ON approvals(matter_id, approved_at DESC);
"""


class Store:
    """SQLite-backed store for matters, entities, and surface-form aliases.

    All data is per-matter and stays on the user's disk. The database file
    itself contains real names — treat it as confidential.
    """

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False is required because Streamlit reruns the
        # script on different threads (the WebSocket dispatcher uses a thread
        # pool). SQLite itself serializes operations under the default
        # threading mode, so cross-thread use is safe for our single-user
        # workload — we just need Python to stop guarding it.
        self._conn = sqlite3.connect(
            self.db_path, isolation_level=None, check_same_thread=False
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._conn.executescript(SCHEMA)
        self._migrate_v2()
        self._migrate_v3()

    def _migrate_v2(self) -> None:
        """Add columns added after the original schema. Idempotent."""

        cols = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(matters)").fetchall()
        }
        if "llm_model" not in cols:
            self._conn.execute("ALTER TABLE matters ADD COLUMN llm_model TEXT")
        if "notes" not in cols:
            self._conn.execute("ALTER TABLE matters ADD COLUMN notes TEXT")
        if "redact_codenames" not in cols:
            self._conn.execute(
                "ALTER TABLE matters ADD COLUMN redact_codenames INTEGER NOT NULL DEFAULT 0"
            )

    def _migrate_v3(self) -> None:
        """Columns the MCP plugin needs. Idempotent.

        ``entities.provisional_review_id`` marks an entity created by a
        review that has not been approved yet; an approval sets it back to
        NULL, a cancel deletes the row, and ``recover_after_restart`` sweeps
        what a crash left behind. ``approvals.outcome`` says how each
        approval ended (released, refused, withdrawn, expired,
        lost_on_restart), so the ledger never stays silent."""

        ecols = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(entities)").fetchall()
        }
        if "provisional_review_id" not in ecols:
            self._conn.execute("ALTER TABLE entities ADD COLUMN provisional_review_id TEXT")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_entities_provisional "
            "ON entities(provisional_review_id)"
        )
        acols = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(approvals)").fetchall()
        }
        if "outcome" not in acols:
            self._conn.execute("ALTER TABLE approvals ADD COLUMN outcome TEXT")

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @contextmanager
    def _tx(self, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        """One transaction. ``immediate`` takes the write lock at BEGIN, so
        two connections (two processes on one jude.db) serialise on it
        instead of both reading the same counter."""

        self._conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
        try:
            yield self._conn
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise

    # ----- matters -----

    def create_matter(
        self,
        name: str,
        mode: Mode = Mode.STRICT,
        llm_endpoint: str = "anthropic",
        zero_retention_attested: bool = False,
        matter_id: str | None = None,
        redact_codenames: bool = False,
    ) -> Matter:
        mid = matter_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self._tx() as c:
            c.execute(
                "INSERT INTO matters (id, name, mode, llm_endpoint, "
                "zero_retention_attested, redact_codenames, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (mid, name, mode.value, llm_endpoint, int(zero_retention_attested),
                 int(redact_codenames), now),
            )
        self._log(mid, "matter.create", json.dumps({"name": name, "mode": mode.value}))
        return Matter(
            id=mid,
            name=name,
            mode=mode,
            llm_endpoint=llm_endpoint,
            zero_retention_attested=zero_retention_attested,
            redact_codenames=redact_codenames,
            created_at=datetime.fromisoformat(now),
        )

    def set_redact_codenames(self, matter_id: str, flag: bool) -> None:
        """Per-matter opt-in: redact deal codenames ("Project X" and the
        bare "X") like any party name. Off by default (ruling of
        13 October 2026)."""

        with self._tx() as c:
            c.execute(
                "UPDATE matters SET redact_codenames = ? WHERE id = ?",
                (int(flag), matter_id),
            )
        self._log(matter_id, "matter.redact_codenames", json.dumps({"flag": bool(flag)}))

    def get_matter(self, matter_id: str) -> Matter | None:
        row = self._conn.execute(
            "SELECT * FROM matters WHERE id = ?", (matter_id,)
        ).fetchone()
        return self._row_to_matter(row) if row else None

    def list_matters(self) -> list[Matter]:
        rows = self._conn.execute(
            "SELECT * FROM matters ORDER BY created_at DESC"
        ).fetchall()
        return [self._row_to_matter(r) for r in rows]

    def set_matter_notes(self, matter_id: str, notes: str | None) -> None:
        """Update the matter's free-text working-notes field. None or
        empty-after-strip clears the notes."""

        cleaned = notes.strip() if isinstance(notes, str) else None
        with self._tx() as c:
            c.execute(
                "UPDATE matters SET notes = ? WHERE id = ?",
                (cleaned or None, matter_id),
            )

    def set_llm_endpoint(
        self, matter_id: str, endpoint: str, model: str | None = None
    ) -> None:
        with self._tx() as c:
            c.execute(
                "UPDATE matters SET llm_endpoint = ?, llm_model = ? WHERE id = ?",
                (endpoint, model, matter_id),
            )
        self._log(
            matter_id,
            "matter.set_llm_endpoint",
            json.dumps({"endpoint": endpoint, "model": model}),
        )

    def set_mode(
        self,
        matter_id: str,
        mode: Mode,
        zero_retention_attested: bool = False,
    ) -> None:
        if mode == Mode.SMART and not zero_retention_attested:
            raise ValueError(
                "Smart mode requires the user to attest a zero-retention LLM endpoint."
            )
        with self._tx() as c:
            c.execute(
                "UPDATE matters SET mode = ?, zero_retention_attested = ? WHERE id = ?",
                (mode.value, int(zero_retention_attested), matter_id),
            )
        self._log(
            matter_id,
            "matter.set_mode",
            json.dumps({"mode": mode.value, "zr": zero_retention_attested}),
        )

    @staticmethod
    def _row_to_matter(row: sqlite3.Row) -> Matter:
        try:
            llm_model = row["llm_model"]
        except (KeyError, IndexError):
            llm_model = None
        try:
            notes = row["notes"]
        except (KeyError, IndexError):
            notes = None
        try:
            redact_codenames = bool(row["redact_codenames"])
        except (KeyError, IndexError):
            redact_codenames = False
        return Matter(
            id=row["id"],
            name=row["name"],
            mode=Mode(row["mode"]),
            llm_endpoint=row["llm_endpoint"],
            llm_model=llm_model,
            zero_retention_attested=bool(row["zero_retention_attested"]),
            notes=notes,
            redact_codenames=redact_codenames,
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    # ----- entities -----

    # Provisional entities (``provisional_review_id`` set) belong to one
    # unfinished plugin review. Every reader takes ``review_id``: the plugin
    # passes its review's id and sees its own provisional rows; the CLI, the
    # Streamlit UI and ``rehydrate()`` pass nothing and see confirmed rows
    # only, so a pseudonym that a cancel or a restart may still delete is
    # never reused by another front-end (nor shown as a known entity).
    _VISIBLE = "(e.provisional_review_id IS NULL OR e.provisional_review_id = ?)"

    def find_entity_by_surface(
        self, matter_id: str, surface: str, *, review_id: str | None = None
    ) -> Entity | None:
        norm = normalize_surface(surface)
        if not norm:
            return None
        row = self._conn.execute(
            f"""
            SELECT e.* FROM entities e
            JOIN surface_forms s ON s.entity_id = e.id
            WHERE e.matter_id = ? AND s.normalized = ? AND {self._VISIBLE}
            LIMIT 1
            """,
            (matter_id, norm, review_id),
        ).fetchone()
        return self._row_to_entity(row) if row else None

    def find_entity_by_surface_or_alias(
        self,
        matter_id: str,
        surface: str,
        entity_type: EntityType,
        *,
        review_id: str | None = None,
    ) -> Entity | None:
        """Look up an entity by surface form, falling back to a
        substring-token alias for PERSON and ORG types. ``review_id`` scopes
        the lookup to confirmed entities plus that review's provisional ones.

        Solves the duplicate-pseudonym problem when a document mentions
        someone in the header by full name ("Marie-Claire Lefèvre") and
        in the sign-off by first name only ("Marie-Claire"): the second
        encounter resolves to the same entity instead of creating a new
        one.

        Aliasing is conservative:
          * Only fires for PERSON and ORG (token-substring matching
            against an EMAIL or IBAN would create false positives).
          * Refuses to match when more than one entity of the same type
            could plausibly own the surface — the user resolves the
            ambiguity manually via the merge UI.
          * Token-aligned: "Pioneer" matches "Pioneer Industries SA"
            but not "PioneerX".
        """

        exact = self.find_entity_by_surface(matter_id, surface, review_id=review_id)
        if exact and exact.entity_type == entity_type:
            return exact

        if entity_type not in (EntityType.PERSON, EntityType.ORG):
            return None

        norm = normalize_surface(surface)
        if not norm:
            return None
        needle_tokens = norm.split()
        if not needle_tokens:
            return None

        candidates: list[Entity] = []
        for ent in self.list_entities(matter_id, review_id=review_id):
            if ent.entity_type != entity_type:
                continue
            for form in {ent.canonical, *ent.surface_forms}:
                f_norm = normalize_surface(form)
                if not f_norm:
                    continue
                f_tokens = f_norm.split()
                if _is_token_subsequence(needle_tokens, f_tokens):
                    candidates.append(ent)
                    break
        if len(candidates) == 1:
            return candidates[0]
        return None

    def find_entity_by_pseudonym(
        self, matter_id: str, pseudonym: str, *, review_id: str | None = None
    ) -> Entity | None:
        row = self._conn.execute(
            f"SELECT e.* FROM entities e WHERE e.matter_id = ? AND e.pseudonym = ? "
            f"AND {self._VISIBLE}",
            (matter_id, pseudonym, review_id),
        ).fetchone()
        return self._row_to_entity(row) if row else None

    def create_entity(
        self,
        matter_id: str,
        canonical: str,
        entity_type: EntityType,
        surface_forms: set[str] | None = None,
        public_context: str | None = None,
        user_marked: bool = False,
        *,
        provisional_review_id: str | None = None,
    ) -> Entity:
        """Create an entity with the next pseudonym of its type.

        The counter update and the insert are ONE ``BEGIN IMMEDIATE``
        transaction, so two processes on the same database can never both
        read ``next_n = 7`` and both issue ``Org7``. An entity created on
        behalf of an unfinished review carries ``provisional_review_id``
        and writes no ``entity.create`` audit line (which would carry the
        real name): it is logged as ``entity.confirm`` at approval or
        deleted on cancel."""

        forms = set(surface_forms or set())
        forms.add(canonical)
        now = datetime.now(timezone.utc).isoformat()
        with self._tx(immediate=True) as c:
            pseudonym = self._allocate_pseudonym(c, matter_id, entity_type)
            cur = c.execute(
                "INSERT INTO entities (matter_id, canonical, entity_type, pseudonym, "
                "public_context, user_marked, created_at, provisional_review_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    matter_id,
                    canonical,
                    entity_type.value,
                    pseudonym,
                    public_context,
                    int(user_marked),
                    now,
                    provisional_review_id,
                ),
            )
            entity_id = int(cur.lastrowid)
            for form in forms:
                norm = normalize_surface(form)
                if norm:
                    c.execute(
                        "INSERT OR IGNORE INTO surface_forms (entity_id, form, normalized) "
                        "VALUES (?, ?, ?)",
                        (entity_id, form, norm),
                    )
            if provisional_review_id is None:
                self._log(
                    matter_id,
                    "entity.create",
                    json.dumps({"canonical": canonical, "pseudonym": pseudonym}),
                )
        return Entity(
            id=entity_id,
            matter_id=matter_id,
            canonical=canonical,
            entity_type=entity_type,
            pseudonym=pseudonym,
            public_context=public_context,
            user_marked=user_marked,
            surface_forms=forms,
            created_at=datetime.fromisoformat(now),
        )

    def add_surface_form(self, entity_id: int, form: str) -> bool:
        """Add a surface form. Returns True when a row was inserted, False
        when the (normalised) form was already there or is empty."""

        norm = normalize_surface(form)
        if not norm:
            return False
        with self._tx() as c:
            cur = c.execute(
                "INSERT OR IGNORE INTO surface_forms (entity_id, form, normalized) "
                "VALUES (?, ?, ?)",
                (entity_id, form, norm),
            )
            inserted = cur.rowcount == 1
        return inserted

    def remove_surface_form(self, entity_id: int, form: str) -> None:
        """Undo ``add_surface_form`` (a cancelled review leaves a
        pre-existing entity's dictionary as it found it)."""

        norm = normalize_surface(form)
        if not norm:
            return
        with self._tx() as c:
            c.execute(
                "DELETE FROM surface_forms WHERE entity_id = ? AND normalized = ?",
                (entity_id, norm),
            )

    def set_public_context(self, entity_id: int, context: str | None) -> None:
        with self._tx() as c:
            c.execute(
                "UPDATE entities SET public_context = ? WHERE id = ?",
                (context, entity_id),
            )

    def delete_entity(self, entity_id: int) -> None:
        with self._tx() as c:
            c.execute("DELETE FROM entities WHERE id = ?", (entity_id,))

    def merge_entities(self, matter_id: str, primary_id: int, secondary_id: int) -> Entity:
        """Merge `secondary` into `primary`.

        All surface forms of secondary are moved onto primary; secondary's
        canonical becomes a surface form of primary; if primary has no
        public_context, secondary's is inherited. Secondary is then deleted.

        The primary's pseudonym is preserved; secondary's pseudonym is freed
        and not reused (gaps in the numbering are intentional and audit-friendly).
        """

        if primary_id == secondary_id:
            raise ValueError("Cannot merge an entity with itself.")
        primary = self._fetch_entity_by_id(matter_id, primary_id)
        secondary = self._fetch_entity_by_id(matter_id, secondary_id)
        if primary is None or secondary is None:
            raise ValueError("Both entities must exist in the same matter.")
        if primary.entity_type != secondary.entity_type:
            raise ValueError(
                f"Cannot merge entities of different types: "
                f"{primary.entity_type.value} vs {secondary.entity_type.value}."
            )

        sec_forms = secondary.surface_forms | {secondary.canonical}
        with self._tx() as c:
            for form in sec_forms:
                norm = normalize_surface(form)
                if not norm:
                    continue
                c.execute(
                    "INSERT OR IGNORE INTO surface_forms (entity_id, form, normalized) "
                    "VALUES (?, ?, ?)",
                    (primary_id, form, norm),
                )
            if not primary.public_context and secondary.public_context:
                c.execute(
                    "UPDATE entities SET public_context = ? WHERE id = ?",
                    (secondary.public_context, primary_id),
                )
            c.execute("DELETE FROM entities WHERE id = ?", (secondary_id,))
        self._log(
            matter_id,
            "entity.merge",
            json.dumps(
                {
                    "primary": {"id": primary_id, "pseudonym": primary.pseudonym},
                    "secondary_dropped": {
                        "id": secondary_id,
                        "pseudonym": secondary.pseudonym,
                        "canonical": secondary.canonical,
                    },
                }
            ),
        )
        merged = self._fetch_entity_by_id(matter_id, primary_id)
        assert merged is not None
        return merged

    # ----- conversations -----

    def create_conversation(
        self, matter_id: str, title: str | None = None
    ) -> Conversation:
        cid = str(uuid.uuid4())
        title = title or f"Conversation {datetime.now(timezone.utc).strftime('%b %d %H:%M')}"
        now = datetime.now(timezone.utc).isoformat()
        with self._tx() as c:
            c.execute(
                "INSERT INTO conversations (id, matter_id, title, created_at) "
                "VALUES (?, ?, ?, ?)",
                (cid, matter_id, title, now),
            )
        self._log(matter_id, "conversation.create", json.dumps({"id": cid, "title": title}))
        return Conversation(
            id=cid,
            matter_id=matter_id,
            title=title,
            created_at=datetime.fromisoformat(now),
        )

    def list_conversations(self, matter_id: str) -> list[Conversation]:
        rows = self._conn.execute(
            "SELECT * FROM conversations WHERE matter_id = ? ORDER BY created_at DESC",
            (matter_id,),
        ).fetchall()
        return [
            Conversation(
                id=r["id"],
                matter_id=r["matter_id"],
                title=r["title"],
                created_at=datetime.fromisoformat(r["created_at"]),
            )
            for r in rows
        ]

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        row = self._conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if row is None:
            return None
        return Conversation(
            id=row["id"],
            matter_id=row["matter_id"],
            title=row["title"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def rename_conversation(self, conversation_id: str, title: str) -> None:
        with self._tx() as c:
            c.execute(
                "UPDATE conversations SET title = ? WHERE id = ?",
                (title, conversation_id),
            )

    def delete_conversation(self, conversation_id: str) -> None:
        with self._tx() as c:
            c.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))

    def add_message(
        self,
        conversation_id: str,
        role: MessageRole,
        redacted_text: str,
        display_text: str,
    ) -> Message:
        now = datetime.now(timezone.utc).isoformat()
        with self._tx() as c:
            cur = c.execute(
                "INSERT INTO messages (conversation_id, role, redacted_text, "
                "display_text, created_at) VALUES (?, ?, ?, ?, ?)",
                (conversation_id, role.value, redacted_text, display_text, now),
            )
            mid = int(cur.lastrowid)
        return Message(
            id=mid,
            conversation_id=conversation_id,
            role=role,
            redacted_text=redacted_text,
            display_text=display_text,
            created_at=datetime.fromisoformat(now),
        )

    def export_matter_json(self, matter_id: str) -> dict:
        """Serialise the entire matter — its row, entities (with surface
        forms), conversations and messages — to a plain dict suitable for
        JSON encoding. Used for backup, archival, and (eventually)
        cross-machine portability via a future import path."""

        matter = self.get_matter(matter_id)
        if matter is None:
            raise ValueError(f"Unknown matter: {matter_id}")

        entities = self.list_entities(matter_id)
        conversations = self.list_conversations(matter_id)

        return {
            "version": 1,
            "matter": {
                "id": matter.id,
                "name": matter.name,
                "mode": matter.mode.value,
                "llm_endpoint": matter.llm_endpoint,
                "llm_model": matter.llm_model,
                "zero_retention_attested": matter.zero_retention_attested,
                "notes": matter.notes,
                "created_at": (
                    matter.created_at.isoformat() if matter.created_at else None
                ),
            },
            "entities": [
                {
                    "id": e.id,
                    "canonical": e.canonical,
                    "entity_type": e.entity_type.value,
                    "pseudonym": e.pseudonym,
                    "public_context": e.public_context,
                    "user_marked": e.user_marked,
                    "surface_forms": sorted(e.surface_forms),
                    "created_at": (
                        e.created_at.isoformat() if e.created_at else None
                    ),
                }
                for e in entities
            ],
            "conversations": [
                {
                    "id": c.id,
                    "title": c.title,
                    "created_at": (
                        c.created_at.isoformat() if c.created_at else None
                    ),
                    "messages": [
                        {
                            "id": m.id,
                            "role": m.role.value,
                            "redacted_text": m.redacted_text,
                            "display_text": m.display_text,
                            "created_at": (
                                m.created_at.isoformat() if m.created_at else None
                            ),
                        }
                        for m in self.list_messages(c.id)
                    ],
                }
                for c in conversations
            ],
        }

    def export_conversation_markdown(self, conversation_id: str) -> str:
        """Render a conversation as a markdown transcript using the rehydrated
        display text — what the lawyer reads, not what the LLM saw."""

        conv = self.get_conversation(conversation_id)
        if conv is None:
            raise ValueError(f"Unknown conversation: {conversation_id}")
        lines = [
            f"# {conv.title}",
            "",
            f"_Conversation `{conv.id}`, started "
            f"{conv.created_at.isoformat() if conv.created_at else 'unknown'}._",
            "",
        ]
        for m in self.list_messages(conversation_id):
            speaker = "You" if m.role == MessageRole.USER else "Assistant"
            stamp = m.created_at.isoformat() if m.created_at else ""
            lines.append(f"## {speaker} · {stamp}")
            lines.append("")
            lines.append(m.display_text)
            lines.append("")
        return "\n".join(lines)

    def list_messages(self, conversation_id: str) -> list[Message]:
        rows = self._conn.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id ASC",
            (conversation_id,),
        ).fetchall()
        return [
            Message(
                id=r["id"],
                conversation_id=r["conversation_id"],
                role=MessageRole(r["role"]),
                redacted_text=r["redacted_text"],
                display_text=r["display_text"],
                created_at=datetime.fromisoformat(r["created_at"]),
            )
            for r in rows
        ]

    # ----- approvals (the ledger) -----

    def record_approval(
        self,
        *,
        review_id: str,
        matter_id: str,
        payload_sha256: str,
        chars: int,
        endpoint: str,
        endpoint_host: str,
        mode: str,
        zero_retention: bool,
        n_hidden: int,
        n_kept: int,
        n_user_marked: int,
        attestation: str,
        approver_os_user: str,
        ui_lang: str | None,
        delete_entity_ids: Iterable[int] = (),
        purpose: str = "mcp_document",
        model: str | None = None,
        confirm_entity_ids: Iterable[int] = (),
    ) -> int:
        """Write the approval row, confirm the provisional entities the
        review used (``provisional_review_id`` back to NULL, one
        ``entity.confirm`` audit line each), delete the entities the user
        chose to keep visible (and that this review alone created) and log
        the ``mcp.approve`` row — all in ONE transaction. Either every
        effect lands or none does: a text must never be releasable without
        its record, and the record must never exist without the deletions
        and confirmations it describes."""

        now = datetime.now(timezone.utc).isoformat()
        ids = list(delete_entity_ids)
        confirm = [i for i in confirm_entity_ids if i not in ids]
        with self._tx(immediate=True) as c:
            cur = c.execute(
                "INSERT INTO approvals (review_id, matter_id, purpose, payload_sha256, chars, "
                "endpoint, endpoint_host, model, mode, zero_retention, n_hidden, n_kept, "
                "n_user_marked, attestation, approver_os_user, ui_lang, verified_at_send, "
                "approved_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)",
                (
                    review_id, matter_id, purpose, payload_sha256, chars,
                    endpoint, endpoint_host, model, mode, int(zero_retention),
                    n_hidden, n_kept, n_user_marked, attestation, approver_os_user,
                    ui_lang, now,
                ),
            )
            approval_id = int(cur.lastrowid)
            if confirm:
                marks = ",".join("?" for _ in confirm)
                provisional = c.execute(
                    f"SELECT id, canonical, pseudonym FROM entities WHERE id IN ({marks}) "
                    "AND provisional_review_id IS NOT NULL ORDER BY id",
                    confirm,
                ).fetchall()
                c.execute(
                    f"UPDATE entities SET provisional_review_id = NULL WHERE id IN ({marks})",
                    confirm,
                )
                for row in provisional:
                    self._log(
                        matter_id,
                        "entity.confirm",
                        json.dumps(
                            {
                                "canonical": row["canonical"],
                                "pseudonym": row["pseudonym"],
                                "review_id": review_id,
                            }
                        ),
                    )
            for entity_id in ids:
                c.execute("DELETE FROM entities WHERE id = ?", (entity_id,))
            # _log() runs inside the open transaction (no BEGIN of its own),
            # so a failure here rolls the row and the deletions back too.
            self._log(
                matter_id,
                "mcp.approve",
                json.dumps(
                    {
                        "approval_id": approval_id,
                        "review_id": review_id,
                        "sha256": payload_sha256,
                        "chars": chars,
                        "n_hidden": n_hidden,
                        "n_kept": n_kept,
                        "pruned_entity_ids": ids,
                        "confirmed_entity_ids": confirm,
                    }
                ),
            )
        return approval_id

    def get_approval(self, approval_id: int) -> Approval | None:
        row = self._conn.execute(
            "SELECT * FROM approvals WHERE id = ?", (approval_id,)
        ).fetchone()
        if row is None:
            return None
        return Approval(
            id=row["id"],
            review_id=row["review_id"],
            matter_id=row["matter_id"],
            purpose=row["purpose"],
            payload_sha256=row["payload_sha256"],
            chars=row["chars"],
            endpoint=row["endpoint"],
            endpoint_host=row["endpoint_host"],
            mode=row["mode"],
            zero_retention=bool(row["zero_retention"]),
            n_hidden=row["n_hidden"],
            n_kept=row["n_kept"],
            n_user_marked=row["n_user_marked"],
            attestation=row["attestation"],
            approver_os_user=row["approver_os_user"],
            ui_lang=row["ui_lang"],
            verified_at_send=row["verified_at_send"],
            approved_at=datetime.fromisoformat(row["approved_at"]),
            released_at=(
                datetime.fromisoformat(row["released_at"]) if row["released_at"] else None
            ),
            outcome=row["outcome"],
        )

    def set_approval_verified(
        self,
        approval_id: int,
        verified: bool,
        *,
        audit: tuple[str, str, str] | None = None,
    ) -> None:
        """Record the release-time check: 1 when the text re-hashed to the
        recorded digest and was handed to the local pipe (``outcome`` =
        released); 0 when it did not and was refused (``outcome`` =
        refused). ``released_at`` means handed to the pipe, not received
        by the model. ``audit`` — ``(matter_id, action, detail)`` — is
        written in the SAME transaction, so the ledger never says released
        without its ``mcp.release`` line (or the reverse)."""

        released_at = datetime.now(timezone.utc).isoformat() if verified else None
        outcome = "released" if verified else "refused"
        with self._tx(immediate=True) as c:
            c.execute(
                "UPDATE approvals SET verified_at_send = ?, released_at = ?, outcome = ? "
                "WHERE id = ?",
                (int(verified), released_at, outcome, approval_id),
            )
            if audit is not None:
                self._log(*audit)

    def close_approval(
        self,
        approval_id: int,
        outcome: Literal["withdrawn", "expired", "lost_on_restart"],
    ) -> None:
        """An approval that will never be released: the lawyer withdrew it,
        the model never collected it, or the server restarted."""

        with self._tx() as c:
            c.execute(
                "UPDATE approvals SET outcome = ? WHERE id = ? AND outcome IS NULL",
                (outcome, approval_id),
            )

    def recover_after_restart(self) -> dict[str, int]:
        """Sweep what an abrupt stop left behind: delete every entity still
        marked provisional (its review died with the process) and close
        every approval that was neither released nor refused as
        ``lost_on_restart``. One ``mcp.recover`` audit line per matter
        touched. Safe because the server's instance lock guarantees no
        other server holds a live review on this home."""

        per_matter: dict[str, dict[str, int]] = {}
        with self._tx(immediate=True) as c:
            for row in c.execute(
                "SELECT matter_id, COUNT(*) AS n FROM entities "
                "WHERE provisional_review_id IS NOT NULL GROUP BY matter_id"
            ).fetchall():
                per_matter.setdefault(row["matter_id"], {"pruned": 0, "approvals_lost": 0})
                per_matter[row["matter_id"]]["pruned"] = int(row["n"])
            c.execute("DELETE FROM entities WHERE provisional_review_id IS NOT NULL")
            for row in c.execute(
                "SELECT matter_id, COUNT(*) AS n FROM approvals "
                "WHERE outcome IS NULL AND verified_at_send IS NULL GROUP BY matter_id"
            ).fetchall():
                per_matter.setdefault(row["matter_id"], {"pruned": 0, "approvals_lost": 0})
                per_matter[row["matter_id"]]["approvals_lost"] = int(row["n"])
            c.execute(
                "UPDATE approvals SET outcome = 'lost_on_restart' "
                "WHERE outcome IS NULL AND verified_at_send IS NULL"
            )
            for matter_id, counts in per_matter.items():
                self._log(matter_id, "mcp.recover", json.dumps(counts))
        return {
            "pruned": sum(v["pruned"] for v in per_matter.values()),
            "approvals_lost": sum(v["approvals_lost"] for v in per_matter.values()),
            "matters": len(per_matter),
        }

    def last_used_by_matter(self) -> dict[str, str]:
        """Latest audit timestamp per matter — the 'last used' order the
        plugin window sorts matters by."""

        rows = self._conn.execute(
            "SELECT matter_id, MAX(ts) AS ts FROM audit_log GROUP BY matter_id"
        ).fetchall()
        return {r["matter_id"]: r["ts"] for r in rows}

    def _fetch_entity_by_id(self, matter_id: str, entity_id: int) -> Entity | None:
        row = self._conn.execute(
            "SELECT * FROM entities WHERE matter_id = ? AND id = ?",
            (matter_id, entity_id),
        ).fetchone()
        return self._row_to_entity(row) if row else None

    def list_entities(self, matter_id: str, *, review_id: str | None = None) -> list[Entity]:
        """The confirmed entities of a matter, plus the provisional ones of
        ``review_id`` when given (the plugin review that created them)."""

        rows = self._conn.execute(
            f"SELECT e.* FROM entities e WHERE e.matter_id = ? AND {self._VISIBLE} "
            "ORDER BY e.id ASC",
            (matter_id, review_id),
        ).fetchall()
        return [self._row_to_entity(r) for r in rows]

    def _row_to_entity(self, row: sqlite3.Row) -> Entity:
        forms = {
            r["form"]
            for r in self._conn.execute(
                "SELECT form FROM surface_forms WHERE entity_id = ?", (row["id"],)
            ).fetchall()
        }
        return Entity(
            id=row["id"],
            matter_id=row["matter_id"],
            canonical=row["canonical"],
            entity_type=EntityType(row["entity_type"]),
            pseudonym=row["pseudonym"],
            public_context=row["public_context"],
            user_marked=bool(row["user_marked"]),
            surface_forms=forms,
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    # ----- pseudonym allocation -----

    @staticmethod
    def _allocate_pseudonym(
        c: sqlite3.Connection, matter_id: str, entity_type: EntityType
    ) -> str:
        """Allocate the next pseudonym for `entity_type` in `matter_id`,
        inside the caller's (IMMEDIATE) transaction.

        One statement reads and advances the counter (``RETURNING`` gives
        the value after the update), so no interleaving can hand the same
        number to two callers. Counters are monotonic per (matter, type)
        and never decremented, so a deleted or merged-away pseudonym is
        never reused. This preserves the integrity of any document that
        was redacted before the change.
        """

        prefix = _pseudonym_prefix(entity_type)
        row = c.execute(
            "INSERT INTO pseudonym_counters (matter_id, entity_type, next_n) "
            "VALUES (?, ?, 2) "
            "ON CONFLICT(matter_id, entity_type) DO UPDATE SET next_n = next_n + 1 "
            "RETURNING next_n",
            (matter_id, entity_type.value),
        ).fetchone()
        n = int(row[0]) - 1
        return f"{prefix}{n}"

    # ----- audit -----

    def _log(self, matter_id: str, action: str, detail: str | None = None) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO audit_log (matter_id, action, detail, ts) VALUES (?, ?, ?, ?)",
            (matter_id, action, detail, ts),
        )


def _is_token_subsequence(needle: list[str], haystack: list[str]) -> bool:
    """True iff `needle` appears as a contiguous run of tokens in `haystack`."""

    if not needle or not haystack:
        return False
    n = len(needle)
    for i in range(len(haystack) - n + 1):
        if haystack[i : i + n] == needle:
            return True
    return False


def _pseudonym_prefix(t: EntityType) -> str:
    return {
        EntityType.PERSON: "Person",
        EntityType.ORG: "Org",
        EntityType.LOC: "Loc",
        EntityType.EMAIL: "Email",
        EntityType.PHONE: "Phone",
        EntityType.IBAN: "Iban",
        EntityType.CASE_REF: "Case",
        EntityType.URL: "Url",
        EntityType.SECRET: "Secret",
        EntityType.OTHER: "X",
    }[t]
