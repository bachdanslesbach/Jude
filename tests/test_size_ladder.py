"""Plumbing for the model-size / throughput ladder.

The efficiency analysis needs the same pipeline with GLiNER small,
medium and large, and the corpus split into the tuned-on `dev` set and
the never-tuned-on `heldout` set. Nothing here loads a model.
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmark.schema import GoldDocument
from jude.store import Store
from jude.types import Mode


class _FakeGliner:
    def predict_entities(self, text, labels, threshold=0.5):  # noqa: ANN001
        return []


class TestPipelineGlinerModel:
    def test_pipeline_passes_the_model_name_to_the_detector(self, monkeypatch):
        import jude.detect.gliner_detector as gd
        from jude.detect import DetectionPipeline

        seen: list[str] = []

        def fake_load(name: str):
            seen.append(name)
            return _FakeGliner()

        monkeypatch.setattr(gd, "_load", fake_load)
        store = Store(":memory:")
        try:
            matter = store.create_matter("t", mode=Mode.STRICT)
            DetectionPipeline(store=store, matter_id=matter.id, use_gliner=True,
                              gliner_model="urchade/gliner_small-v2.1")
        finally:
            store.close()
        assert seen == ["urchade/gliner_small-v2.1"]

    def test_default_model_is_large(self, monkeypatch):
        import jude.detect.gliner_detector as gd
        from jude.detect import DetectionPipeline

        seen: list[str] = []
        monkeypatch.setattr(gd, "_load", lambda name: (seen.append(name), _FakeGliner())[1])
        store = Store(":memory:")
        try:
            matter = store.create_matter("t", mode=Mode.STRICT)
            DetectionPipeline(store=store, matter_id=matter.id, use_gliner=True)
        finally:
            store.close()
        assert seen == ["urchade/gliner_large-v2.1"]


class TestSplit:
    def test_gold_document_reads_split_default_dev(self, tmp_path: Path):
        base = {"id": "doc_001_x_en", "title": "t", "language": "en", "text": "Acme SA.",
                "gold_spans": [{"start": 0, "end": 7, "type": "ORG", "text": "Acme SA"}]}
        p = tmp_path / "a.json"
        p.write_text(json.dumps(base), encoding="utf-8")
        assert GoldDocument.from_json(p).split == "dev"
        base["split"] = "heldout"
        p.write_text(json.dumps(base), encoding="utf-8")
        assert GoldDocument.from_json(p).split == "heldout"

    def test_load_corpus_filters_by_split(self, tmp_path: Path, monkeypatch):
        import benchmark.run as run

        for i, split in enumerate(["dev", "heldout", "heldout"]):
            d = {"id": f"doc_00{i}_x_en", "title": "t", "language": "en", "text": "Acme SA.",
                 "gold_spans": [], "split": split}
            (tmp_path / f"doc_00{i}_x_en.json").write_text(json.dumps(d), encoding="utf-8")
        monkeypatch.setattr(run, "CORPUS_DIR", tmp_path)
        assert len(run._load_corpus()) == 3
        assert [d.id for d in run._load_corpus(split="heldout")] == ["doc_001_x_en", "doc_002_x_en"]
        assert [d.id for d in run._load_corpus(split="dev")] == ["doc_000_x_en"]
