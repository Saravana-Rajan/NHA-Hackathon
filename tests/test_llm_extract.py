"""Tests for pipeline.llm_extract."""
from pipeline.llm import LLMClient, LLMMode
from pipeline.llm_extract import extract_dates_llm


def test_dry_run_returns_nulls():
    client = LLMClient(mode=LLMMode.DRY_RUN)
    result = extract_dates_llm(client, "Some discharge summary text", target_fields=["doa", "dod"])
    assert "doa" in result
    assert "dod" in result


def test_json_parse_valid():
    from pipeline.llm_extract import _parse_llm_response
    parsed = _parse_llm_response('Here is the JSON: {"doa": "12-03-2026", "dod": "18-03-2026"}')
    assert parsed["doa"] == "12-03-2026"
    assert parsed["dod"] == "18-03-2026"


def test_normalize_date_formats():
    from pipeline.llm_extract import _normalize_dd_mm_yyyy
    assert _normalize_dd_mm_yyyy("12-Mar-2026") == "12-03-2026"
    assert _normalize_dd_mm_yyyy("12/3/26") == "12-03-2026"
    assert _normalize_dd_mm_yyyy("12-03-26") == "12-03-2026"
    assert _normalize_dd_mm_yyyy(None) is None
    assert _normalize_dd_mm_yyyy("not a date") is None
