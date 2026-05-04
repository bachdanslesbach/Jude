from __future__ import annotations

import re

from ..store import Store
from ..types import Detection, DetectionSource


class DictionaryDetector:
    """Find every occurrence of a known surface form from the per-matter store.

    This is what makes the tool *learn*: every time the user accepts (or
    corrects) a detection, the form is added to the store; future runs will
    catch it deterministically with high priority.
    """

    def __init__(self, store: Store, matter_id: str):
        self.store = store
        self.matter_id = matter_id

    def detect(self, text: str) -> list[Detection]:
        forms = self._all_forms()
        if not forms:
            return []
        forms.sort(key=len, reverse=True)
        out: list[Detection] = []
        seen_spans: set[tuple[int, int]] = set()
        for form, entity_type in forms:
            pattern = re.compile(rf"(?<!\w){re.escape(form)}(?!\w)", re.IGNORECASE)
            for m in pattern.finditer(text):
                span = (m.start(), m.end())
                if any(_overlaps(span, s) for s in seen_spans):
                    continue
                seen_spans.add(span)
                out.append(
                    Detection(
                        text=m.group(0),
                        start=m.start(),
                        end=m.end(),
                        entity_type=entity_type,
                        source=DetectionSource.DICTIONARY,
                        confidence=0.99,
                    )
                )
        return out

    def _all_forms(self) -> list[tuple[str, "EntityType"]]:  # noqa: F821
        from ..types import EntityType  # local to avoid cycle in some setups

        rows = self.store._conn.execute(  # noqa: SLF001
            """
            SELECT s.form, e.entity_type
            FROM surface_forms s
            JOIN entities e ON e.id = s.entity_id
            WHERE e.matter_id = ?
            """,
            (self.matter_id,),
        ).fetchall()
        return [(r["form"], EntityType(r["entity_type"])) for r in rows]


def _overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return not (a[1] <= b[0] or b[1] <= a[0])
