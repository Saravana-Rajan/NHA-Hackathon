"""OCR layer. EasyOCR primary (pure-Python), Tesseract fallback, NOOP for testing."""
from __future__ import annotations
from enum import Enum
from pathlib import Path
from typing import Optional

from pipeline.models import PageOCR, OCRLine


class OCRBackend(str, Enum):
    EASYOCR = "easyocr"
    PADDLE = "paddle"
    TESSERACT = "tesseract"
    PYMUPDF = "pymupdf"
    NOOP = "noop"  # for testing; returns empty text


_EASY_INSTANCE = None


def _get_easy():
    """Lazily initialize EasyOCR reader once (downloads model weights on first use).

    Auto-detects CUDA via torch so the sandbox GPU is used when available.
    """
    global _EASY_INSTANCE
    if _EASY_INSTANCE is None:
        import easyocr
        try:
            import torch
            gpu_enabled = bool(torch.cuda.is_available())
        except Exception:
            gpu_enabled = False
        _EASY_INSTANCE = easyocr.Reader(["en"], gpu=gpu_enabled, verbose=False)
    return _EASY_INSTANCE


def _ocr_easyocr(image_path: str) -> PageOCR:
    reader = _get_easy()
    results = reader.readtext(image_path, detail=1)
    lines = []
    text_parts = []
    for bbox_pts, text, conf in results:
        if not text:
            continue
        xs = [int(pt[0]) for pt in bbox_pts]
        ys = [int(pt[1]) for pt in bbox_pts]
        bbox = [min(xs), min(ys), max(xs), max(ys)]
        lines.append(OCRLine(text=text, bbox=bbox, confidence=float(conf)))
        text_parts.append(text)
    return PageOCR(text="\n".join(text_parts), lines=lines)


def _get_paddle():
    """Lazily initialize PaddleOCR once."""
    from paddleocr import PaddleOCR
    return PaddleOCR(use_angle_cls=True, lang="en", show_log=False)


_PADDLE_INSTANCE = None


def _ocr_paddle(image_path: str) -> PageOCR:
    global _PADDLE_INSTANCE
    if _PADDLE_INSTANCE is None:
        _PADDLE_INSTANCE = _get_paddle()
    result = _PADDLE_INSTANCE.ocr(image_path, cls=True)
    lines = []
    text_parts = []
    if result and result[0]:
        for detection in result[0]:
            bbox_pts = detection[0]
            text, conf = detection[1]
            if not text:
                continue
            xs = [int(pt[0]) for pt in bbox_pts]
            ys = [int(pt[1]) for pt in bbox_pts]
            bbox = [min(xs), min(ys), max(xs), max(ys)]
            lines.append(OCRLine(text=text, bbox=bbox, confidence=float(conf)))
            text_parts.append(text)
    return PageOCR(text="\n".join(text_parts), lines=lines)


def _ocr_tesseract(image_path: str) -> PageOCR:
    import pytesseract
    from PIL import Image
    img = Image.open(image_path)
    text = pytesseract.image_to_string(img)
    lines = [OCRLine(text=line.strip()) for line in text.splitlines() if line.strip()]
    return PageOCR(text=text, lines=lines)


def run_ocr(
    image_path: str,
    backend: OCRBackend = OCRBackend.EASYOCR,
) -> PageOCR:
    """Run OCR on a single image. Returns empty result on any failure."""
    if not Path(image_path).exists():
        return PageOCR(text="", lines=[])
    if backend == OCRBackend.NOOP:
        return PageOCR(text="", lines=[])
    try:
        if backend == OCRBackend.EASYOCR:
            return _ocr_easyocr(image_path)
        if backend == OCRBackend.PADDLE:
            return _ocr_paddle(image_path)
        if backend == OCRBackend.TESSERACT:
            return _ocr_tesseract(image_path)
    except Exception:
        return PageOCR(text="", lines=[])
    return PageOCR(text="", lines=[])


def extract_text_from_pdf_page(pdf_path: str, page_number: int) -> PageOCR:
    """Extract embedded text from a PDF page using PyMuPDF (no OCR).

    Returns empty PageOCR for scanned/image-only PDFs — callers should
    fall back to run_ocr() in that case.
    """
    if not pdf_path:
        return PageOCR(text="", lines=[])
    p = Path(pdf_path)
    if not p.exists() or p.suffix.lower() != ".pdf":
        return PageOCR(text="", lines=[])
    try:
        import fitz  # pymupdf
    except Exception:
        return PageOCR(text="", lines=[])
    try:
        with fitz.open(pdf_path) as doc:
            idx = page_number - 1
            if idx < 0 or idx >= doc.page_count:
                return PageOCR(text="", lines=[])
            page = doc.load_page(idx)
            raw_text = page.get_text("text") or ""
            lines: list[OCRLine] = []
            try:
                blocks = page.get_text("blocks") or []
            except Exception:
                blocks = []
            for b in blocks:
                if len(b) < 5:
                    continue
                x0, y0, x1, y1, btext = b[0], b[1], b[2], b[3], b[4]
                if not btext:
                    continue
                for ln in str(btext).splitlines():
                    ln = ln.strip()
                    if ln:
                        lines.append(OCRLine(
                            text=ln,
                            bbox=[int(x0), int(y0), int(x1), int(y1)],
                            confidence=1.0,
                        ))
            if not lines and raw_text.strip():
                for ln in raw_text.splitlines():
                    ln = ln.strip()
                    if ln:
                        lines.append(OCRLine(text=ln, confidence=1.0))
            return PageOCR(text=raw_text, lines=lines)
    except Exception:
        return PageOCR(text="", lines=[])
