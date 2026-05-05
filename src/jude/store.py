from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .types import (
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

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        self._conn.execute("BEGIN")
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
    ) -> Matter:
        mid = matter_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self._tx() as c:
            c.execute(
                "INSERT INTO matters (id, name, mode, llm_endpoint, "
                "zero_retention_attested, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (mid, name, mode.value, llm_endpoint, int(zero_retention_attested), now),
            )
        self._log(mid, "matter.create", json.dumps({"name": name, "mode": mode.value}))
        return Matter(
            id=mid,
            name=name,
            mode=mode,
            llm_endpoint=llm_endpoint,
            zero_retention_attested=zero_retention_attested,
            created_at=datetime.fromisoformat(now),
        )

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
        return Matter(
            id=row["id"],
            name=row["name"],
            mode=Mode(row["mode"]),
            llm_endpoint=row["llm_endpoint"],
            zero_retention_attested=bool(row["zero_retention_attested"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    # ----- entities -----

    def find_entity_by_surface(self, matter_id: str, surface: str) -> Entity | None:
        norm = normalize_surface(surface)
        if not norm:
            return None
        row = self._conn.execute(
            """
            SELECT e.* FROM entities e
            JOIN surface_forms s ON s.entity_id = e.id
            WHERE e.matter_id = ? AND s.normalized = ?
            LIMIT 1
            """,
            (matter_id, norm),
        ).fetchone()
        return self._row_to_entity(row) if row else None

    def find_entity_by_pseudonym(self, matter_id: str, pseudonym: str) -> Entity | None:
        row = self._conn.execute(
            "SELECT * FROM entities WHERE matter_id = ? AND pseudonym = ?",
            (matter_id, pseudonym),
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
    ) -> Entity:
        forms = set(surface_forms or set())
        forms.add(canonical)
        pseudonym = self._next_pseudonym(matter_id, entity_type)
        now = datetime.now(timezone.utc).isoformat()
        with self._tx() as c:
            cur = c.execute(
                "INSERT INTO entities (matter_id, canonical, entity_type, pseudonym, "
                "public_context, user_marked, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    matter_id,
                    canonical,
                    entity_type.value,
                    pseudonym,
                    public_context,
                    int(user_marked),
                    now,
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

    def add_surface_form(self, entity_id: int, form: str) -> None:
        norm = normalize_surface(form)
        if not norm:
            return
        with self._tx() as c:
            c.execute(
                "INSERT OR IGNORE INTO surface_forms (entity_id, form, normalized) "
                "VALUES (?, ?, ?)",
                (entity_id, form, norm),
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

    def _fetch_entity_by_id(self, matter_id: str, entity_id: int) -> Entity | None:
        row = self._conn.execute(
            "SELECT * FROM entities WHERE matter_id = ? AND id = ?",
            (matter_id, entity_id),
        ).fetchone()
        return self._row_to_entity(row) if row else None

    def list_entities(self, matter_id: str) -> list[Entity]:
        rows = self._conn.execute(
            "SELECT * FROM entities WHERE matter_id = ? ORDER BY id ASC",
            (matter_id,),
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

    def _next_pseudonym(self, matter_id: str, entity_type: EntityType) -> str:
        """Allocate the next pseudonym for `entity_type` in `matter_id`.

        Counters are monotonic per (matter, type) and never decremented, so a
        deleted or merged-away pseudonym is never reused. This preserves the
        integrity of any document that was redacted before the change.
        """

        prefix = _pseudonym_prefix(entity_type)
        row = self._conn.execute(
            "SELECT next_n FROM pseudonym_counters "
            "WHERE matter_id = ? AND entity_type = ?",
            (matter_id, entity_type.value),
        ).fetchone()
        n = int(row["next_n"]) if row else 1
        self._conn.execute(
            "INSERT INTO pseudonym_counters (matter_id, entity_type, next_n) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(matter_id, entity_type) DO UPDATE SET next_n = ?",
            (matter_id, entity_type.value, n + 1, n + 1),
        )
        return f"{prefix}{n}"

    # ----- audit -----

    def _log(self, matter_id: str, action: str, detail: str | None = None) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO audit_log (matter_id, action, detail, ts) VALUES (?, ?, ?, ?)",
            (matter_id, action, detail, ts),
        )


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
