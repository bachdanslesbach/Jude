"""Ablation: full Jude pipeline WITHOUT the public-knowledge whitelist.

Quantifies how much the whitelist contributes to precision (it should
boost precision by removing false positives like 'European Commission'
and 'Digital Markets Act' from the redaction set).
"""

from __future__ import annotations

from ..schema import PredSpan


class JudeNoFilterRunner:
    name = "jude-no-public-filter"

    def predict(self, text: str) -> list[PredSpan]:
        from jude.detect import DetectionPipeline, resolve_overlaps
        from jude.store import Store
        from jude.types import Mode

        store = Store(":memory:")
        try:
            matter = store.create_matter("benchmark", mode=Mode.STRICT)
            pipeline = DetectionPipeline(store=store, matter_id=matter.id)

            # Two passes (manual, since we want to bypass the public-knowledge
            # filter inside redact()):
            first = pipeline.detect(text)
            for d in first:
                if not store.find_entity_by_surface_or_alias(
                    matter.id, d.text, d.entity_type
                ):
                    store.create_entity(
                        matter.id, d.text, d.entity_type,
                    )
            second = pipeline.detect(text)
            merged = resolve_overlaps(list(first) + list(second))
            return [
                PredSpan(
                    start=d.start, end=d.end,
                    type=d.entity_type.value, text=d.text,
                )
                for d in merged
            ]
        finally:
            store.close()
