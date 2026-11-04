#!/usr/bin/env python3
"""Build the Claude Desktop bundle (``dist/jude-<version>.mcpb``) from ``mcpb/``.

Standard library only. The bundle is a zip archive with ``manifest.json`` at
its root, the icon, and the entry-point stub; it contains no Python runtime,
no models and no Jude code — the manifest points Claude Desktop at the
``jude`` executable the user picks at install time.

Usage::

    python scripts/build_mcpb.py                 # -> dist/jude-<version>.mcpb
    python scripts/build_mcpb.py --out build/    # another output directory
    python scripts/build_mcpb.py --check         # validate only, write nothing
    python scripts/build_mcpb.py --validate      # also run `npx @anthropic-ai/mcpb validate`
                                                 # (fetches an npm package: network, in
                                                 # your terminal, never in the server)

The script refuses to build when the manifest is invalid: every problem is
printed, one per line, and the exit code is 1. Nothing is written to ``dist/``
in that case.

Importable API (used by the tests)::

    read_version(pyproject_path) -> str
    load_manifest(mcpb_dir) -> dict
    validate(manifest, mcpb_dir, expected_version=None) -> list[str]   # [] when valid
    build(out_dir, mcpb_dir=..., pyproject=...) -> Path                 # raises ManifestError
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import stat
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
MCPB_DIR = REPO_ROOT / "mcpb"
PYPROJECT = REPO_ROOT / "pyproject.toml"
DEFAULT_OUT = REPO_ROOT / "dist"

SERVER_TYPES = frozenset({"binary", "node", "python"})
USER_CONFIG_TYPES = frozenset({"string", "number", "boolean", "directory", "file"})
MANIFEST_VERSIONS = frozenset({"0.1", "0.2", "0.3"})

# https://semver.org/#is-there-a-suggested-regular-expression-regex-to-check-a-semver-string
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)
# Any `${...}` occurrence inside mcp_config strings.
VARIABLE = re.compile(r"\$\{[^}]*\}")
# The only substitutions Claude Desktop performs inside mcp_config.
ALLOWED_VARIABLE = re.compile(r"^\$\{(__dirname|pathSeparator|/|user_config\..+)\}$")
USER_CONFIG_REF = re.compile(r"^\$\{user_config\.(.+)\}$")

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# Files under mcpb/ that are not part of the bundle.
BUNDLE_EXCLUDE_NAMES = frozenset({"README.md", ".DS_Store"})
BUNDLE_EXCLUDE_DIRS = frozenset({"__pycache__"})


class ManifestError(ValueError):
    """Raised by :func:`build` when the manifest does not pass :func:`validate`."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("\n".join(errors))
        self.errors = errors


# --------------------------------------------------------------------------- inputs


def read_version(pyproject: Path = PYPROJECT) -> str:
    """Return ``[project].version`` from ``pyproject.toml``."""
    with pyproject.open("rb") as fh:
        data = tomllib.load(fh)
    try:
        version = data["project"]["version"]
    except KeyError as exc:
        raise ManifestError([f"{pyproject}: no [project].version"]) from exc
    if not isinstance(version, str) or not version:
        raise ManifestError([f"{pyproject}: [project].version must be a non-empty string"])
    return version


def load_manifest(mcpb_dir: Path = MCPB_DIR) -> dict[str, Any]:
    """Parse ``mcpb_dir/manifest.json``; a parse error is reported as a ManifestError."""
    path = mcpb_dir / "manifest.json"
    if not path.is_file():
        raise ManifestError([f"{path}: not found"])
    try:
        with path.open("rb") as fh:
            manifest = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ManifestError([f"{path}: invalid JSON — {exc.msg} (line {exc.lineno})"]) from exc
    if not isinstance(manifest, dict):
        raise ManifestError([f"{path}: top level must be a JSON object"])
    return manifest


# --------------------------------------------------------------------------- validation


def _get(d: Any, *keys: str) -> Any:
    for key in keys:
        if not isinstance(d, dict) or key not in d:
            return None
        d = d[key]
    return d


def _nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _is_executable(path: Path) -> bool:
    return bool(path.stat().st_mode & stat.S_IXUSR)


