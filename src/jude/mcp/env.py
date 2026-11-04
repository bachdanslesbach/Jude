"""The plugin's environment, in one place.

Three things live here because they used to live in four: the offline
flags the server sets for itself and the installer writes into Claude
Desktop's configuration, the variables an installing shell is allowed to
pass through to the Desktop-launched process, and the two settings
(languages, GLiNER checkpoint) the server and the doctor must read the
same way.

``normalise_env`` exists because an optional ``${user_config.hf_home}``
left empty in the bundle arrives as ``HF_HOME=""``, which
``huggingface_hub`` would treat as a path.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, MutableMapping

OFFLINE_ENV: dict[str, str] = {
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_HUB_DISABLE_TELEMETRY": "1",
    "DO_NOT_TRACK": "1",
    "PYTHONUTF8": "1",
    "TOKENIZERS_PARALLELISM": "false",
}

# Path-like variables: an empty value means "unset", never "the empty path".
EMPTY_IS_UNSET: tuple[str, ...] = (
    "JUDE_HOME",
    "HF_HOME",
    "HF_HUB_CACHE",
    "HUGGINGFACE_HUB_CACHE",
    "TRANSFORMERS_CACHE",
    "XDG_CACHE_HOME",
)

# What the installer copies from the installing shell into the Desktop entry.
PASSTHROUGH: tuple[str, ...] = (*EMPTY_IS_UNSET, "JUDE_MCP_LANGS", "JUDE_MCP_GLINER")

DEFAULT_LANGS = "en,fr,nl"
DEFAULT_GLINER = "urchade/gliner_small-v2.1"


def normalise_env(environ: MutableMapping[str, str]) -> None:
    """Set the offline flags (without overriding an explicit value) and
    delete path variables whose value is the empty string."""

    for key, value in OFFLINE_ENV.items():
        environ.setdefault(key, value)
    for key in EMPTY_IS_UNSET:
        if key in environ and environ[key] == "":
            del environ[key]


def langs(environ: Mapping[str, str] | None = None) -> tuple[str, ...]:
    """The spaCy languages the plugin requires, from ``JUDE_MCP_LANGS``."""

    env = os.environ if environ is None else environ
    raw = env.get("JUDE_MCP_LANGS") or DEFAULT_LANGS
    parsed = tuple(x.strip() for x in raw.split(",") if x.strip())
    return parsed or tuple(DEFAULT_LANGS.split(","))


def gliner_model(environ: Mapping[str, str] | None = None) -> str:
    """The GLiNER checkpoint the plugin loads from the local cache."""

    env = os.environ if environ is None else environ
    return env.get("JUDE_MCP_GLINER") or DEFAULT_GLINER
