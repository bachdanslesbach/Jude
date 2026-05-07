from __future__ import annotations

import re

from ..store import Store
from ..types import Detection, DetectionSource

# Legal/corporate suffixes that should also match in their stripped form.
# When 'Lumen Reality SARL' is in the dictionary, an occurrence of just
# 'Lumen Reality' (with no SARL) refers to the same entity and must be
# caught — otherwise the document's first body mention escapes redaction.
_SUFFIX_RE = re.compile(
    r"\s+(?:Inc\.?|LLC|Ltd\.?|Limited|S\.?A\.?|SARL|SAS|SE|"
    r"GmbH|AG|N\.?V\.?|B\.?V\.?|PLC|Co\.?|Corp\.?|"
    r"Corporation|Company|SPRL|SCRL|ASBL|BVBA|"
    r"plc|s\.?p\.?a\.?|kg|ohg|oy|ab|aktiebolag|asa)\b\.?",
    re.IGNORECASE,
)


def _strip_legal_suffix(form: str) -> str:
    return _SUFFIX_RE.sub("", form).strip(" .,").strip()


class DictionaryDetector:
    """Find every occurrence of a known surface form from the per-matter store.

    This is what makes the tool *learn*: every time the user accepts (or
    corrects) a detection, the form is added to the store; future runs will
    catch it deterministically with high priority.

    Surface forms with a corporate suffix ("Lumen Reality SARL") also
    match in their stripped form ("Lumen Reality"). Without this, the
    document's first body mention by short name escapes redaction even
    though the matter dictionary has the full name.
    """

    def __init__(self, store: Store, matter_id: str):
        self.store = store
        self.matter_id = matter_id

    def detect(self, text: str) -> list[Detection]:
        forms = self._all_forms_with_aliases()
        if not forms:
            return []
        forms.sort(key=lambda kv: len(kv[0]), reverse=True)
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

    def _all_forms_with_aliases(self) -> list[tuple[str, "EntityType"]]:  # noqa: F821
        """Returns the stored surface forms plus their suffix-stripped
        aliases for ORG entities. Single-form entities (no suffix) are
        unchanged; entities with a corporate suffix get a second
        searchable form."""

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

        forms: list[tuple[str, EntityType]] = []
        seen: set[tuple[str, str]] = set()
        for r in rows:
            form = r["form"]
            etype = EntityType(r["entity_type"])
            key = (form.lower(), etype.value)
            if key not in seen:
                seen.add(key)
                forms.append((form, etype))
            if etype == EntityType.ORG:
                stripped = _strip_legal_suffix(form)
                if stripped and stripped != form and len(stripped) >= 3:
                    sk = (stripped.lower(), etype.value)
                    if sk not in seen:
                        seen.add(sk)
                        forms.append((stripped, etype))
        return forms


def _overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return not (a[1] <= b[0] or b[1] <= a[0])
