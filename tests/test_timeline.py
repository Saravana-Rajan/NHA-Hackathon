"""Tests for pipeline.timeline."""
from pipeline.timeline import build_episode_timeline
from pipeline.models import PageResult, PageOCR


def _pr(doc_type, text, page=1, file_name="d.pdf"):
    return PageResult(case_id="C1", file_name=file_name, page_number=page,
                      ocr=PageOCR(text=text, lines=[]), doc_type=doc_type)


def test_timeline_has_sequence_numbers():
    pages = [
        _pr("clinical_notes", "Date: 10-03-2026 admission noted"),
        _pr("operative_notes", "Date: 12-03-2026 surgery performed", page=2),
        _pr("discharge_summary", "Date: 15-03-2026 discharge", page=3),
    ]
    tl = build_episode_timeline("SB039A", pages)
    assert len(tl) >= 3
    seqs = [e.sequence for e in tl]
    assert seqs == sorted(seqs)  # strictly increasing
    for i, e in enumerate(tl, start=1):
        assert e.sequence == i


def test_chronology_error_when_discharge_before_admission():
    pages = [
        _pr("discharge_summary", "Date of Admission: 15-03-2026 Date of Discharge: 10-03-2026"),
    ]
    tl = build_episode_timeline("SB039A", pages)
    validities = {e.event_type: e.temporal_validity for e in tl}
    assert validities.get("Discharge") == "Chronology error"


def test_empty_pages_returns_empty_timeline():
    assert build_episode_timeline("MG064A", []) == []


def test_timeline_uses_doa_dod_from_entities():
    pr = _pr("discharge_summary", "Admission 10-03-2026 discharge 15-03-2026")
    pr.entities = {"doa": "10-03-2026", "dod": "15-03-2026"}
    tl = build_episode_timeline("SB039A", [pr])
    assert any(e.event_type == "Admission" and e.date == "10-03-2026" for e in tl)
    assert any(e.event_type == "Discharge" and e.date == "15-03-2026" for e in tl)
