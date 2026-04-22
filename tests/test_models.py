"""Tests for pipeline dataclass models."""
from pipeline.models import Page, PageOCR, OCRLine, Evidence, PageResult


def test_page_minimal_fields():
    p = Page(case_id="C1", file_name="d.pdf", page_number=1, image_path="/tmp/x.png")
    assert p.case_id == "C1"
    assert p.page_number == 1


def test_ocr_line_bbox_optional():
    line = OCRLine(text="Hello", bbox=None, confidence=0.99)
    assert line.text == "Hello"
    assert line.bbox is None


def test_evidence_requires_page_and_snippet():
    e = Evidence(page_number=1, text_span="Hb 6.2 g/dL", rule_id="severe_anemia.hb_below_7")
    assert e.page_number == 1
    assert "Hb" in e.text_span


def test_page_result_defaults():
    pr = PageResult(case_id="C1", file_name="d.pdf", page_number=1)
    assert pr.doc_type == "unknown"
    assert pr.doc_type_confidence == 0.0
    assert pr.output_row == {}