def _iter_strings(node: Any, where: str):
    """Yield ``(path, string)`` for every string nested in ``node``."""
    if isinstance(node, str):
        yield where, node
    elif isinstance(node, list):
        for i, item in enumerate(node):
            yield from _iter_strings(item, f"{where}[{i}]")
    elif isinstance(node, dict):
        for key, item in node.items():
            yield from _iter_strings(item, f"{where}.{key}")


def _safe_relative(rel: str) -> bool:
    """A bundle-relative path: no absolute, no drive, no ``..`` component."""
    if not rel or rel.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", rel):
        return False
    return ".." not in Path(rel).parts


def validate(
    manifest: dict[str, Any],
    mcpb_dir: Path = MCPB_DIR,
    expected_version: str | None = None,
) -> list[str]:
    """Return the list of problems with ``manifest``; an empty list means valid.

    Checks (from the bundle design, §B.7): the required keys; ``version`` is
    semver and, when ``expected_version`` is given, equals it; ``server.type``
    is one of binary/node/python; ``server.entry_point`` exists in the bundle
    and is executable; ``server.mcp_config.command`` is set; every
    ``user_config`` entry has a ``title``, a ``description`` and a known
    ``type`` (``directory`` included — the bundle's optional ``jude_home`` and
    ``hf_home`` folders); every ``${...}`` inside ``mcp_config`` is one Claude
    Desktop substitutes (``${__dirname}``, ``${pathSeparator}``, ``${/}``,
    ``${user_config.X}`` with ``X`` declared); a ``${user_config.X}`` used as
    the ``command`` is a *required* entry; ``icon`` is an existing PNG inside
    the bundle; and the ``tools`` list, when present, is a list of
    ``{name, description}``.
    """
    errors: list[str] = []

    # --- identity
    mv = manifest.get("manifest_version")
    if not _nonempty_str(mv):
        errors.append("manifest_version: required string")
    elif mv not in MANIFEST_VERSIONS:
        errors.append(f"manifest_version: {mv!r} is not one of {sorted(MANIFEST_VERSIONS)}")

    name = manifest.get("name")
    if not _nonempty_str(name):
        errors.append("name: required string")
    elif not re.match(r"^[a-z0-9][a-z0-9._-]*$", name):
        errors.append(f"name: {name!r} should be lowercase letters, digits, '.', '_' or '-'")

    version = manifest.get("version")
    if not _nonempty_str(version):
        errors.append("version: required string")
    elif not SEMVER.match(version):
        errors.append(f"version: {version!r} is not semver (MAJOR.MINOR.PATCH)")
    elif expected_version is not None and version != expected_version:
        errors.append(
            f"version: manifest says {version!r} but pyproject.toml says {expected_version!r}"
        )

    if not _nonempty_str(manifest.get("description")):
        errors.append("description: required string")

    if not _nonempty_str(_get(manifest, "author", "name")):
        errors.append("author.name: required string")

    # --- server
    server = manifest.get("server")
    if not isinstance(server, dict):
        errors.append("server: required object")
        server = {}

    stype = server.get("type")
    if stype not in SERVER_TYPES:
        errors.append(f"server.type: {stype!r} is not one of {sorted(SERVER_TYPES)}")

    entry = server.get("entry_point")
    if not _nonempty_str(entry):
        errors.append("server.entry_point: required string")
    elif not _safe_relative(entry):
        errors.append(f"server.entry_point: {entry!r} must be a relative path inside the bundle")
    else:
        entry_path = mcpb_dir / entry
        if not entry_path.is_file():
            errors.append(f"server.entry_point: {entry!r} does not exist under {mcpb_dir}")
        elif not _is_executable(entry_path):
            errors.append(f"server.entry_point: {entry!r} is not executable (chmod 755)")

    mcp_config = server.get("mcp_config")
    if not isinstance(mcp_config, dict):
        errors.append("server.mcp_config: required object")
        mcp_config = {}
    if not _nonempty_str(mcp_config.get("command")):
        errors.append("server.mcp_config.command: required string")
    args = mcp_config.get("args", [])
    if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        errors.append("server.mcp_config.args: must be a list of strings")
    env = mcp_config.get("env", {})
    if not isinstance(env, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in env.items()
    ):
        errors.append("server.mcp_config.env: must be an object of string values")

    # --- user_config
    user_config = manifest.get("user_config", {})
    if not isinstance(user_config, dict):
        errors.append("user_config: must be an object")
        user_config = {}
    for key, spec in user_config.items():
        if not isinstance(spec, dict):
            errors.append(f"user_config.{key}: must be an object")
            continue
        if not _nonempty_str(spec.get("title")):
            errors.append(f"user_config.{key}.title: required string")
        if not _nonempty_str(spec.get("description")):
            errors.append(f"user_config.{key}.description: required string")
        if spec.get("type") not in USER_CONFIG_TYPES:
            errors.append(
                f"user_config.{key}.type: {spec.get('type')!r} is not one of "
                f"{sorted(USER_CONFIG_TYPES)}"
            )
        if "required" in spec and not isinstance(spec["required"], bool):
            errors.append(f"user_config.{key}.required: must be true or false")

    # --- ${...} substitutions inside mcp_config
    for where, text in _iter_strings(mcp_config, "server.mcp_config"):
        for var in VARIABLE.findall(text):
            if not ALLOWED_VARIABLE.match(var):
                errors.append(
                    f"{where}: {var} is not a substitution Claude Desktop performs "
                    "(allowed: ${__dirname}, ${pathSeparator}, ${/}, ${user_config.<key>})"
                )
                continue
            ref = USER_CONFIG_REF.match(var)
            if ref is None:
                continue
            spec = user_config.get(ref.group(1))
            if spec is None:
                errors.append(f"{where}: {var} refers to an undeclared user_config key")
            elif where == "server.mcp_config.command" and (
                not isinstance(spec, dict) or spec.get("required") is not True
            ):
                # An optional entry left empty arrives as "" — an empty command
                # cannot start anything. Optional entries belong in `env` (where
                # the server deletes empty values at start), not in `command`.
                errors.append(
                    f"{where}: {var} must be a required user_config entry "
                    '("required": true) — an empty command cannot start the server'
                )

    # --- icon
    icon = manifest.get("icon")
    if icon is not None:
        if not _nonempty_str(icon):
            errors.append("icon: must be a relative path string")
        elif not _safe_relative(icon):
            errors.append(f"icon: {icon!r} must be a relative path inside the bundle")
        elif not icon.lower().endswith(".png"):
            errors.append(f"icon: {icon!r} must be a .png file")
        else:
            icon_path = mcpb_dir / icon
            if not icon_path.is_file():
                errors.append(f"icon: {icon!r} does not exist under {mcpb_dir}")
            else:
                with icon_path.open("rb") as fh:
                    if fh.read(8) != PNG_SIGNATURE:
                        errors.append(f"icon: {icon!r} is not a PNG file")

    # --- tools
    tools = manifest.get("tools")
    if tools is not None:
        if not isinstance(tools, list):
            errors.append("tools: must be a list")
        else:
            seen: set[str] = set()
            for i, tool in enumerate(tools):
                if not isinstance(tool, dict) or not _nonempty_str(tool.get("name")):
                    errors.append(f"tools[{i}]: must be an object with a name")
                    continue
                if not _nonempty_str(tool.get("description")):
                    errors.append(f"tools[{i}] ({tool['name']}): description required")
                if tool["name"] in seen:
                    errors.append(f"tools[{i}]: duplicate tool name {tool['name']!r}")
                seen.add(tool["name"])

    # --- privacy_policies / compatibility: shape only
    policies = manifest.get("privacy_policies")
    if policies is not None and (
        not isinstance(policies, list) or not all(isinstance(p, str) for p in policies)
    ):
        errors.append("privacy_policies: must be a list of URL strings")
    platforms = _get(manifest, "compatibility", "platforms")
    if platforms is not None and (
        not isinstance(platforms, list)
        or not all(p in {"darwin", "win32", "linux"} for p in platforms)
    ):
        errors.append("compatibility.platforms: must be a list of darwin/win32/linux")

    return errors


