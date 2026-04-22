"""Tests for MG006A (Enteric Fever)."""
from pipeline.models import PageResult, PageOCR
from rules.mg006a_enteric import evaluate_page_mg006a


def _pr(doc_type, text, page_number=1, file_name="d.pdf", quality=None):
    pr = PageResult(case_id="C1", file_name=file_name, page_number=page_number,
                    ocr=PageOCR(text=text, lines=[]), doc_type=doc_type,
                    doc_type_confidence=0.9)
    if quality:
        pr.quality = quality
    return pr


def test_fever_high_temp():
    pr = _pr("clinical_notes", "Patient has fever, temp 102 F for 3 days. c/o headache.")
    r = {x.field_name: x for x in evaluate_page_mg006a(pr)}
    assert r["fever"].value == 1
    assert r["fever"].evidence


def test_fever_celsius():
    pr = _pr("clinical_notes", "Temperature 38.5 C recorded daily.")
    r = {x.field_name: x.value for x in evaluate_page_mg006a(pr)}
    assert r["fever"] == 1


def test_no_fever_below_threshold():
    pr = _pr("clinical_notes", "Temperature 37.2 C normal range.")
    r = {x.field_name: x.value for x in evaluate_page_mg006a(pr)}
    assert r["fever"] == 0


def test_symptoms_headache():
    pr = _pr("clinical_notes", "Patient c/o headache and dizziness.")
    r = {x.field_name: x.value for x in evaluate_page_mg006a(pr)}
    assert r["symptoms"] == 1


def test_investigation_pre():
    pr = _pr("investigation_pre", "Widal test positive for Salmonella typhi.")
    r = {x.field_name: x.value for x in evaluate_page_mg006a(pr)}
    assert r["investigation_pre"] == 1


def test_poor_quality_flag():
    pr = _pr("unknown", "garbled text", quality={"is_poor": True})
    r = {x.field_name: x.value for x in evaluate_page_mg006a(pr)}
    assert r["poor_quality"] == 1


def test_no_poor_quality_when_quality_good():
    pr = _pr("clinical_notes", "Clear text.", quality={"is_poor": False})
    r = {x.field_name: x.value for x in evaluate_page_mg006a(pr)}
    assert r["poor_quality"] == 0
