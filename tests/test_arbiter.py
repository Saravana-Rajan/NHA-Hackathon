"""Tests for Stage C LLM arbiter."""
from pipeline.arbiter import classify_via_llm_arbiter, _parse_arbiter_response
from pipeline.llm import LLMClient, LLMMode


def test_arbiter_returns_label_from_candidates_on_dry_run():
    client = LLMClient(mode=LLMMode.DRY_RUN)
    label, conf, evidence = classify_via_llm_arbiter(
        client,
        page_text="Unclear scan text.",
        candidates=["discharge_summary", "cbc_hb_report", "unknown"],
    )
    assert label in {"discharge_summary", "cbc_hb_report", "unknown"}
    assert 0.0 <= conf <= 1.0


def test_parse_arbiter_response_strict_json():
    label, reason = _parse_arbiter_response('{"label":"cbc_hb_report","reason":"has Hb value"}')
    assert label == "cbc_hb_report"
    assert "Hb" in reason


def test_parse_arbiter_response_wrapped():
    label, reason = _parse_arbiter_response('Here: {"label":"discharge_summary","reason":"explicit title"}')
    assert label == "discharge_summary"
