"""Tests for rules.common helpers."""
from pipeline.models import Evidence, RuleResult, PageResult
from rules.common import (
    positive_rule,
    negative_rule,
    merge_rule_results_into_row,
    group_multipage_doc_rank,
)


def test_positive_rule_has_evidence():
    ev = Evidence(page_number=2, text_span="Hb 6.1 g/dL", rule_id="severe_anemia.hb_below_7")
    r = positive_rule("severe_anemia", [ev], rule_path="hb_below_7")
    assert r.value == 1
    assert r.evidence == [ev]


def test_negative_rule_no_evidence_required():
    r = negative_rule("severe_anemia")
    assert r.value == 0
    assert r.evidence == []


def test_merge_rule_results_updates_row():
    row = {"severe_anemia": 0, "cbc_hb_report": 0, "document_rank": 0}
    results = [
        positive_rule("severe_anemia", [Evidence(1, "Hb 6", "x")]),
        positive_rule("cbc_hb_report", [Evidence(1, "Haemoglobin", "y")]),
    ]
    merged_evidence = []
    merge_rule_results_into_row(row, results, merged_evidence)
    assert row["severe_anemia"] == 1
    assert row["cbc_hb_report"] == 1
    assert len(merged_evidence) == 2


def test_multipage_same_rank_grouping():
    # three rows from the same file => they share the same rank (max of assigned)
    rows = [
        {"file_name": "d.pdf", "page_number": 1, "document_rank": 2, "extra_document": 0},
        {"file_name": "d.pdf", "page_number": 2, "document_rank": 2, "extra_document": 0},
        {"file_name": "d.pdf", "page_number": 3, "document_rank": 99, "extra_document": 1},
    ]
    group_multipage_doc_rank(rows)
    # if any page of the file was classified (non-99), all pages from that file keep that rank
    # extra_document=1 stays only for pages whose own label was unknown AND no other page rescued them
    ranks = [r["document_rank"] for r in rows]
    assert ranks[0] == 2
    assert ranks[1] == 2
    # page 3 should be upgraded from 99 to 2 because other pages of same file were classified
    assert ranks[2] == 2
