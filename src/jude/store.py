from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .types import Entity, EntityType, Matter, Mode, normalize_surface

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
"""


class Store:
    """SQLite-backed store for matters, entities, and surface-form aliases.

    All data is per-matter and stays on the user's disk. The database file
    itself contains real names — treat it as confidential.
    """

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, isolation_level=None)
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
        prefix = _pseudonym_prefix(entity_type)
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM entities "
            "WHERE matter_id = ? AND entity_type = ?",
            (matter_id, entity_type.value),
        ).fetchone()
        n = int(row["n"]) + 1
        return f"{prefix}_{n:03d}"

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
        EntityType.OTHER: "X",
    }[t]
