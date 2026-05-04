from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

PARAGRAPH_SEP = "\n\n"
PAGE_MARKER = "\n\n--- Page {n} ---\n\n"


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
    """Read text from a native-text PDF.

    Limitations of v0:
      * Scanned (image-only) PDFs are detected and surfaced as a warning;
        no OCR is performed yet.
      * No write-back to PDF — the redacted output is plain text. The user
        can paste it into their LLM tool of choice.
    """

    @staticmethod
    def read(path: Path | str) -> PdfExtraction:
        import pymupdf

        doc = pymupdf.open(str(path))
        try:
            extraction = PdfExtraction()
            extraction.metadata = {
                k: v
                for k, v in (doc.metadata or {}).items()
                if v
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
                    "OCR is not yet supported in v0; convert with an OCR tool first "
                    "(e.g. ocrmypdf) or use a text-PDF version."
                )
            elif empty_pages > 0:
                extraction.warnings.append(
                    f"{empty_pages} of {len(extraction.pages)} pages contain no "
                    "extractable text — they may be scanned images and will be "
                    "skipped silently."
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
        return PdfAdapter.read(path).is_text_pdf
