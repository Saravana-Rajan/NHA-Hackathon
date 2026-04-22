"""Tests for SB039A (Total Knee Replacement)."""
from pipeline.models import PageResult, PageOCR
from rules.sb039a_tkr import evaluate_page_sb039a


def _pr(doc_type, text, page_number=1, file_name="d.pdf"):
    return PageResult(
        case_id="C1",
        file_name=file_name,
        page_number=page_number,
        ocr=PageOCR(text=text, lines=[]),
        doc_type=doc_type,
        doc_type_confidence=0.9,
    )


def test_arthritis_type_fires_on_osteoarthritis():
    pr = _pr("clinical_notes", "Patient has osteoarthritis of the right knee for 5 years.")
    r = {x.field_name: x for x in evaluate_page_sb039a(pr)}
    assert r["arthritis_type"].value == 1
    assert r["arthritis_type"].evidence


def test_arthritis_type_rheumatoid():
    pr = _pr("clinical_notes", "Known case of rheumatoid arthritis.")
    r = {x.field_name: x.value for x in evaluate_page_sb039a(pr)}
    assert r["arthritis_type"] == 1


def test_age_valid_fires_for_67():
    pr = _pr("clinical_notes", "Name: X Age: 67 years Sex: M")
    r = {x.field_name: x for x in evaluate_page_sb039a(pr)}
    assert r["age_valid"].value == 1
    assert r["age_valid"].evidence


def test_age_valid_does_not_fire_for_48():
    pr = _pr("clinical_notes", "Age: 48 years old male")
    r = {x.field_name: x.value for x in evaluate_page_sb039a(pr)}
    assert r["age_valid"] == 0


def test_xray_ct_knee_presence_from_doctype():
    pr = _pr("xray_ct_knee", "X-ray knee joint shows joint space narrowing.")
    r = {x.field_name: x.value for x in evaluate_page_sb039a(pr)}
    assert r["xray_ct_knee"] == 1


def test_operative_notes_presence():
    pr = _pr("operative_notes", "Operative notes: total knee arthroplasty performed.")
    r = {x.field_name: x.value for x in evaluate_page_sb039a(pr)}
    assert r["operative_notes"] == 1


def test_implant_invoice_presence():
    pr = _pr("implant_invoice", "Implant invoice. Serial number 12345. Manufacturer ABC.")
    r = {x.field_name: x.value for x in evaluate_page_sb039a(pr)}
    assert r["implant_invoice"] == 1


def test_discharge_summary_presence():
    pr = _pr("discharge_summary", "Discharge summary. Patient stable.")
    r = {x.field_name: x.value for x in evaluate_page_sb039a(pr)}
    assert r["discharge_summary"] == 1


def test_post_op_implant_present_on_implant_invoice_with_serial():
    pr = _pr("implant_invoice",
             "Implant Invoice\nSerial number: 1234AB\nManufacturer: Zimmer Biomet")
    r = {x.field_name: x for x in evaluate_page_sb039a(pr)}
    assert r["post_op_implant_present"].value == 1
    assert r["post_op_implant_present"].evidence


def test_post_op_implant_present_requires_doc_type():
    # text mentions serial but doc_type is clinical_notes => should not fire
    pr = _pr("clinical_notes", "Mention of serial number 1234 in random text.")
    r = {x.field_name: x.value for x in evaluate_page_sb039a(pr)}
    assert r["post_op_implant_present"] == 0


def test_doa_dod_extraction_from_discharge_summary():
    pr = _pr(
        "discharge_summary",
        "Date of Admission: 12-03-2026\nDate of Discharge: 18-03-2026\nPatient stable.",
    )
    results = evaluate_page_sb039a(pr)
    # doa/dod are set on pr.entities, not returned as RuleResult
    assert pr.entities.get("doa") == "12-03-2026"
    assert pr.entities.get("dod") == "18-03-2026"


def test_unknown_doctype_no_presence_flags():
    pr = _pr("unknown", "Random unrelated text.")
    r = {x.field_name: x.value for x in evaluate_page_sb039a(pr)}
    for f in ("clinical_notes", "xray_ct_knee", "indoor_case",
              "operative_notes", "implant_invoice", "post_op_photo",
              "post_op_xray", "discharge_summary"):
        assert r[f] == 0, f
