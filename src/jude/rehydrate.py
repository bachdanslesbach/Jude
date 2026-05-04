from __future__ import annotations

import re

from .store import Store


def rehydrate(text: str, store: Store, matter_id: str) -> str:
    """Replace every pseudonym in *text* with the canonical real name.

    Pseudonyms are matched with word boundaries so partial-prefix collisions
    (e.g. `Org_001` is not matched inside `Org_0011`) are avoided. Longer
    pseudonyms are processed first to be safe.
    """

    entities = store.list_entities(matter_id)
    entities.sort(key=lambda e: -len(e.pseudonym))

    result = text
    for ent in entities:
        pattern = re.compile(rf"(?<!\w){re.escape(ent.pseudonym)}(?!\w)")
        result = pattern.sub(ent.canonical, result)
    return result
