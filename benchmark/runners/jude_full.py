"""The full Jude detection + redaction pipeline.

Every detector (regex + patterns + known entities + spaCy + GLiNER +
dictionary, language-routed, two-pass) plus the public-knowledge
whitelist that drops public institutions and treaties from the
redaction set. This is the system Jude actually ships; the benchmark
scores it against gold to see how close to production-quality
redaction we are.

`gliner_model` / `use_gliner` exist for the model-size ladder: the same
pipeline with GLiNER small, medium, large, or none.
"""

from __future__ import annotations

from ..schema import PredSpan


class JudeFullRunner:
    def __init__(
        self,
        name: str = "jude-full",
        gliner_model: str | None = None,
        use_gliner: bool | None = None,
    ):
        self.name = name
        self.gliner_model = gliner_model
        self.use_gliner = use_gliner

    def predict(self, text: str) -> list[PredSpan]:
        from jude.detect import DetectionPipeline
        from jude.redact import redact_two_pass
        from jude.store import Store
        from jude.types import Mode

        # Fresh in-memory store per document so the dictionary state is
        # not contaminated across documents. Inside one document, the
        # two-pass redact does its own first-pass-populates-dict trick.
        store = Store(":memory:")
        try:
            matter = store.create_matter("benchmark", mode=Mode.STRICT)
            pipeline = DetectionPipeline(
                store=store,
                matter_id=matter.id,
                use_gliner=self.use_gliner,
                gliner_model=self.gliner_model,
            )
            result = redact_two_pass(text, pipeline, store, matter.id, Mode.STRICT)
            return [
                PredSpan(
                    start=d.start,
                    end=d.end,
                    type=d.entity_type.value,
                    text=d.text,
                )
                for d in result.detections
            ]
        finally:
            store.close()

    def extra_meta(self) -> dict:
        return {
            "gliner_model": self.gliner_model or ("urchade/gliner_large-v2.1" if self.use_gliner is not False else None),
            "use_gliner": self.use_gliner,
        }
