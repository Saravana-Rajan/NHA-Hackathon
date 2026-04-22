"""Tests for pipeline.ingest."""
from pathlib import Path
from pipeline.ingest import (
    iter_case_files,
    discover_cases,
    infer_package_code,
    SUPPORTED_EXTENSIONS,
)


def test_iter_case_files_returns_supported(sample_mg006a_case: Path):
    files = iter_case_files(sample_mg006a_case)
    assert len(files) >= 1
    for f in files:
        assert f.suffix.lower() in SUPPORTED_EXTENSIONS


def test_iter_case_files_is_sorted(sample_mg006a_case: Path):
    files = iter_case_files(sample_mg006a_case)
    names = [f.name for f in files]
    assert names == sorted(names)


def test_discover_cases_finds_all_four_packages(claims_root: Path, all_package_codes):
    cases = discover_cases(claims_root)
    assert len(cases) > 0
    package_codes_seen = {pkg for (_, pkg) in cases.values()}
    for pkg in all_package_codes:
        assert pkg in package_codes_seen, f"Missing package {pkg}"


def test_infer_package_code_from_parent_dir(claims_root: Path):
    case_dir = claims_root / "MG006A" / "CMJAY_TR_CMJAY_2025_R3_1022010623"
    assert infer_package_code(case_dir) == "MG006A"


from pipeline.ingest import extract_pages


def test_extract_pages_from_pdf(sample_mg006a_case, tmp_path):
    pdf = next(f for f in sample_mg006a_case.iterdir() if f.suffix == ".pdf")
    pages = extract_pages(pdf, case_id=sample_mg006a_case.name, out_dir=tmp_path)
    assert len(pages) >= 1
    for p in pages:
        assert p.page_number >= 1
        assert p.file_name == pdf.name
        assert p.image_path
        assert (tmp_path / p.image_path).exists() or p.image_path.startswith(str(tmp_path))


def test_extract_pages_from_image(sample_mg006a_case, tmp_path):
    img = next((f for f in sample_mg006a_case.iterdir()
                if f.suffix.lower() in {".jpg", ".jpeg", ".png"}), None)
    if img is None:
        import pytest
        pytest.skip("No image file in sample case")
    pages = extract_pages(img, case_id=sample_mg006a_case.name, out_dir=tmp_path)
    assert len(pages) == 1
    assert pages[0].page_number == 1