# --------------------------------------------------------------------------- build


def bundle_files(mcpb_dir: Path = MCPB_DIR) -> list[Path]:
    """Regular files under ``mcpb_dir`` that go into the archive, manifest first."""
    files: list[Path] = []
    for path in sorted(mcpb_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(mcpb_dir)
        if rel.name in BUNDLE_EXCLUDE_NAMES or rel.name.startswith("."):
            continue
        if any(part in BUNDLE_EXCLUDE_DIRS for part in rel.parts):
            continue
        files.append(path)
    files.sort(key=lambda p: (p.name != "manifest.json" or p.parent != mcpb_dir, p.as_posix()))
    return files


def build(
    out_dir: Path = DEFAULT_OUT,
    *,
    mcpb_dir: Path = MCPB_DIR,
    pyproject: Path = PYPROJECT,
) -> Path:
    """Validate, then write ``out_dir/<name>-<version>.mcpb``. Raises ManifestError."""
    version = read_version(pyproject)
    manifest = load_manifest(mcpb_dir)
    errors = validate(manifest, mcpb_dir, expected_version=version)
    if errors:
        raise ManifestError(errors)

    entry = manifest["server"]["entry_point"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{manifest['name']}-{version}.mcpb"
    tmp_path = out_path.with_suffix(".mcpb.part")

    with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in bundle_files(mcpb_dir):
            arcname = path.relative_to(mcpb_dir).as_posix()
            info = zipfile.ZipInfo.from_file(path, arcname)
            mode = stat.S_IMODE(path.stat().st_mode)
            if arcname == entry:
                mode = 0o755
            info.external_attr = ((stat.S_IFREG | mode) & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            with path.open("rb") as fh:
                zf.writestr(info, fh.read(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

    with zipfile.ZipFile(tmp_path) as zf:
        bad = zf.testzip()
        names = zf.namelist()
    if bad is not None:
        tmp_path.unlink(missing_ok=True)
        raise ManifestError([f"{tmp_path}: corrupt member {bad!r}"])
    if "manifest.json" not in names:
        tmp_path.unlink(missing_ok=True)
        raise ManifestError([f"{tmp_path}: manifest.json is not at the archive root"])

    tmp_path.replace(out_path)
    return out_path


def npx_validate(mcpb_dir: Path = MCPB_DIR) -> int:
    """Run ``npx @anthropic-ai/mcpb validate`` on the manifest.

    Returns the validator's exit code, or 0 when ``npx`` is not installed.
    """
    npx = shutil.which("npx")
    if npx is None:
        print("npx not found; skipping `@anthropic-ai/mcpb validate`", file=sys.stderr)
        return 0
    cmd = [npx, "--yes", "@anthropic-ai/mcpb", "validate", str(mcpb_dir / "manifest.json")]
    print("running:", " ".join(cmd), "(downloads an npm package — network, in this terminal)")
    return subprocess.run(cmd, check=False).returncode


# --------------------------------------------------------------------------- cli


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="output directory (default: dist/)",
    )
    parser.add_argument(
        "--mcpb-dir",
        type=Path,
        default=MCPB_DIR,
        help="bundle source directory (default: mcpb/)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the manifest and exit without writing anything",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="after building, run `npx @anthropic-ai/mcpb validate` when npx is available",
    )
    args = parser.parse_args(argv)

    try:
        if args.check:
            version = read_version()
            manifest = load_manifest(args.mcpb_dir)
            errors = validate(manifest, args.mcpb_dir, expected_version=version)
            if errors:
                raise ManifestError(errors)
            print(f"manifest OK: {manifest['name']} {version}")
            return 0
        out_path = build(args.out, mcpb_dir=args.mcpb_dir)
    except ManifestError as exc:
        print("manifest invalid — nothing written:", file=sys.stderr)
        for line in exc.errors:
            print(f"  - {line}", file=sys.stderr)
        return 1

    size = out_path.stat().st_size
    print(f"wrote {out_path} ({size:,} bytes)")
    if args.validate:
        return npx_validate(args.mcpb_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
