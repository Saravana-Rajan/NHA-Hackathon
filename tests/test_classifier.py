"""Tests for pipeline.classifier Stage-A rules."""
from pipeline.classifier import classify_document_type
from pipeline.models import PageOCR


def _ocr(text):
    return PageOCR(text=text, lines=[])


def test_discharge_summary_detected():
    ocr = _ocr("Discharge Summary\nDate of Discharge: 12-Mar-2026\nCourse in hospital: patient improved.")
    label, conf = classify_document_type("MG064A", ocr, {})
    assert label == "discharge_summary"
    assert conf >= 0.7


def test_cbc_hb_report_detected():
    ocr = _ocr("Complete Blood Count\nHaemoglobin: 6.2 g/dL\nMCV 82 MCHC 34\nPlatelet count 1.8 lakh")
    label, conf = classify_document_type("MG064A", ocr, {})
    assert label == "cbc_hb_report"
    assert conf >= 0.7


def test_usg_report_detected():
    ocr = _ocr("USG ABDOMEN\nGall bladder shows multiple calculi\nImpression: cholelithiasis")
    label, conf = classify_document_type("SG039C", ocr, {})
    assert label == "usg_report"


def test_operative_notes_detected():
    ocr = _ocr("OPERATIVE NOTES\nProcedure performed: laparoscopic cholecystectomy\nSurgeon: Dr X")
    label, conf = classify_document_type("SG039C", ocr, {})
    assert label == "operative_notes"


def test_xray_for_tkr_package():
    ocr = _ocr("X-RAY KNEE JOINT\nOsteoarthritis changes noted.")
    label, conf = classify_document_type("SB039A", ocr, {})
    assert label == "xray_ct_knee"


def test_unknown_on_noise():
    ocr = _ocr("Random noise text without any clinical keywords here at all.")
    label, conf = classify_document_type("MG064A", ocr, {})
    assert label == "unknown"
    assert conf < 0.5


def test_empty_text():
    label, conf = classify_document_type("MG064A", _ocr(""), {})
    assert label == "unknown"
    assert conf == 0.0


def test_classifier_returns_evidence_in_visual_tags():
    """After classification, the matched keyword should be retrievable for provenance."""
    from pipeline.classifier import classify_document_type_with_evidence
    ocr = _ocr("Discharge Summary\nDate of Discharge: 12-Mar-2026")
    label, conf, evidence = classify_document_type_with_evidence("MG064A", ocr, {})
    assert label == "discharge_summary"
    assert evidence, "Evidence list must not be empty for a positive match"
    assert any("discharge summary" in e.text_span.lower() for e in evidence)
