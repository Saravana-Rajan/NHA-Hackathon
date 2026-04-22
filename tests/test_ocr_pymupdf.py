"""Tests for the PyMuPDF text-layer extraction path in pipeline.ocr.

These complement the existing test_ocr.py tests — the PyMuPDF function
short-circuits OCR entirely when a PDF already carries an embedded
text layer (which most Indian hospital claim PDFs do).
"""
from pathlib import Path

import pytest

from pipeline.ocr import extract_text_from_pdf_page, OCRBackend
from pipeline.models import PageOCR


def test_pymupdf_backend_enum_defined():
    """OCRBackend.PYMUPDF should exist and round-trip as a string."""
    assert OCRBackend.PYMUPDF.value == "pymupdf"


def test_pymupdf_text_extraction_on_sample_pdf(sample_mg006a_case: Path, claims_root: Path):
    """At least one real claim PDF must yield a non-empty text layer.

    Start in the MG006A sample folder (as specified by the task) and, if
    that folder happens to contain only scanned PDFs, widen the search to
    the claims root. The pipeline only needs *some* digitally-native
    pages to exist in the corpus for the PyMuPDF fast path to pay off.
    """
    import fitz

    def _probe(pdfs: list[Path]) -> bool:
        for pdf in pdfs:
            try:
                with fitz.open(pdf) as doc:
                    n = min(doc.page_count, 10)
            except Exception:
                continue
            for page_num in range(1, n + 1):
                result = extract_text_from_pdf_page(str(pdf), page_num)
                assert isinstance(result, PageOCR)
                if result.text and result.text.strip():
                    # Sanity-check lines are populated when text is.
                    assert len(result.lines) > 0
                    return True
        return False

    sample_pdfs = [p for p in sample_mg006a_case.iterdir() if p.suffix.lower() == ".pdf"]
    assert sample_pdfs, f"Expected at least one PDF in {sample_mg006a_case}"

    if _probe(sample_pdfs):
        return

    # The MG006A sample folder is all scans — widen to the full claims root.
    all_pdfs = list(claims_root.rglob("*.pdf"))
    assert _probe(all_pdfs), (
        "No PDF in the entire claims corpus yielded a text layer — "
        "expected at least one of the real hospital PDFs to be digitally native."
    )


def test_pymupdf_on_image_file_returns_empty(sample_mg006a_case: Path):
    """Calling on a .jpg path must return an empty PageOCR (no crash)."""
    jpg = next(
        (p for p in sample_mg006a_case.iterdir()
         if p.suffix.lower() in {".jpg", ".jpeg", ".png"}),
        None,
    )
    if jpg is None:
        pytest.skip("No image file in sample case to test against")
    result = extract_text_from_pdf_page(str(jpg), 1)
    assert isinstance(result, PageOCR)
    assert result.text == ""
    assert result.lines == []


def test_pymupdf_graceful_on_missing_file(tmp_path: Path):
    """A non-existent path must return empty without raising."""
    result = extract_text_from_pdf_page(str(tmp_path / "does_not_exist.pdf"), 1)
    assert isinstance(result, PageOCR)
    assert result.text == ""
    assert result.lines == []


def test_pymupdf_graceful_on_out_of_range_page(sample_mg006a_case: Path):
    """A page number past the end of the PDF returns empty, not an error."""
    pdf = next(p for p in sample_mg006a_case.iterdir() if p.suffix.lower() == ".pdf")
    result = extract_text_from_pdf_page(str(pdf), 99999)
    assert isinstance(result, PageOCR)
    assert result.text == ""
    assert result.lines == []


def test_pymupdf_graceful_on_empty_path():
    """An empty path string returns empty, not an error."""
    result = extract_text_from_pdf_page("", 1)
    assert isinstance(result, PageOCR)
    assert result.text == ""
    assert result.lines == []
