"""Which language components are missing, by stable id.

Shared by ``reviews.check_models`` (fail closed before a document is
prepared) and by the doctor (say what to install). The ids are the keys
of the ``ui.missing.*`` strings: ``spacy_en``, ``spacy_fr``, ``spacy_nl``,
``gliner_package`` and ``gliner``.

Nothing here downloads anything: a component is present when it is
installed or in the local Hugging Face cache, and missing otherwise.
"""

from __future__ import annotations

from collections.abc import Iterable


def spacy_model_missing(lang: str) -> bool:
    from ..detect.spacy_detector import _resolve_model_for_language

    return _resolve_model_for_language(lang, {}) is None


def gliner_package_missing() -> bool:
    try:
        import gliner  # noqa: F401
    except ImportError:
        return True
    return False


def gliner_cached(model: str) -> bool:
    """True when the checkpoint's config is in the local Hub cache, i.e. the
    weights can be loaded with the offline flags set."""

    try:
        from huggingface_hub import try_to_load_from_cache
    except ImportError:
        return False
    try:
        hit = try_to_load_from_cache(model, "gliner_config.json")
        if not isinstance(hit, str):
            hit = try_to_load_from_cache(model, "config.json")
        return isinstance(hit, str)
    except Exception:
        return False


def missing_components(langs: Iterable[str], gliner_model: str) -> tuple[str, ...]:
    """One id per missing component, in a stable order: the spaCy languages
    first (in the order given), then ``gliner_package`` or ``gliner``."""

    missing: list[str] = []
    for lang in langs:
        if spacy_model_missing(lang):
            missing.append(f"spacy_{lang}")
    if gliner_package_missing():
        missing.append("gliner_package")
    elif not gliner_cached(gliner_model):
        missing.append("gliner")
    return tuple(missing)
