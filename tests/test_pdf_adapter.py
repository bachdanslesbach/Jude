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
    # Pages are joined with a blank-line separator only — no visible
    # "--- Page N ---" marker, since spaCy was redacting the markers.
    assert "First page text" in extraction.text
    assert "Second page text" in extraction.text
    assert "Page" not in extraction.text  # no visible marker


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


def test_image_only_pdf_without_ocr_returns_warning(tmp_path: Path):
    src = tmp_path / "blank.pdf"
    _make_blank_pdf(src)
    extraction = PdfAdapter.read(src, enable_ocr=False)
    assert extraction.is_text_pdf is False
    assert any("ocr" in w.lower() for w in extraction.warnings)


def test_ocr_raises_when_tesseract_missing(tmp_path: Path, monkeypatch):
    from jude.adapters import pdf as pdf_module
    from jude.adapters.pdf import OCRUnavailableError

    monkeypatch.setattr(pdf_module.shutil, "which", lambda _: None)
    src = tmp_path / "blank.pdf"
    _make_blank_pdf(src)
    with pytest.raises(OCRUnavailableError, match="tesseract"):
        PdfAdapter.read(src, enable_ocr=True)


# ---------- native PDF write-back (v0.4.10) ----------


def test_write_redacted_replaces_text_across_all_pages(tmp_path: Path):
    """Each occurrence of any surface form across every page is physically
    redacted in the output PDF — and re-extraction of the redacted PDF no
    longer contains the real names but does contain their pseudonyms."""

    src = tmp_path / "src.pdf"
    dst = tmp_path / "out.pdf"
    _make_text_pdf(src, [
        "Amazon and Microsoft are the parties.",
        "On the second page Microsoft sues Amazon.",
    ])
    PdfAdapter.write_redacted(
        src, dst, replacements={"Amazon": "Org1", "Microsoft": "Org2"}
    )
    assert dst.exists()
    re_read = PdfAdapter.read(dst).text
    assert "Amazon" not in re_read
    assert "Microsoft" not in re_read
    assert "Org1" in re_read
    assert "Org2" in re_read


def test_write_redacted_handles_multiple_occurrences_on_same_page(tmp_path: Path):
    src = tmp_path / "src.pdf"
    dst = tmp_path / "out.pdf"
    _make_text_pdf(src, ["Amazon Amazon Amazon Microsoft Amazon."])
    PdfAdapter.write_redacted(
        src, dst, replacements={"Amazon": "Org1", "Microsoft": "Org2"}
    )
    text = PdfAdapter.read(dst).text
    assert "Amazon" not in text
    # All four occurrences became Org1.
    assert text.count("Org1") == 4


def test_write_redacted_processes_longer_keys_first(tmp_path: Path):
    """If both 'Amazon' and 'Amazon.com Inc.' map to the same entity, the
    longer key must be applied first or partial-name shadowing produces
    'Org1.com Inc.'."""

    src = tmp_path / "src.pdf"
    dst = tmp_path / "out.pdf"
    _make_text_pdf(src, ["Amazon.com Inc. and standalone Amazon."])
    PdfAdapter.write_redacted(
        src,
        dst,
        replacements={"Amazon": "Org1", "Amazon.com Inc.": "Org1"},
    )
    text = PdfAdapter.read(dst).text
    assert "Amazon" not in text
    assert ".com Inc." not in text  # the longer form was redacted whole


def test_write_redacted_clears_metadata_by_default(tmp_path: Path):
    src = tmp_path / "src.pdf"
    dst = tmp_path / "out.pdf"
    _make_text_pdf(src, ["Hello"], author="Jane Doe")
    PdfAdapter.write_redacted(src, dst, replacements={})
    re_read = PdfAdapter.read(dst)
    assert (re_read.metadata.get("author") or "") == ""


def test_write_redacted_rejects_image_only_pdf(tmp_path: Path):
    """v0 native write-back works only on text PDFs. For image-only inputs
    the user should run OCR first and get a text export, or accept that
    the redacted output is .txt."""

    src = tmp_path / "blank.pdf"
    dst = tmp_path / "out.pdf"
    _make_blank_pdf(src)
    with pytest.raises(ValueError, match=r"image-only"):
        PdfAdapter.write_redacted(src, dst, replacements={})


@pytest.mark.skipif(
    __import__("shutil").which("tesseract") is None,
    reason="tesseract not installed on this machine",
)
def test_ocr_extracts_text_from_image_pdf(tmp_path: Path):
    """End-to-end OCR: render text as an image, embed it in a PDF, OCR it back."""

    from PIL import Image, ImageDraw, ImageFont
    import img2pdf

    img_path = tmp_path / "page.png"
    pdf_path = tmp_path / "scanned.pdf"
    img = Image.new("RGB", (1200, 600), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
    except OSError:
        font = ImageFont.load_default()
    draw.text((50, 100), "Amazon competes with Microsoft.", fill="black", font=font)
    img.save(img_path)
    with open(pdf_path, "wb") as f:
        f.write(img2pdf.convert(str(img_path)))

    pre = PdfAdapter.read(pdf_path, enable_ocr=False)
    assert pre.is_text_pdf is False

    post = PdfAdapter.read(pdf_path, enable_ocr=True)
    assert post.is_text_pdf is True
    text_lower = post.text.lower()
    assert "amazon" in text_lower
    assert "microsoft" in text_lower
    assert any("ocr was applied" in w.lower() for w in post.warnings)
