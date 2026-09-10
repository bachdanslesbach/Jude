"""GLiNER must load from the local cache when there is no network.

Reproduces a failure seen on this machine during a connectivity blip:
`jude review` died with a ConnectError because `from_pretrained`
consulted the Hub before touching the cached files.
"""

from __future__ import annotations

import pytest


def test_gliner_loads_with_hub_offline(monkeypatch):
    pytest.importorskip("gliner")
    from huggingface_hub import try_to_load_from_cache

    if not try_to_load_from_cache("urchade/gliner_large-v2.1", "gliner_config.json"):
        pytest.skip("gliner_large-v2.1 not in the local cache")

    from jude.detect import gliner_detector

    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    gliner_detector._load.cache_clear()
    try:
        det = gliner_detector.GlinerDetector()
        assert det.model is not None
    finally:
        gliner_detector._load.cache_clear()
