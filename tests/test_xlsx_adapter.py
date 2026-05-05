"""Tests for the XLSX adapter.

Written test-first — at the time of this commit `jude.adapters.xlsx`
does not exist; these tests must fail (red). The next commit makes
them green.

Concept being specified
-----------------------

Spreadsheets are common in competition / antitrust work: market-share
grids, pricing data, transaction lists, capacity tables. The adapter
must:

  * Read every cell across every sheet, returning a flat text
    representation suitable for the redaction pipeline along with a
    structural map (sheet → row → col) for write-back.
  * Surface metadata warnings the same way DocxAdapter does — author
    names in workbook properties leak.
  * Write a redacted copy that preserves the workbook structure
    (sheet names, cell positions) but replaces text-cell contents
    with their redacted form. Formula cells are replaced with their
    cached text value, since redacting a formula would leak the
    referenced cells' real names through the formula's references.
"""

from __future__ import annotations

from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

from jude.adapters.xlsx import (
    PARAGRAPH_SEP,
    XlsxAdapter,
    XlsxExtraction,
)


def _make_workbook(
    path: Path,
    sheets: dict[str, list[list[str | int | float]]],
    *,
    author: str = "",
) -> None:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for sheet_name, rows in sheets.items():
        ws = wb.create_sheet(title=sheet_name)
        for row in rows:
            ws.append(row)
    if author:
        wb.properties.creator = author
        wb.properties.lastModifiedBy = author
    wb.save(str(path))


# ---------- read ----------


def test_read_extracts_text_from_every_sheet(tmp_path: Path):
    src = tmp_path / "in.xlsx"
    _make_workbook(
        src,
        {
            "Parties": [
                ["Buyer", "Seller"],
                ["Meta Platforms Inc.", "Lumen Reality SARL"],
            ],
            "Financials": [
                ["Item", "Amount EUR"],
                ["Purchase price", 450_000_000],
            ],
        },
    )
    extraction = XlsxAdapter.read(src)
    assert isinstance(extraction, XlsxExtraction)
    assert "Meta Platforms Inc." in extraction.text
    assert "Lumen Reality SARL" in extraction.text
    assert "Purchase price" in extraction.text
    # Sheet names appear as section markers so the LLM understands the
    # spreadsheet structure.
    assert "Parties" in extraction.text
    assert "Financials" in extraction.text


def test_read_warns_on_author_metadata(tmp_path: Path):
    src = tmp_path / "in.xlsx"
    _make_workbook(
        src, {"Sheet": [["Hello"]]}, author="Jane Doe",
    )
    extraction = XlsxAdapter.read(src)
    assert any("metadata" in w.lower() for w in extraction.warnings)
    assert extraction.core_properties.get("creator") == "Jane Doe"


def test_read_handles_empty_workbook(tmp_path: Path):
    src = tmp_path / "in.xlsx"
    _make_workbook(src, {"Sheet1": []})
    extraction = XlsxAdapter.read(src)
    assert extraction.text == "" or extraction.text.strip() == "Sheet1"


def test_read_includes_numeric_cell_values_as_strings(tmp_path: Path):
    src = tmp_path / "in.xlsx"
    _make_workbook(src, {"Numbers": [[42, 3.14, "ok"]]})
    extraction = XlsxAdapter.read(src)
    assert "42" in extraction.text
    assert "3.14" in extraction.text


# ---------- write ----------


def test_write_redacted_preserves_sheet_names(tmp_path: Path):
    src = tmp_path / "in.xlsx"
    dst = tmp_path / "out.xlsx"
    _make_workbook(
        src,
        {"Sheet A": [["Amazon", "Microsoft"]], "Sheet B": [["Org"]]},
    )
    XlsxAdapter.write_redacted(src, dst, replacements={"Amazon": "Org1", "Microsoft": "Org2"})
    wb = openpyxl.load_workbook(str(dst))
    assert "Sheet A" in wb.sheetnames
    assert "Sheet B" in wb.sheetnames


def test_write_redacted_replaces_text_cells_in_place(tmp_path: Path):
    src = tmp_path / "in.xlsx"
    dst = tmp_path / "out.xlsx"
    _make_workbook(
        src,
        {"S": [["Amazon paid", "Microsoft received"], ["other", "data"]]},
    )
    XlsxAdapter.write_redacted(
        src,
        dst,
        replacements={"Amazon": "Org1", "Microsoft": "Org2"},
    )
    wb = openpyxl.load_workbook(str(dst))
    ws = wb["S"]
    a1 = ws["A1"].value
    b1 = ws["B1"].value
    assert "Amazon" not in a1
    assert "Org1" in a1
    assert "Microsoft" not in b1
    assert "Org2" in b1


def test_write_redacted_clears_workbook_metadata_when_requested(tmp_path: Path):
    src = tmp_path / "in.xlsx"
    dst = tmp_path / "out.xlsx"
    _make_workbook(src, {"S": [["Hello"]]}, author="Jane Doe")
    XlsxAdapter.write_redacted(src, dst, replacements={}, clear_metadata=True)
    wb = openpyxl.load_workbook(str(dst))
    assert (wb.properties.creator or "") == ""
    assert (wb.properties.lastModifiedBy or "") == ""


def test_write_redacted_leaves_numeric_cells_unchanged(tmp_path: Path):
    """Numbers don't get redacted by string-replacement — that would mangle
    them. Numeric cells pass through verbatim."""

    src = tmp_path / "in.xlsx"
    dst = tmp_path / "out.xlsx"
    _make_workbook(src, {"S": [[42, 3.14, "Amazon"]]})
    XlsxAdapter.write_redacted(src, dst, replacements={"Amazon": "Org1"})
    wb = openpyxl.load_workbook(str(dst))
    row = list(wb["S"].iter_rows(values_only=True))[0]
    assert row[0] == 42
    assert row[1] == 3.14
    assert row[2] == "Org1"
