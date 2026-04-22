"""Tests for validate F1 + provenance coverage functions."""
from pipeline.validate import compute_field_level_f1, check_provenance_coverage


def _mg_row(page, **kwargs):
    base = {
        "case_id": "C1", "link": "d.pdf", "procedure_code": "MG064A",
        "page_number": page,
        "clinical_notes": 0, "cbc_hb_report": 0, "indoor_case": 0,
        "treatment_details": 0, "post_hb_report": 0, "discharge_summary": 0,
        "severe_anemia": 0, "common_signs": 0, "significant_signs": 0,
        "life_threatening_signs": 0, "extra_document": 0, "document_rank": 0,
    }
    base.update(kwargs)
    return base


def test_f1_perfect_when_pred_equals_gold():
    gold = [_mg_row(1, severe_anemia=1, cbc_hb_report=1),
            _mg_row(2, clinical_notes=1)]
    pred = [_mg_row(1, severe_anemia=1, cbc_hb_report=1),
            _mg_row(2, clinical_notes=1)]
    m = compute_field_level_f1("MG064A", pred, gold)
    assert m["severe_anemia"]["f1"] == 1.0
    assert m["cbc_hb_report"]["f1"] == 1.0
    assert m["clinical_notes"]["f1"] == 1.0


def test_f1_zero_when_all_missed():
    gold = [_mg_row(1, severe_anemia=1)]
    pred = [_mg_row(1, severe_anemia=0)]
    m = compute_field_level_f1("MG064A", pred, gold)
    assert m["severe_anemia"]["f1"] == 0.0
    assert m["severe_anemia"]["fn"] == 1


def test_f1_mixed():
    gold = [_mg_row(1, severe_anemia=1), _mg_row(2, severe_anemia=1)]
    pred = [_mg_row(1, severe_anemia=1), _mg_row(2, severe_anemia=0)]
    m = compute_field_level_f1("MG064A", pred, gold)
    # 1 TP, 0 FP, 1 FN => prec=1, rec=0.5 => f1=0.6667
    assert m["severe_anemia"]["tp"] == 1
    assert m["severe_anemia"]["fn"] == 1
    assert 0 < m["severe_anemia"]["f1"] < 1


def test_provenance_coverage_full():
    rows = [_mg_row(1, severe_anemia=1)]
    evp = {1: 2}  # 2 evidence entries for page 1
    ratio, missing = check_provenance_coverage("MG064A", rows, evp)
    assert ratio == 1.0
    assert missing == []


def test_provenance_coverage_missing():
    rows = [_mg_row(1, severe_anemia=1)]
    evp = {1: 0}
    ratio, missing = check_provenance_coverage("MG064A", rows, evp)
    assert ratio == 0.0
    assert "page=1" in missing


def test_provenance_no_positives_is_full_coverage():
    rows = [_mg_row(1)]  # no positives
    evp = {}
    ratio, missing = check_provenance_coverage("MG064A", rows, evp)
    assert ratio == 1.0
