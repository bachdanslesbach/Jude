from pathlib import Path

import pytest

from jude.adapters.pdf import PdfAdapter

pymupdf = pytest.importorskip("pymupdf")


def _make_text_pdf(path: Path, pages: list[str], *, author: str = "") -> None:
    doc = pymupdf.open()
    for content in pages:
        page = doc.new_page()
        page.insert_text((72, 72), content, fontsize=12)
    if author:
        doc.set_metadata({"author": author})
    doc.save(str(path))
    doc.close()


def _make_blank_pdf(path: Path, n_pages: int = 1) -> None:
    doc = pymupdf.open()
    for _ in range(n_pages):
        doc.new_page()
    doc.save(str(path))
    doc.close()


def test_pdf_extracts_text_per_page(tmp_path: Path):
    src = tmp_path / "in.pdf"
    _make_text_pdf(src, ["First page text.", "Second page text."])
    extraction = PdfAdapter.read(src)
    assert extraction.is_text_pdf is True
    assert len(extraction.pages) == 2
    assert "First page text" in extraction.pages[0]
    assert "Second page text" in extraction.pages[1]
    assert "--- Page 1 ---" in extraction.text
    assert "--- Page 2 ---" in extraction.text


def test_pdf_warns_on_image_only_document(tmp_path: Path):
    src = tmp_path / "blank.pdf"
    _make_blank_pdf(src, n_pages=2)
    extraction = PdfAdapter.read(src)
    assert extraction.is_text_pdf is False
    assert any("image-only" in w for w in extraction.warnings)


def test_pdf_warns_on_metadata(tmp_path: Path):
    src = tmp_path / "in.pdf"
    _make_text_pdf(src, ["Hello"], author="Jane Doe")
    extraction = PdfAdapter.read(src)
    assert extraction.metadata.get("author") == "Jane Doe"
    assert any("metadata" in w.lower() for w in extraction.warnings)
