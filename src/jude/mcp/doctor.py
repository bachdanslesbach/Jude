"""``jude mcp doctor``: one line per check, ``OK`` / ``MISSING`` / ``FIX``.

``--as-desktop`` re-runs the checks in a subprocess whose environment is
what Claude Desktop would give the server (a bare PATH, HOME and USER,
plus the ``env`` of the configured jude entry or of the bundle's
manifest, plus the offline flags): when the two runs differ, both are
printed, so a model that the terminal sees and the plugin does not is
found before the first document.

``--fix`` is the only place in the plugin that is allowed to use the
network (downloading spaCy models and GLiNER weights): it runs in the
terminal, says so in plain words first, and asks once. It never touches
the Desktop configuration.
"""

from __future__ import annotations

import json
import os
import socket
import stat
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from ..paths import default_db_path, jude_home
from . import env as _env
from . import models
from .install import claude_desktop_config_path
from .launch import pid_alive, read_window_file, state_dir

Status = Literal["OK", "MISSING", "FIX"]

_SPACY_DEFAULTS = {"en": "en_core_web_lg", "fr": "fr_core_news_md", "nl": "nl_core_news_md"}
# Checks whose failure must block the installer.
REQUIRED: frozenset[str] = frozenset({"interpreter", "importable", "spacy", "home", "bind"})
TRACE_SENTENCE = "contains document fragments; never share this file"
BUNDLE_DIR_NAME = "Claude Extensions"


@dataclass
class Check:
    name: str
    status: Status
    detail: str
    fix: str | None = None

    def line(self) -> str:
        base = f"{self.status:<8}{self.name:<14}{self.detail}"
        return base if not self.fix or self.status == "OK" else f"{base}\n        fix: {self.fix}"


def _mode_ok(path: Path, wanted: int) -> bool:
    try:
        return stat.S_IMODE(path.stat().st_mode) == wanted
    except OSError:
        return False


def find_bundle(config_path: Path) -> Path | None:
    """The installed Jude bundle, if any: a ``manifest.json`` whose name is
    ``jude`` under the extensions directory beside the Desktop config
    (``Claude Extensions/`` on macOS; to be confirmed on the first bundle
    install)."""

    root = config_path.parent / BUNDLE_DIR_NAME
    if not root.is_dir():
        return None
    for manifest in sorted(root.glob("*/manifest.json")) + sorted(root.glob("*/*/manifest.json")):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("name") == "jude":
            return manifest
    return None


