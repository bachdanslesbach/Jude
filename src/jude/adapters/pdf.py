from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

PARAGRAPH_SEP = "\n\n"
PAGE_MARKER = "\n\n--- Page {n} ---\n\n"


class OCRUnavailableError(RuntimeError):
    """Raised when OCR is requested but the system binary is not installed."""


@dataclass
class PdfExtraction:
    """Flat text extracted from a PDF, plus warnings about risky content.

    `pages` preserves the page-level break structure; `text` is the joined
    string with `--- Page N ---` separators inserted so the user can
    cross-reference back to the original.
    """

    pages: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    is_text_pdf: bool = True
    warnings: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        if not self.pages:
            return ""
        parts: list[str] = []
        for i, page in enumerate(self.pages, 1):
            parts.append(PAGE_MARKER.format(n=i))
            parts.append(page)
        return "".join(parts).lstrip()


class PdfAdapter:
    """Read text from a PDF, optionally running OCR when the PDF has no text.

    Behavior:
      * Native-text PDFs: text is extracted directly.
      * Image-only PDFs with `enable_ocr=False`: a warning is surfaced and
        no text is returned. The caller can then re-call with OCR enabled.
      * Image-only PDFs with `enable_ocr=True`: `ocrmypdf` is run against
        the file in a temp directory to produce a searchable copy, which
        is then text-extracted normally.

    `ocrmypdf` requires the `tesseract` system binary (and language data).
    Install on macOS with `brew install tesseract tesseract-lang`. Without
    it, calls with `enable_ocr=True` raise `OCRUnavailableError`.
    """

    @staticmethod
    def read(
        path: Path | str,
        *,
        enable_ocr: bool = False,
        ocr_languages: tuple[str, ...] = ("eng", "fra"),
    ) -> PdfExtraction:
        extraction = PdfAdapter._extract(path)
        if extraction.is_text_pdf or not enable_ocr:
            return extraction

        # Image-only PDF and OCR is requested — run ocrmypdf and re-extract.
        ocr_pdf = _run_ocrmypdf(Path(path), ocr_languages)
        try:
            ocr_extraction = PdfAdapter._extract(ocr_pdf)
            ocr_extraction.warnings = extraction.warnings + [
                f"OCR was applied (languages: {'+'.join(ocr_languages)})."
            ]
            ocr_extraction.metadata = extraction.metadata
            return ocr_extraction
        finally:
            ocr_pdf.unlink(missing_ok=True)
            ocr_pdf.parent.rmdir() if ocr_pdf.parent.exists() else None

    @staticmethod
    def _extract(path: Path | str) -> PdfExtraction:
        import pymupdf

        doc = pymupdf.open(str(path))
        try:
            extraction = PdfExtraction()
            extraction.metadata = {
                k: v for k, v in (doc.metadata or {}).items() if v
            }

            empty_pages = 0
            for page in doc:
                text = page.get_text("text").strip()
                extraction.pages.append(text)
                if not text:
                    empty_pages += 1

            if empty_pages > 0 and empty_pages == len(extraction.pages):
                extraction.is_text_pdf = False
                extraction.warnings.append(
                    "PDF appears to be image-only (no extractable text). "
                    "Re-run with `enable_ocr=True` (or `--ocr` on the CLI) to "
                    "have Jude run ocrmypdf locally and extract text from a "
                    "searchable copy."
                )
            elif empty_pages > 0:
                extraction.warnings.append(
                    f"{empty_pages} of {len(extraction.pages)} pages contain no "
                    "extractable text — they may be scanned images. Re-run with "
                    "OCR enabled to capture them."
                )

            if any(extraction.metadata.values()):
                extraction.warnings.append(
                    "PDF metadata (author, title, producer, etc.) may contain "
                    "identifying information. The text-only export does not "
                    "include metadata, but the original PDF still does."
                )

            return extraction
        finally:
            doc.close()

    @staticmethod
    def is_text_pdf(path: Path | str) -> bool:
        return PdfAdapter._extract(path).is_text_pdf

    @staticmethod
    def write_redacted(
        source_path: Path | str,
        target_path: Path | str,
        replacements: dict[str, str],
        clear_metadata: bool = True,
    ) -> None:
        """Produce a true redacted PDF using PyMuPDF redact-annotations.

        Each occurrence of any key in `replacements` across every page is
        physically removed (not just covered) via `page.apply_redactions()`
        and its value is rendered in place.

        Limitations of v0:
          * Image-only PDFs raise ValueError. Run OCR first, or accept
            the .txt redacted output.
          * The replacement is rendered with the default Helvetica face
            at a small size that fits the original rect; complex layout
            preservation isn't attempted.
        """

        import pymupdf

        doc = pymupdf.open(str(source_path))
        try:
            if not _has_text(doc):
                raise ValueError(
                    "Cannot redact an image-only PDF natively. Run OCR "
                    "first to add a text layer, or accept the .txt "
                    "redacted output."
                )

            # Longer keys first to avoid partial-name shadowing — e.g. so
            # "Amazon.com Inc." gets fully redacted before a "Amazon" pass
            # would otherwise leave a ".com Inc." dangling.
            ordered = sorted(replacements.items(), key=lambda kv: -len(kv[0]))

            for page in doc:
                for surface, pseudonym in ordered:
                    if not surface:
                        continue
                    rects = page.search_for(surface)
                    if not rects:
                        continue
                    for rect in rects:
                        page.add_redact_annot(
                            rect,
                            text=pseudonym,
                            fontname="helv",
                            fontsize=9,
                        )
                    # Apply per-key so later (shorter) keys search the
                    # already-redacted page and don't double-hit content
                    # that was just removed.
                    page.apply_redactions()

            if clear_metadata:
                doc.set_metadata({})

            doc.save(str(target_path))
        finally:
            doc.close()


def _has_text(doc) -> bool:  # type: ignore[no-untyped-def]
    for page in doc:
        if page.get_text("text").strip():
            return True
    return False


def _run_ocrmypdf(input_pdf: Path, languages: tuple[str, ...]) -> Path:
    """Run `ocrmypdf` on `input_pdf` to produce a searchable PDF.

    Returns the path of the OCR output (caller is responsible for cleanup).
    Raises `OCRUnavailableError` if the system tesseract is missing.
    """

    if shutil.which("tesseract") is None:
        raise OCRUnavailableError(
            "OCR was requested but the `tesseract` system binary is not "
            "installed. On macOS:\n"
            "  brew install tesseract tesseract-lang\n"
            "On Debian/Ubuntu:\n"
            "  apt install tesseract-ocr tesseract-ocr-eng tesseract-ocr-fra"
        )

    tmpdir = Path(tempfile.mkdtemp(prefix="jude_ocr_"))
    output = tmpdir / "ocr.pdf"
    lang_arg = "+".join(languages)
    cmd = [
        "ocrmypdf",
        "--language", lang_arg,
        "--skip-text",
        "--quiet",
        "--output-type", "pdf",
        str(input_pdf),
        str(output),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as e:
        raise OCRUnavailableError(
            "`ocrmypdf` was not found on PATH. Install it with "
            "`pip install ocrmypdf` (and ensure tesseract is installed)."
        ) from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"ocrmypdf failed (exit {e.returncode}):\n{e.stderr}"
        ) from e
    return output
