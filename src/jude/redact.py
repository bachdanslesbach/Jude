from __future__ import annotations

from .context import ContextProvider, default_provider
from .store import Store
from .types import (
    Detection,
    Entity,
    EntityType,
    Mode,
    RedactionResult,
)


def redact(
    text: str,
    detections: list[Detection],
    store: Store,
    matter_id: str,
    mode: Mode = Mode.STRICT,
    context_provider: ContextProvider | None = None,
) -> RedactionResult:
    """Apply detections to text, producing pseudonymized output.

    Each detection is resolved to an existing or new Entity in the per-matter
    store. The same canonical entity always gets the same pseudonym.

    In SMART mode, the *first* occurrence of an entity in the output text gets
    its public_context appended in parentheses; subsequent occurrences use the
    bare pseudonym. This keeps the output readable for the LLM while limiting
    the duplication of context tags.
    """

    matter = store.get_matter(matter_id)
    if matter is None:
        raise ValueError(f"Unknown matter: {matter_id}")
    if mode == Mode.SMART and not matter.zero_retention_attested:
        raise ValueError(
            "Smart mode requires the matter to attest a zero-retention LLM endpoint."
        )

    provider = context_provider or default_provider() if mode == Mode.SMART else None
    sorted_dets = sorted(detections, key=lambda d: d.start)
    used_entities: dict[int, Entity] = {}
    seen_in_output: set[int] = set()

    out_parts: list[str] = []
    cursor = 0

    for det in sorted_dets:
        if det.start < cursor:
            continue

        entity = _get_or_create_entity(store, matter_id, det)
        assert entity.id is not None

        if provider is not None and not entity.public_context:
            ctx = provider.lookup(entity.canonical, entity.entity_type)
            if ctx:
                store.set_public_context(entity.id, ctx)
                entity.public_context = ctx

        used_entities[entity.id] = entity

        if det.text not in entity.surface_forms:
            store.add_surface_form(entity.id, det.text)
            entity.surface_forms.add(det.text)

        replacement = _format_replacement(entity, mode, seen_in_output)
        seen_in_output.add(entity.id)

        out_parts.append(text[cursor : det.start])
        out_parts.append(replacement)
        cursor = det.end

    out_parts.append(text[cursor:])

    return RedactionResult(
        redacted_text="".join(out_parts),
        detections=sorted_dets,
        entities_used=list(used_entities.values()),
        mode=mode,
    )


def _get_or_create_entity(
    store: Store, matter_id: str, det: Detection
) -> Entity:
    # Exact + alias lookup. The aliasing layer turns the "Marie-Claire
    # Lefèvre" / "Marie-Claire" duplicate-entity problem from a manual
    # merge into a no-op the first time both forms are seen in the same
    # matter.
    existing = store.find_entity_by_surface_or_alias(
        matter_id, det.text, det.entity_type
    )
    if existing is not None:
        return existing
    return store.create_entity(
        matter_id=matter_id,
        canonical=det.text,
        entity_type=det.entity_type,
    )


def _format_replacement(
    entity: Entity, mode: Mode, already_seen: set[int]
) -> str:
    if mode == Mode.SMART and entity.public_context and entity.id not in already_seen:
        return f"{entity.pseudonym} ({entity.public_context})"
    return entity.pseudonym


def redact_two_pass(
    text: str,
    pipeline,  # type: ignore[no-untyped-def]
    store: Store,
    matter_id: str,
    mode: Mode = Mode.STRICT,
    context_provider: ContextProvider | None = None,
) -> RedactionResult:
    """Detect → redact → detect again → re-redact if the second pass found
    spans the first didn't.

    The motivating case: spaCy catches "Acme Corp" in the document body
    (where context disambiguates it as an ORG) but misses it in a header
    or title (where the surrounding tokens confuse the parser). The first
    `redact()` call persists the body match into the per-matter dictionary,
    which the next call to `pipeline.detect()` then uses to find every
    other occurrence of the same surface form — including the title.

    The second redaction is run against the ORIGINAL text (not the already-
    redacted text), with the union of first-pass and newly-discovered
    spans, so offsets stay coherent.
    """

    first = pipeline.detect(text)
    first_result = redact(text, first, store, matter_id, mode, context_provider)

    second = pipeline.detect(text)
    new_spans = [d for d in second if not _overlaps_any(d, first)]
    if not new_spans:
        return first_result

    merged = sorted(first + new_spans, key=lambda d: d.start)
    return redact(text, merged, store, matter_id, mode, context_provider)


def _overlaps_any(d: Detection, others: list[Detection]) -> bool:
    return any(not (d.end <= o.start or o.end <= d.start) for o in others)


def force_redact_span(
    text: str,
    start: int,
    end: int,
    entity_type: EntityType,
    store: Store,
    matter_id: str,
) -> Entity:
    """Manually redact a span the user marked in the UI."""

    surface = text[start:end]
    existing = store.find_entity_by_surface(matter_id, surface)
    if existing:
        return existing
    return store.create_entity(
        matter_id=matter_id,
        canonical=surface,
        entity_type=entity_type,
        user_marked=True,
    )