def _config_entry(config_path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """(jude entry, error) from the Desktop configuration."""

    if not config_path.exists():
        return None, None
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        entry = data.get("mcpServers", {}).get("jude")
    except (ValueError, AttributeError, UnicodeDecodeError):
        return None, "invalid"
    return (entry if isinstance(entry, dict) else None), None


def desktop_environment(
    *,
    config_path: Path | None = None,
    environ: Mapping[str, str] | None = None,
    platform: str | None = None,
) -> dict[str, str]:
    """What Claude Desktop hands the server: a bare base plus the entry's
    ``env`` (or the bundle manifest's) plus the offline flags. Nothing from
    the current shell except HOME/USER (Windows: SystemRoot, USERPROFILE,
    APPDATA)."""

    environ = os.environ if environ is None else environ
    platform = platform or sys.platform
    cfg = config_path or claude_desktop_config_path()
    out: dict[str, str] = {}
    if platform == "win32":
        for key in ("SystemRoot", "USERPROFILE", "APPDATA"):
            if environ.get(key):
                out[key] = environ[key]
        out["PATH"] = str(Path(environ.get("SystemRoot", r"C:\Windows")) / "System32")
    else:
        for key in ("HOME", "USER"):
            if environ.get(key):
                out[key] = environ[key]
        out["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
    entry, _err = _config_entry(cfg)
    source_env: Mapping[str, Any] | None = None
    if entry is not None and isinstance(entry.get("env"), dict):
        source_env = entry["env"]
    else:
        bundle = find_bundle(cfg)
        if bundle is not None:
            try:
                manifest = json.loads(bundle.read_text(encoding="utf-8"))
                source_env = manifest.get("server", {}).get("mcp_config", {}).get("env")
            except (OSError, ValueError, AttributeError):
                source_env = None
    for key, value in (source_env or {}).items():
        if isinstance(value, str) and not value.startswith("${"):
            out[str(key)] = value
    for key, value in _env.OFFLINE_ENV.items():
        out.setdefault(key, value)
    return out


def run_checks(
    *,
    config_path: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> list[Check]:
    environ = os.environ if environ is None else environ
    checks: list[Check] = []

    exe = Path(sys.executable)
    checks.append(Check("interpreter", "OK" if exe.exists() else "MISSING", str(exe)))

    cfg = config_path or claude_desktop_config_path()
    entry, err = _config_entry(cfg)
    bundle = find_bundle(cfg)
    if err == "invalid":
        checks.append(Check("config", "FIX", f"{cfg} is not valid JSON"))
    elif entry is not None and bundle is not None:
        checks.append(
            Check("config", "FIX", "duplicate: config entry and bundle; remove one",
                  "jude mcp install-claude-desktop --uninstall, or uninstall the bundle")
        )
    elif entry is not None:
        if entry.get("command") != sys.executable:
            checks.append(Check("config", "FIX", "configured interpreter differs from this one",
                                "jude mcp install-claude-desktop"))
        else:
            checks.append(Check("config", "OK", str(cfg)))
    elif bundle is not None:
        checks.append(Check("config", "OK", f"OK (bundle) {bundle.parent}"))
    elif cfg.exists():
        checks.append(Check("config", "MISSING", f"no jude entry in {cfg}",
                            "jude mcp install-claude-desktop"))
    else:
        checks.append(Check("config", "MISSING", f"{cfg} not found",
                            "jude mcp install-claude-desktop"))

    try:
        import mcp  # noqa: F401

        import jude.mcp.server  # noqa: F401

        checks.append(Check("importable", "OK", "jude.mcp and the mcp SDK import"))
    except Exception as exc:
        checks.append(Check("importable", "MISSING", type(exc).__name__,
                            'pip install "jude[mcp]"'))

    for lang in _env.langs(environ):
        if models.spacy_model_missing(lang):
            wanted = _SPACY_DEFAULTS.get(lang, f"{lang}_core_news_md")
            checks.append(Check("spacy", "MISSING", f"{lang}: no model installed",
                                f"{sys.executable} -m spacy download {wanted}"))
        else:
            from ..detect.spacy_detector import _resolve_model_for_language

            checks.append(Check("spacy", "OK", f"{lang}: {_resolve_model_for_language(lang, {})}"))

    gliner_model = _env.gliner_model(environ)
    if models.gliner_package_missing():
        checks.append(Check("gliner", "MISSING", "gliner package not installed",
                            'pip install "jude[gliner]"'))
    elif models.gliner_cached(gliner_model):
        checks.append(Check("gliner", "OK", f"{gliner_model} cached"))
    else:
        checks.append(Check("gliner", "MISSING", f"{gliner_model} weights not cached",
                            f"{sys.executable} -c \"from gliner import GLiNER; "
                            f"GLiNER.from_pretrained('{gliner_model}')\""))

    for name, module, extra in (("pdf", "pymupdf", "pdf"), ("xlsx", "openpyxl", "xlsx")):
        try:
            __import__(module)
        except ImportError:
            checks.append(Check(name, "MISSING", f"{module} not installed (optional)",
                                f'pip install "jude[{extra}]"'))
        else:
            checks.append(Check(name, "OK", f"{module} importable"))

    home = jude_home()
    db = default_db_path()
    if not home.is_dir():
        checks.append(Check("home", "MISSING", str(home), "jude init"))
    elif not _mode_ok(home, 0o700) or (db.exists() and not _mode_ok(db, 0o600)):
        checks.append(Check("home", "FIX", f"{home} should be 0700 and jude.db 0600",
                            f"chmod 700 {home}; chmod 600 {db}"))
    else:
        checks.append(Check("home", "OK", f"{home} 0700, jude.db 0600"))

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
        checks.append(Check("bind", "OK", "127.0.0.1 ephemeral port"))
    except OSError as exc:
        checks.append(Check("bind", "MISSING", f"cannot bind 127.0.0.1: {type(exc).__name__}"))

    sdir = state_dir()
    stale = [p for p in sdir.glob("window-*.json") if _stale(p)] if sdir.is_dir() else []
    tmp = sdir / "tmp"
    stale_tmp = list(tmp.iterdir()) if tmp.is_dir() else []
    if stale or stale_tmp:
        detail = f"{len(stale)} window file(s), {len(stale_tmp)} temp dir(s)"
        checks.append(Check("stale", "FIX", detail, "jude mcp doctor --fix"))
    else:
        checks.append(Check("stale", "OK", "no stale window or temp files"))

    trace = sdir / "trace.log"
    if trace.exists():
        size = sum(p.stat().st_size for p in sdir.glob("trace.log*"))
        checks.append(Check("trace", "OK", f"{trace} ({size} bytes; {TRACE_SENTENCE})",
                            "jude mcp doctor --fix deletes it"))
    else:
        checks.append(Check("trace", "OK" if sdir.is_dir() else "MISSING",
                            f"{trace} (created on first run; {TRACE_SENTENCE})"))

    desktop_logs = _desktop_log_dir()
    checks.append(Check("desktop-logs", "OK" if desktop_logs.exists() else "MISSING",
                        str(desktop_logs)))
    return checks


def run_checks_as_desktop(
    desktop_env: Mapping[str, str], *, run: Callable[..., Any] | None = None
) -> list[Check]:
    """Run the checks in a subprocess with exactly ``desktop_env``."""

    runner = run or subprocess.run
    proc = runner(
        [sys.executable, "-m", "jude.mcp.doctor", "--json"],
        env=dict(desktop_env),
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        rows = json.loads(proc.stdout or "[]")
    except ValueError:
        return [Check("as-desktop", "FIX", "the Desktop-environment run produced no report")]
    return [Check(**row) for row in rows if isinstance(row, dict)]


def differences(terminal: list[Check], desktop: list[Check]) -> list[tuple[Check, Check | None]]:
    """Pairs (terminal check, desktop check) whose status differs."""

    remaining: dict[str, list[Check]] = {}
    for c in desktop:
        remaining.setdefault(c.name, []).append(c)
    out: list[tuple[Check, Check | None]] = []
    for c in terminal:
        pool = remaining.get(c.name) or []
        other = pool.pop(0) if pool else None
        if other is None or other.status != c.status:
            out.append((c, other))
    return out


def _stale(path: Path) -> bool:
    info = read_window_file(path)
    if info is None:
        return True
    try:
        return not pid_alive(int(info["pid"]))
    except (TypeError, ValueError):
        return True


def _desktop_log_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "Claude"
    if sys.platform.startswith("win"):
        return Path(os.environ.get("APPDATA", str(Path.home()))) / "Claude" / "logs"
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "Claude" / "logs"


def doctor_ok(checks: list[Check] | None = None) -> bool:
    checks = checks if checks is not None else run_checks()
    return all(c.status == "OK" for c in checks if c.name in REQUIRED)


def fix(
    checks: list[Check],
    *,
    confirm: Callable[[str], bool],
    echo: Callable[[str], None] = print,
    run: Callable[[list[str]], int] | None = None,
) -> None:
    """Apply the fixes the user confirms once. Uses the network for model
    downloads — from the terminal, after saying so. Offers to delete the
    trace files. Never writes the Claude Desktop configuration."""

    fixable = ("spacy", "gliner", "home", "stale", "trace")
    todo = [
        c for c in checks
        if c.name in fixable and (c.status != "OK" or (c.name == "trace" and c.fix))
    ]
    if not todo:
        echo("Nothing to fix.")
        return
    echo("The following will be done (model downloads use the network, from this terminal):")
    for c in todo:
        echo(f"  - {c.name}: {c.fix or c.detail}")
    if not confirm("Proceed? [y/N] "):
        echo("Nothing changed.")
        return
    runner = run or (lambda cmd: subprocess.run(cmd, check=False).returncode)
    for c in todo:
        if c.name == "spacy" and c.fix:
            runner(c.fix.split())
        elif c.name == "gliner" and "from_pretrained" in (c.fix or ""):
            model = _env.gliner_model()
            code = f"from gliner import GLiNER; GLiNER.from_pretrained('{model}')"
            runner([sys.executable, "-c", code])
        elif c.name == "home":
            home = jude_home()
            home.mkdir(parents=True, exist_ok=True)
            os.chmod(home, 0o700)
            db = default_db_path()
            if db.exists():
                os.chmod(db, 0o600)
        elif c.name == "stale":
            from .launch import sweep_stale_files

            sweep_stale_files(state_dir(), now=lambda: float("inf"))
        elif c.name == "trace":
            for p in state_dir().glob("trace.log*"):
                p.unlink(missing_ok=True)
    echo("Done. Run `jude mcp doctor` again to confirm.")


def _emit_json() -> None:
    print(json.dumps([asdict(c) for c in run_checks()]))


if __name__ == "__main__":  # pragma: no cover — the --as-desktop subprocess
    if "--json" in sys.argv[1:]:
        _emit_json()
    else:
        for check in run_checks():
            print(check.line())
