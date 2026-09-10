"""CLI smoke tests using Typer's CliRunner.

Each test points JUDE_HOME at a fresh tmp_path so they're isolated.
The detection pipeline runs for real — these are integration tests
against the underlying store, redact, and rehydrate logic, not just
the CLI argument parsing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from jude.cli import app


@pytest.fixture
def cli(tmp_path: Path, monkeypatch):
    """A CliRunner with JUDE_HOME redirected at tmp_path so each test
    starts from an empty database."""

    monkeypatch.setenv("JUDE_HOME", str(tmp_path))
    return CliRunner()


def _run(cli, *args, expect_success: bool = True):
    result = cli.invoke(app, list(args))
    if expect_success:
        assert result.exit_code == 0, (
            f"command {args} failed:\nstdout: {result.stdout}\n"
            f"stderr: {result.stderr if hasattr(result, 'stderr') else ''}"
        )
    return result


def test_init_creates_database(cli, tmp_path):
    _run(cli, "init")
    assert (tmp_path / "jude.db").exists()


def test_matter_create_and_list(cli):
    create = _run(cli, "matter", "create", "alpha")
    assert "Created matter" in create.stdout
    listed = _run(cli, "matter", "list")
    assert "alpha" in listed.stdout


def test_matter_create_smart_without_zr_is_persisted_but_unusable(cli):
    """create_matter doesn't enforce zr at creation time — the matter is
    persisted, but any actual send (smart mode + cloud backend + no zr)
    is refused at the LLM client level. The UI prevents this combination
    via a disabled-until-checked checkbox; the CLI is currently
    permissive. Documenting this asymmetry as a test for now."""

    result = cli.invoke(app, ["matter", "create", "smart-no-zr", "--mode", "smart"])
    assert result.exit_code == 0
    # The matter is persisted but flagged in `matter list` as zr=no.
    listed = _run(cli, "matter", "list")
    assert "smart-no-zr" in listed.stdout


def test_redact_and_rehydrate_round_trip_via_cli(cli, tmp_path):
    # Bootstrap matter and grab its id from the create output.
    create_result = _run(cli, "matter", "create", "round-trip")
    # Output looks like "Created matter <uuid> — round-trip (strict)"
    matter_id = create_result.stdout.split()[2]

    src = tmp_path / "memo.txt"
    src.write_text(
        "Acme Solutions SA filed a complaint. Acme Solutions SA is the client.",
        encoding="utf-8",
    )
    _run(cli, "redact", str(src), "--matter", matter_id)
    redacted = (tmp_path / "memo.redacted.txt").read_text(encoding="utf-8")
    assert "Acme Solutions SA" not in redacted
    assert "Org1" in redacted

    # Rehydrate brings the canonical back.
    rehydrate_in = tmp_path / "rehydrate_in.txt"
    rehydrate_in.write_text(redacted, encoding="utf-8")
    _run(cli, "rehydrate", str(rehydrate_in), "--matter", matter_id)
    out = (tmp_path / "rehydrate_in.rehydrated.txt").read_text(encoding="utf-8")
    assert "Acme Solutions SA" in out


def test_redact_supports_multiple_input_files(cli, tmp_path):
    create_result = _run(cli, "matter", "create", "bulk")
    matter_id = create_result.stdout.split()[2]

    a = tmp_path / "a.txt"
    a.write_text("Pioneer Industries SA is a Belgian company.", encoding="utf-8")
    b = tmp_path / "b.txt"
    b.write_text("Pioneer Industries SA also operates in Germany.", encoding="utf-8")

    _run(cli, "redact", str(a), str(b), "--matter", matter_id)

    a_red = (tmp_path / "a.redacted.txt").read_text(encoding="utf-8")
    b_red = (tmp_path / "b.redacted.txt").read_text(encoding="utf-8")
    assert "Pioneer Industries SA" not in a_red
    assert "Pioneer Industries SA" not in b_red
    # Same pseudonym across the two files.
    pseudonym_in_a = a_red.split()[0]
    assert pseudonym_in_a in b_red


def test_redact_rejects_out_with_multiple_inputs(cli, tmp_path):
    create_result = _run(cli, "matter", "create", "rej")
    matter_id = create_result.stdout.split()[2]
    a = tmp_path / "a.txt"
    a.write_text("Hello", encoding="utf-8")
    b = tmp_path / "b.txt"
    b.write_text("World", encoding="utf-8")
    out = tmp_path / "out.txt"
    result = cli.invoke(
        app, ["redact", str(a), str(b), "--matter", matter_id, "--out", str(out)]
    )
    assert result.exit_code != 0


def test_export_writes_valid_json(cli, tmp_path):
    create_result = _run(cli, "matter", "create", "exp")
    matter_id = create_result.stdout.split()[2]
    src = tmp_path / "in.txt"
    src.write_text("Acme Corp is the seller.", encoding="utf-8")
    _run(cli, "redact", str(src), "--matter", matter_id)

    out = tmp_path / "matter.json"
    _run(cli, "export", matter_id, "--out", str(out))
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["matter"]["id"] == matter_id
    assert data["matter"]["name"] == "exp"
    assert any(e["canonical"] == "Acme Corp" for e in data["entities"])


def test_review_lists_what_was_not_redacted(cli, tmp_path):
    """`jude review` is the fail-closed half of redaction: capitalised or
    identifier-like terms that survived redaction and are not known as
    public, in context. A bare codename word is exactly such a term —
    the neural layers drop it on purpose until the policy is settled."""

    create_result = _run(cli, "matter", "create", "review-matter")
    matter_id = create_result.stdout.split()[2]
    src = tmp_path / "memo.txt"
    src.write_text(
        "Acme Solutions SA sued in Delaware. The court asked Helios to reply; "
        "Helios declined.",
        encoding="utf-8",
    )
    result = _run(cli, "review", str(src), "--matter", matter_id)
    assert "unverified" in result.stdout
    # One line per listed term: "  <term> ×<count>   <context>". The
    # context quotes the raw text, so only the term column is asserted.
    listed = [line.strip().split(" ×")[0] for line in result.stdout.splitlines()
              if " ×" in line]
    assert "Helios" in listed, result.stdout
    assert "Acme Solutions SA" not in listed  # redacted, hence not listed
    assert "Delaware" not in listed  # public jurisdiction
