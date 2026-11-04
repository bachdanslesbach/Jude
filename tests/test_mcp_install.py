"""Installer and doctor: the environment Claude Desktop gives the server."""

from __future__ import annotations

import json
import sys

import pytest

from jude.mcp import doctor as doc
from jude.mcp import env, install


def test_server_entry_copies_passthrough_env_only_when_set(tmp_path):
    shell = {
        "HF_HOME": str(tmp_path / "hf"),
        "JUDE_MCP_LANGS": "en,fr",
        "XDG_CACHE_HOME": "",  # empty: not copied
        "SECRET_SHELL_VAR": "nope",
        "PATH": "/usr/bin",
    }
    entry = install.server_entry(None, shell)
    assert entry["command"] == sys.executable and entry["args"] == ["-m", "jude.mcp"]
    assert entry["env"]["HF_HOME"] == str(tmp_path / "hf")
    assert entry["env"]["JUDE_MCP_LANGS"] == "en,fr"
    assert "XDG_CACHE_HOME" not in entry["env"]
    assert "SECRET_SHELL_VAR" not in entry["env"] and "PATH" not in entry["env"]
    for key, value in env.OFFLINE_ENV.items():
        assert entry["env"][key] == value
    assert "JUDE_HOME" not in entry["env"]
    entry = install.server_entry(str(tmp_path / "home"), {**shell, "JUDE_HOME": "/elsewhere"})
    assert entry["env"]["JUDE_HOME"] == str(tmp_path / "home")  # the explicit option wins
    assert install.copied_variables(entry) == ["HF_HOME", "JUDE_HOME", "JUDE_MCP_LANGS"]


def test_install_dry_run_reports_copied_variables(tmp_path):
    cfg = tmp_path / "claude_desktop_config.json"
    echoed: list[str] = []
    code = install.install(
        dry_run=True, skip_doctor=True, config_path=cfg, echo=echoed.append,
        environ={"HF_HOME": "/hf"},
    )
    assert code == 0 and not cfg.exists()
    assert any("HF_HOME" in line and "copied" in line for line in echoed)


def test_normalise_env_deletes_empty_paths():
    e = {"HF_HOME": "", "JUDE_HOME": "", "HF_HUB_CACHE": "/keep", "HF_HUB_OFFLINE": "0"}
    env.normalise_env(e)
    assert "HF_HOME" not in e and "JUDE_HOME" not in e
    assert e["HF_HUB_CACHE"] == "/keep"
    assert e["HF_HUB_OFFLINE"] == "0"  # an explicit value is not overridden
    for key, value in env.OFFLINE_ENV.items():
        if key != "HF_HUB_OFFLINE":
            assert e[key] == value
    assert env.langs({}) == ("en", "fr", "nl")
    assert env.langs({"JUDE_MCP_LANGS": " fr , nl "}) == ("fr", "nl")
    assert env.gliner_model({}) == env.DEFAULT_GLINER


def test_doctor_as_desktop_scrubs_env(tmp_path):
    cfg = tmp_path / "Claude" / "claude_desktop_config.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(json.dumps({"mcpServers": {"jude": {
        "command": sys.executable, "args": ["-m", "jude.mcp"],
        "env": {"JUDE_HOME": "/data/jude", "HF_HOME": "/data/hf"},
    }}}))
    shell = {"HOME": "/Users/x", "USER": "x", "PATH": "/opt/homebrew/bin:/usr/bin",
             "JUDE_MCP_LANGS": "en", "SECRET_SHELL_VAR": "nope", "HF_HOME": "/shell/hf"}
    out = doc.desktop_environment(config_path=cfg, environ=shell, platform="darwin")
    assert out["HOME"] == "/Users/x" and out["USER"] == "x"
    assert out["PATH"] == "/usr/bin:/bin:/usr/sbin:/sbin"
    assert out["JUDE_HOME"] == "/data/jude" and out["HF_HOME"] == "/data/hf"
    assert "SECRET_SHELL_VAR" not in out and "JUDE_MCP_LANGS" not in out
    for key, value in env.OFFLINE_ENV.items():
        assert out[key] == value
    # Without a config entry, the bundle's manifest env applies; ${...} refs are skipped.
    cfg.unlink()
    bundle = cfg.parent / doc.BUNDLE_DIR_NAME / "jude" / "manifest.json"
    bundle.parent.mkdir(parents=True)
    bundle.write_text(json.dumps({"name": "jude", "server": {"mcp_config": {
        "env": {"JUDE_HOME": "${user_config.jude_home}", "HF_HUB_OFFLINE": "1"},
    }}}))
    out = doc.desktop_environment(config_path=cfg, environ=shell, platform="darwin")
    assert "JUDE_HOME" not in out and out["HF_HUB_OFFLINE"] == "1"


