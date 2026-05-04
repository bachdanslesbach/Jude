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
