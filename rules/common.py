"""Shared helpers for per-package rule engines."""
from __future__ import annotations
from typing import Any, Dict, List

from pipeline.models import Evidence, RuleResult


def positive_rule(
    field_name: str,
    evidence: List[Evidence],
    confidence: float = 1.0,
    rule_path: str = "",
) -> RuleResult:
    return RuleResult(
        field_name=field_name,
        value=1,
        confidence=confidence,
        evidence=list(evidence),
        rule_path=rule_path or field_name,
    )


def negative_rule(field_name: str, confidence: float = 1.0) -> RuleResult:
    return RuleResult(
        field_name=field_name,
        value=0,
        confidence=confidence,
        evidence=[],
        rule_path=field_name,
    )


def merge_rule_results_into_row(
    row: Dict[str, Any],
    results: List[RuleResult],
    evidence_bag: List[Evidence],
) -> None:
    """Apply rule values to a row in place; collect evidence for provenance."""
    for r in results:
        if r.field_name in row:
            row[r.field_name] = r.value
        evidence_bag.extend(r.evidence)


def group_multipage_doc_rank(rows: List[Dict[str, Any]]) -> None:
    """Pages from the same file share the same document_rank.

    If any page from a file has a classified rank (non-99), all pages of that file
    inherit the minimum non-99 rank seen across the file (earliest rank wins for
    multi-document files; for single-document files, all pages align).
    extra_document is cleared for pages that were rescued by this grouping.
    """
    from collections import defaultdict
    file_min_rank: Dict[str, int] = defaultdict(lambda: 99)
    for r in rows:
        fn = r.get("file_name") or r.get("link") or r.get("S3_link/DocumentName") or ""
        rank = r.get("document_rank", 99) or 99
        if rank != 99 and rank < file_min_rank[fn]:
            file_min_rank[fn] = rank
    for r in rows:
        fn = r.get("file_name") or r.get("link") or r.get("S3_link/DocumentName") or ""
        if file_min_rank.get(fn, 99) < 99:
            r["document_rank"] = file_min_rank[fn]
            if r.get("extra_document") == 1:
                r["extra_document"] = 0