def test_doctor_detects_bundle_and_duplicate(tmp_path, monkeypatch):
    monkeypatch.setenv("JUDE_HOME", str(tmp_path / "home"))
    cfg = tmp_path / "Claude" / "claude_desktop_config.json"
    cfg.parent.mkdir(parents=True)
    bundle = cfg.parent / doc.BUNDLE_DIR_NAME / "local.jude" / "manifest.json"
    bundle.parent.mkdir(parents=True)
    bundle.write_text(json.dumps({"name": "jude", "server": {"mcp_config": {"env": {}}}}))
    assert doc.find_bundle(cfg) == bundle
    checks = {c.name: c for c in doc.run_checks(config_path=cfg)}
    assert checks["config"].status == "OK" and "bundle" in checks["config"].detail
    cfg.write_text(json.dumps({"mcpServers": {"jude": {"command": sys.executable}}}))
    checks = {c.name: c for c in doc.run_checks(config_path=cfg)}
    assert checks["config"].status == "FIX" and "duplicate" in checks["config"].detail
    assert {"pdf", "xlsx", "trace"} <= set(checks)
    assert doc.TRACE_SENTENCE in checks["trace"].detail


def test_doctor_requires_nl_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("JUDE_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("JUDE_MCP_LANGS", raising=False)
    import jude.mcp.models as models

    monkeypatch.setattr(models, "spacy_model_missing", lambda lang: lang == "nl")
    cfg = tmp_path / "claude_desktop_config.json"
    spacy_checks = [c for c in doc.run_checks(config_path=cfg) if c.name == "spacy"]
    assert [c.detail.split(":")[0] for c in spacy_checks] == ["en", "fr", "nl"]
    nl = next(c for c in spacy_checks if c.detail.startswith("nl"))
    assert nl.status == "MISSING" and "nl_core_news_md" in (nl.fix or "")
    assert not doc.doctor_ok(spacy_checks)


def test_doctor_differences(tmp_path):
    a = [doc.Check("spacy", "OK", "nl: nl_core_news_md"), doc.Check("gliner", "OK", "x cached")]
    b = [doc.Check("spacy", "MISSING", "nl: no model installed"), doc.Check("gliner", "OK", "x")]
    diff = doc.differences(a, b)
    assert len(diff) == 1 and diff[0][0].name == "spacy" and diff[0][1].status == "MISSING"


@pytest.mark.parametrize("ttl", [None])
def test_run_checks_as_desktop_parses_json(tmp_path, ttl):
    def fake_run(cmd, env, capture_output, text, check):
        class P:
            stdout = json.dumps([{"name": "spacy", "status": "MISSING", "detail": "nl: none",
                                  "fix": "x"}])
        assert env["PATH"].startswith("/usr/bin") or "System32" in env["PATH"]
        return P()

    checks = doc.run_checks_as_desktop(
        {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}, run=fake_run
    )
    assert checks == [doc.Check("spacy", "MISSING", "nl: none", "x")]
