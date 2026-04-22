"""Tests for MG064A (Severe Anemia) rule engine."""
from pipeline.models import PageResult, PageOCR, Evidence
from rules.mg064a_anemia import evaluate_page_mg064a


def _pr(doc_type, text, page_number=1, file_name="d.pdf"):
    return PageResult(
        case_id="C1",
        file_name=file_name,
        page_number=page_number,
        ocr=PageOCR(text=text, lines=[]),
        doc_type=doc_type,
        doc_type_confidence=0.9,
    )


def test_severe_anemia_fires_on_hb_below_7():
    pr = _pr("cbc_hb_report", "Haemoglobin: 6.2 g/dL\nMCV 82")
    results = evaluate_page_mg064a(pr)
    names = {r.field_name: r for r in results}
    assert names["cbc_hb_report"].value == 1
    assert names["severe_anemia"].value == 1
    assert names["severe_anemia"].evidence, "must carry Hb-value evidence"


def test_no_severe_anemia_when_hb_normal():
    pr = _pr("cbc_hb_report", "Haemoglobin: 13.4 g/dL\nMCV 88")
    results = evaluate_page_mg064a(pr)
    names = {r.field_name: r.value for r in results}
    assert names["cbc_hb_report"] == 1
    assert names["severe_anemia"] == 0


def test_common_signs_pallor():
    pr = _pr("clinical_notes", "Patient c/o weakness and pallor. Examination reveals fatigue.")
    results = evaluate_page_mg064a(pr)
    names = {r.field_name: r for r in results}
    assert names["clinical_notes"].value == 1
    assert names["common_signs"].value == 1
    assert names["common_signs"].evidence


def test_life_threatening_signs_shock():
    pr = _pr("clinical_notes", "Patient presents with shock, cardiac failure noted.")
    results = evaluate_page_mg064a(pr)
    names = {r.field_name: r.value for r in results}
    assert names["life_threatening_signs"] == 1


def test_discharge_summary_flag_from_doctype():
    pr = _pr("discharge_summary", "Discharge summary. Patient discharged in stable state.")
    results = evaluate_page_mg064a(pr)
    names = {r.field_name: r.value for r in results}
    assert names["discharge_summary"] == 1


def test_unknown_doctype_produces_extra_document():
    pr = _pr("unknown", "Random uninformative text with no clinical keywords.")
    results = evaluate_page_mg064a(pr)
    names = {r.field_name: r.value for r in results}
    # all presence flags must be zero
    for field in ("clinical_notes", "cbc_hb_report", "indoor_case",
                  "treatment_details", "post_hb_report", "discharge_summary"):
        assert names[field] == 0, field
