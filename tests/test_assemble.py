"""Tests for pipeline.assemble."""
from pipeline.assemble import (
    initialize_output_row,
    populate_row_for_package,
    infer_document_rank,
)
from pipeline.schemas import PACKAGE_SCHEMAS, EXTRA_DOCUMENT_RANK
from pipeline.models import PageResult, Evidence, PageOCR
from rules.common import positive_rule


def test_initialize_output_row_has_exact_keys_mg064a():
    row = initialize_output_row("MG064A", "C1", "doc.pdf", 1)
    assert list(row.keys()) == PACKAGE_SCHEMAS["MG064A"]
    assert row["case_id"] == "C1"
    assert row["link"] == "doc.pdf"
    assert row["procedure_code"] == "MG064A"
    assert row["page_number"] == 1


def test_initialize_output_row_has_exact_keys_all_packages():
    for pkg in PACKAGE_SCHEMAS:
        row = initialize_output_row(pkg, "X", "y", 2)
        assert list(row.keys()) == PACKAGE_SCHEMAS[pkg]


def test_initialize_output_row_dates_are_none_mg006a():
    row = initialize_output_row("MG006A", "C1", "d.pdf", 1)
    assert row["pre_date"] is None
    assert row["post_date"] is None


def test_initialize_output_row_dates_are_none_sb039a():
    row = initialize_output_row("SB039A", "C1", "d.pdf", 1)
    assert row["doa"] is None
    assert row["dod"] is None


def test_initialize_output_row_binary_flags_default_zero():
    row = initialize_output_row("MG064A", "C1", "d.pdf", 1)
    for k in ("clinical_notes", "cbc_hb_report", "severe_anemia", "extra_document"):
        assert row[k] == 0


def test_populate_row_for_extra_document_assigns_rank_99():
    pr = PageResult(case_id="C1", file_name="d.pdf", page_number=1)
    pr.doc_type = "unknown"
    row = populate_row_for_package("MG064A", pr)
    assert row["extra_document"] == 1
    assert row["document_rank"] == EXTRA_DOCUMENT_RANK
    assert list(row.keys()) == PACKAGE_SCHEMAS["MG064A"]


def test_infer_rank_for_known_doctype():
    assert infer_document_rank("MG064A", "clinical_notes") == 1
    assert infer_document_rank("MG064A", "discharge_summary") == 5
    assert infer_document_rank("SB039A", "implant_invoice") == 5


def test_infer_rank_for_unknown_doctype_returns_99():
    assert infer_document_rank("MG064A", "unknown") == EXTRA_DOCUMENT_RANK


def test_populate_row_applies_rule_results():
    pr = PageResult(case_id="C1", file_name="d.pdf", page_number=1,
                    ocr=PageOCR(text="Haemoglobin 6.1 g/dL", lines=[]),
                    doc_type="cbc_hb_report")
    results = [positive_rule("cbc_hb_report", [Evidence(1, "Haemoglobin 6.1", "x")])]
    row = populate_row_for_package("MG064A", pr, rule_results=results)
    assert row["cbc_hb_report"] == 1
    assert row["extra_document"] == 0
    assert row["document_rank"] != EXTRA_DOCUMENT_RANK


def test_populate_row_applies_entity_dates_sb039a():
    pr = PageResult(case_id="C1", file_name="d.pdf", page_number=1,
                    doc_type="discharge_summary")
    pr.entities["doa"] = "12-03-2026"
    pr.entities["dod"] = "18-03-2026"
    row = populate_row_for_package("SB039A", pr, rule_results=[])
    assert row["doa"] == "12-03-2026"
    assert row["dod"] == "18-03-2026"
