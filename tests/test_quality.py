"""Tests for pipeline.quality."""
from pipeline.quality import estimate_page_quality


def test_poor_when_text_empty_and_no_image():
    q = estimate_page_quality("", "")
    assert q["is_poor"] is True
    assert q["text_density"] == 0
    assert "text_density=0<50" in (q.get("reasons") or [])


def test_poor_when_text_very_short():
    q = estimate_page_quality("", "short")
    assert q["is_poor"] is True


def test_not_poor_when_text_long():
    long_text = "This is a long page of extracted text. " * 10  # 400+ chars
    q = estimate_page_quality("", long_text)
    assert q["is_poor"] is False
    assert q["text_density"] >= 200


def test_returns_expected_keys():
    q = estimate_page_quality("", "abc")
    for k in ("is_poor", "blur_score", "text_density", "reasons"):
        assert k in q, k
