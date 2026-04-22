"""Ingest claim case files.

Discovers case folders, walks their supported files, rasterizes
PDFs to page-level images.
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Tuple

from pipeline.models import Page
from pipeline.schemas import PACKAGE_CODES

SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


def iter_case_files(case_dir: Path) -> List[Path]:
    """Return sorted list of supported files in a case folder (non-recursive)."""
    if not case_dir.exists() or not case_dir.is_dir():
        return []
    files = [
        p for p in case_dir.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    return sorted(files, key=lambda p: p.name)


def infer_package_code(case_dir: Path) -> str:
    """The case folder's parent directory name is the package code."""
    return case_dir.parent.name


def discover_cases(data_root: Path) -> Dict[str, Tuple[List[Path], str]]:
    """Discover all case folders beneath `data_root`.

    Expected layout:
        data_root / <package_code> / <case_id> / <files...>

    Returns a dict of case_id -> (sorted file list, package_code).
    Cases with unknown package codes are skipped.
    """
    cases: Dict[str, Tuple[List[Path], str]] = {}
    if not data_root.exists():
        return cases
    for package_dir in sorted(data_root.iterdir()):
        if not package_dir.is_dir():
            continue
        pkg = package_dir.name
        if pkg not in PACKAGE_CODES:
            continue
        for case_dir in sorted(package_dir.iterdir()):
            if not case_dir.is_dir():
                continue
            files = iter_case_files(case_dir)
            if not files:
                continue
            cases[case_dir.name] = (files, pkg)
    return cases


# ---------------------------------------------------------------------------
# Page extraction
# ---------------------------------------------------------------------------

def extract_pages(
    file_path: Path,
    case_id: str,
    out_dir: Path,
    dpi: int = 200,
) -> List[Page]:
    """Rasterize a PDF to per-page PNGs or wrap an image as a single page.

    Writes images to `out_dir` and returns Page records pointing at them.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = file_path.suffix.lower()
    stem = file_path.stem

    if suffix == ".pdf":
        return _extract_pdf_pages(file_path, case_id, out_dir, stem, dpi)
    if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}:
        # Copy-through: record the original image path with page_number=1
        image_path = str(file_path.resolve())
        return [Page(
            case_id=case_id,
            file_name=file_path.name,
            page_number=1,
            image_path=image_path,
            source_pdf_path=None,
            source_page_index=None,
        )]
    return []


def _extract_pdf_pages(
    pdf_path: Path,
    case_id: str,
    out_dir: Path,
    stem: str,
    dpi: int,
) -> List[Page]:
    """Rasterize PDF pages using PyMuPDF (fitz)."""
    import fitz  # pymupdf

    pages: List[Page] = []
    pdf_abs = str(pdf_path.resolve())
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc, start=1):
            zoom = dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            out_path = out_dir / f"{stem}__p{i:03d}.png"
            pix.save(out_path)
            pages.append(Page(
                case_id=case_id,
                file_name=pdf_path.name,
                page_number=i,
                image_path=str(out_path.resolve()),
                source_pdf_path=pdf_abs,
                # fitz is 0-indexed internally; store the 0-based index here.
                source_page_index=i - 1,
            ))
    return pages
