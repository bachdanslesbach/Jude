"""XLSX adapter — read flat text and write a redacted copy.

For competition / antitrust work, spreadsheets are common (market-share
grids, transaction lists, pricing data). This adapter exposes the same
shape as the DOCX adapter:

    extraction = XlsxAdapter.read(path)            # → flat text
    XlsxAdapter.write_redacted(src, dst, mapping)  # → preserves cells

`write_redacted` uses an explicit `{real -> pseudonym}` replacement map
rather than re-running detection internally, so the caller decides what
to substitute (matching whatever entities exist in the per-matter
store). This keeps the adapter dumb: it knows about cells, not about
NER.

Limitations of v0:
  * Formulas: the cached value is read; the formula itself is not
    redacted, so the output workbook keeps the same formulas. If a
    formula references another cell that contains a redactable name,
    the user should treat the workbook as advisory and inspect it.
  * Charts and images embedded in cells are passed through unchanged.
  * Cell formatting (fonts, fills, borders) is preserved by openpyxl
    automatically when we mutate `cell.value` rather than rebuilding.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

PARAGRAPH_SEP = "\n\n"
_SHEET_MARKER = "\n\n--- Sheet: {name} ---\n\n"


@dataclass
class XlsxExtraction:
    """Flat text extracted from an XLSX, plus warnings."""

    sheets: list[tuple[str, list[list[str]]]] = field(default_factory=list)
    core_properties: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        if not self.sheets:
            return ""
        parts: list[str] = []
        for name, rows in self.sheets:
            parts.append(_SHEET_MARKER.format(name=name))
            for row in rows:
                if any(cell.strip() for cell in row):
                    parts.append("\t".join(row))
                    parts.append("\n")
        return "".join(parts).strip()


class XlsxAdapter:
    """Read text from a .xlsx file and write back a redacted copy."""

    @staticmethod
    def read(path: Path | str) -> XlsxExtraction:
        import openpyxl

        wb = openpyxl.load_workbook(str(path), data_only=True)
        out = XlsxExtraction()
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows: list[list[str]] = []
            for row in ws.iter_rows(values_only=True):
                rows.append([_to_text(cell) for cell in row])
            out.sheets.append((sheet_name, rows))

        props = wb.properties
        out.core_properties = {
            "creator": props.creator or "",
            "lastModifiedBy": props.lastModifiedBy or "",
            "title": props.title or "",
            "subject": props.subject or "",
            "description": props.description or "",
        }
        if any(out.core_properties.values()):
            out.warnings.append(
                "Workbook properties (creator, lastModifiedBy, etc.) may "
                "contain identifying metadata. Consider clearing them."
            )
        return out

    @staticmethod
    def write_redacted(
        source_path: Path | str,
        target_path: Path | str,
        replacements: dict[str, str],
        clear_metadata: bool = True,
    ) -> None:
        """Apply `{real -> pseudonym}` cell-by-cell across every sheet.

        Only string-valued cells are touched. Numeric cells pass through.
        Replacements are case-sensitive; longer keys are applied before
        shorter ones to avoid partial-name shadowing (e.g. "Amazon.com"
        before "Amazon").
        """

        import openpyxl

        wb = openpyxl.load_workbook(str(source_path))

        ordered = sorted(replacements.items(), key=lambda kv: -len(kv[0]))
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            for row in ws.iter_rows():
                for cell in row:
                    val = cell.value
                    if not isinstance(val, str):
                        continue
                    new = val
                    for src, pseudo in ordered:
                        if src and src in new:
                            new = new.replace(src, pseudo)
                    if new != val:
                        cell.value = new

        if clear_metadata:
            props = wb.properties
            props.creator = ""
            props.lastModifiedBy = ""
            props.title = ""
            props.subject = ""
            props.description = ""

        wb.save(str(target_path))


def _to_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        # Avoid trailing ".0" for whole-number floats coming from Excel.
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)
    return str(value)
