"""Tests for SG039C (Cholecystectomy)."""
from pipeline.models import PageResult, PageOCR
from rules.sg039c_cholecystectomy import evaluate_page_sg039c


def _pr(doc_type, text, page_number=1, file_name="d.pdf"):
    return PageResult(
        case_id="C1",
        file_name=file_name,
        page_number=page_number,
        ocr=PageOCR(text=text, lines=[]),
        doc_type=doc_type,
        doc_type_confidence=0.9,
    )


def test_clinical_condition_acute_cholecystitis():
    pr = _pr("clinical_notes", "Diagnosis: acute cholecystitis with biliary sludge.")
    r = {x.field_name: x for x in evaluate_page_sg039c(pr)}
    assert r["clinical_condition"].value == 1
    assert r["clinical_condition"].evidence


def test_clinical_condition_cholelithiasis():
    pr = _pr("discharge_summary", "Known case of cholelithiasis, treated with cholecystectomy.")
    r = {x.field_name: x.value for x in evaluate_page_sg039c(pr)}
    assert r["clinical_condition"] == 1


def test_usg_calculi_on_usg_report():
    pr = _pr("usg_report", "Ultrasound abdomen: multiple calculi noted in gall bladder.")
    r = {x.field_name: x for x in evaluate_page_sg039c(pr)}
    assert r["usg_calculi"].value == 1
    assert r["usg_calculi"].evidence


def test_usg_calculi_requires_usg_doctype():
    pr = _pr("clinical_notes", "Mentions gallstone in text.")
    r = {x.field_name: x.value for x in evaluate_page_sg039c(pr)}
    assert r["usg_calculi"] == 0


def test_pain_present():
    pr = _pr("clinical_notes", "Patient c/o epigastric pain for 3 days.")
    r = {x.field_name: x.value for x in evaluate_page_sg039c(pr)}
    assert r["pain_present"] == 1


def test_previous_surgery():
    pr = _pr("clinical_notes", "H/o surgery: previous laparotomy 2 years back.")
    r = {x.field_name: x.value for x in evaluate_page_sg039c(pr)}
    assert r["previous_surgery"] == 1


def test_usg_report_presence_from_doctype():
    pr = _pr("usg_report", "USG abdomen: normal.")
    r = {x.field_name: x.value for x in evaluate_page_sg039c(pr)}
    assert r["usg_report"] == 1


def test_lft_report_presence():
    pr = _pr("lft_report", "Liver function test: ALT 35, AST 30.")
    r = {x.field_name: x.value for x in evaluate_page_sg039c(pr)}
    assert r["lft_report"] == 1


def test_operative_notes_presence():
    pr = _pr("operative_notes", "Operative notes: laparoscopic cholecystectomy.")
    r = {x.field_name: x.value for x in evaluate_page_sg039c(pr)}
    assert r["operative_notes"] == 1


def test_unknown_doctype_no_presence_flags():
    pr = _pr("unknown", "Random text without any relevant keywords.")
    r = {x.field_name: x.value for x in evaluate_page_sg039c(pr)}
    for f in ("clinical_notes", "usg_report", "lft_report", "operative_notes",
              "pre_anesthesia", "discharge_summary", "photo_evidence",
              "histopathology"):
        assert r[f] == 0, f
