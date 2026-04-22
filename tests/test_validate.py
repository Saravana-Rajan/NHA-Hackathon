"""Tests for pipeline.validate."""
from pipeline.validate import validate_output_rows, validate_row_types
from pipeline.assemble import initialize_output_row


def test_valid_rows_pass():
    rows = [initialize_output_row("MG064A", "C1", "d.pdf", i) for i in (1, 2)]
    ok, issues = validate_output_rows("MG064A", rows)
    assert ok
    assert issues == []


def test_missing_key_fails():
    row = initialize_output_row("MG064A", "C1", "d.pdf", 1)
    del row["cbc_hb_report"]
    ok, issues = validate_output_rows("MG064A", [row])
    assert not ok
    assert any("cbc_hb_report" in x or "mismatch" in x.lower() for x in issues)


def test_wrong_key_order_fails():
    row = initialize_output_row("MG064A", "C1", "d.pdf", 1)
    # reverse the order
    reversed_row = {k: row[k] for k in reversed(list(row))}
    ok, issues = validate_output_rows("MG064A", [reversed_row])
    assert not ok


def test_unknown_package_fails():
    ok, issues = validate_output_rows("UNKNOWN", [{"case_id": "C1"}])
    assert not ok
    assert any("unknown package" in x.lower() for x in issues)


def test_binary_flag_out_of_range_fails():
    row = initialize_output_row("MG064A", "C1", "d.pdf", 1)
    row["clinical_notes"] = 2
    ok, issues = validate_row_types("MG064A", row)
    assert not ok
    assert any("clinical_notes" in x for x in issues)


def test_date_field_wrong_type_fails():
    row = initialize_output_row("MG006A", "C1", "d.pdf", 1)
    row["pre_date"] = 5  # should be str or None
    ok, issues = validate_row_types("MG006A", row)
    assert not ok
