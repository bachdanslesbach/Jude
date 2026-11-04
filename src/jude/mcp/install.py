"""``jude mcp install-claude-desktop``: write the server entry into Claude
Desktop's configuration file, with a backup, atomically, after the doctor
has passed.

The entry uses the absolute interpreter of the current virtual
environment and ``-m jude.mcp``, so Claude Desktop (whose PATH is not a
shell's) always finds the right Python. Its ``env`` carries the offline
flags and every pass-through variable (``JUDE_HOME``, ``HF_HOME``, the
cache paths, ``JUDE_MCP_LANGS``, ``JUDE_MCP_GLINER``) that is set and
non-empty in the installing shell, so the Desktop-launched Jude finds the
same models and the same database as the terminal's.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .env import OFFLINE_ENV, PASSTHROUGH

INVALID_JSON_MESSAGE = (
    "The Claude Desktop configuration file is not valid JSON; nothing was written. "
    "Fix or remove it, then run the installer again."
)


def claude_desktop_config_path(
    platform: str | None = None,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    platform = platform or sys.platform
    env = env if env is not None else os.environ
    home = home or Path.home()
    if platform == "darwin":
        return home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    if platform.startswith("win"):
        appdata = env.get("APPDATA")
        base = Path(appdata) if appdata else home / "AppData" / "Roaming"
        return base / "Claude" / "claude_desktop_config.json"
    xdg = env.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else home / ".config"
    return base / "Claude" / "claude_desktop_config.json"


def server_entry(
    jude_home: str | None = None, environ: Mapping[str, str] | None = None
) -> dict[str, Any]:
    """The ``mcpServers.jude`` entry: this interpreter, ``-m jude.mcp``, and
    an ``env`` made of the offline flags plus every ``PASSTHROUGH`` variable
    present and non-empty in ``environ``. An explicit ``jude_home`` wins."""

    environ = os.environ if environ is None else environ
    env: dict[str, str] = {}
    for key in PASSTHROUGH:
        value = environ.get(key)
        if value:
            env[key] = value
    if jude_home:
        env["JUDE_HOME"] = str(jude_home)
    env.update(OFFLINE_ENV)
    return {"command": sys.executable, "args": ["-m", "jude.mcp"], "env": env}


def copied_variables(entry: Mapping[str, Any]) -> list[str]:
    env = entry.get("env") or {}
    return sorted(k for k in env if k in PASSTHROUGH)


def _backup_name(path: Path, now: datetime | None = None) -> Path:
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    return path.with_name(f"{path.name}.bak-{stamp}")


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".claude_desktop_config.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def install(
    *,
    dry_run: bool = False,
    uninstall: bool = False,
    jude_home: str | None = None,
    skip_doctor: bool = False,
    config_path: Path | None = None,
    doctor: Callable[[], bool] | None = None,
    echo: Callable[[str], None] = print,
    environ: Mapping[str, str] | None = None,
) -> int:
    """Returns an exit code: 0 written (or dry-run), 1 doctor refused, 2
    the existing file is not usable JSON."""

    path = config_path or claude_desktop_config_path()
    if not uninstall and not skip_doctor:
        if doctor is None:
            from .doctor import doctor_ok

            doctor = doctor_ok
        if not doctor():
            echo(
                "jude mcp doctor found problems; fix them (`jude mcp doctor --fix`) or pass "
                "--skip-doctor. Nothing was written."
            )
            return 1

    data: dict[str, Any] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError):
            echo(INVALID_JSON_MESSAGE)
            return 2
        if not isinstance(loaded, dict):
            echo(INVALID_JSON_MESSAGE)
            return 2
        data = loaded
    servers = data.get("mcpServers")
    if servers is None:
        servers = {}
        data["mcpServers"] = servers
    if not isinstance(servers, dict):
        echo(INVALID_JSON_MESSAGE)
        return 2

    entry: dict[str, Any] | None = None
    if uninstall:
        servers.pop("jude", None)
    else:
        entry = server_entry(jude_home, environ)
        servers["jude"] = entry

    rendered = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    backup = _backup_name(path) if path.exists() else None

    if entry is not None:
        copied = copied_variables(entry)
        if copied:
            echo("Environment copied from this shell into the Desktop entry: " + ", ".join(copied))
        else:
            echo("No JUDE_HOME / HF_HOME / cache variable is set in this shell; defaults apply.")

    if dry_run:
        echo(rendered)
        echo(f"Would write {path}")
        if backup is not None:
            echo(f"Would back up the current file to {backup}")
        return 0

    if backup is not None:
        shutil.copy2(path, backup)
        echo(f"Backed up {path} to {backup}")
    _atomic_write(path, rendered)
    verb = "Removed the jude server from" if uninstall else "Wrote the jude server to"
    echo(f"{verb} {path}")
    echo("Restart Claude Desktop.")
    return 0
