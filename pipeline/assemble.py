"""Assemble per-page output rows in exact schema order.

Phase 1 behaviour: zero-initialized row, extra_document/document_rank from doc_type.
Phase 2 extension: overlay rule-engine-produced RuleResult values and entity fields
(doa, dod, pre_date, post_date) onto the row; re-derive extra_document and
document_rank from the final row state.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional

from pipeline.models import PageResult, RuleResult
from pipeline.schemas import (
    PACKAGE_SCHEMAS,
    RANK_MAP,
    EXTRA_DOCUMENT_RANK,
    DATE_FIELDS_PER_PACKAGE,
    BINARY_FIELDS_PER_PACKAGE,
    link_key_for_package,
)


# Per-package entity -> row field mapping (date fields populated from pr.entities)
ENTITY_DATE_FIELDS: Dict[str, List[str]] = {
    "SB039A": ["doa", "dod"],
    "MG006A": ["pre_date", "post_date"],
    "MG064A": [],
    "SG039C": [],
}


def initialize_output_row(
    package_code: str,
    case_id: str,
    file_name: str,
    page_number: int,
) -> Dict[str, Any]:
    """Create a zero-initialized row with the exact package schema key order."""
    schema = PACKAGE_SCHEMAS[package_code]
    link_key = link_key_for_package(package_code)
    date_fields = set(DATE_FIELDS_PER_PACKAGE.get(package_code, []))
    row: Dict[str, Any] = {}
    for key in schema:
        if key == "case_id":
            row[key] = case_id
        elif key == link_key:
            row[key] = file_name
        elif key == "procedure_code":
            row[key] = package_code
        elif key == "page_number":
            row[key] = page_number
        elif key == "document_rank":
            row[key] = 0  # populated later
        elif key in date_fields:
            row[key] = None
        else:
            row[key] = 0
    return row


def infer_document_rank(package_code: str, doc_type: str) -> int:
    """Map doctype to canonical rank; unknown -> 99."""
    return RANK_MAP.get(package_code, {}).get(doc_type, EXTRA_DOCUMENT_RANK)


def _presence_flags_for_package(package_code: str) -> List[str]:
    """Return the subset of binary fields that act as doc-type presence flags."""
    # Presence flags are the binary fields that map to doc types in the RANK_MAP.
    return [k for k in RANK_MAP.get(package_code, {}).keys()
            if k in BINARY_FIELDS_PER_PACKAGE.get(package_code, [])]


def populate_row_for_package(
    package_code: str,
    page_result: PageResult,
    rule_results: Optional[List[RuleResult]] = None,
) -> Dict[str, Any]:
    """Build a schema-ordered row, optionally overlaying rule results + entities."""
    from rules.common import merge_rule_results_into_row

    row = initialize_output_row(
        package_code,
        page_result.case_id,
        page_result.file_name,
        page_result.page_number,
    )

    doc_type = page_result.doc_type or "unknown"

    # Default rank from doc_type
    rank = infer_document_rank(package_code, doc_type)
    row["document_rank"] = rank

    # extra_document if rank is 99 (unknown doctype)
    if rank == EXTRA_DOCUMENT_RANK:
        row["extra_document"] = 1

    # Overlay rule results
    if rule_results:
        merge_rule_results_into_row(row, rule_results, page_result.evidence)

    # Overlay entity date fields
    for date_field in ENTITY_DATE_FIELDS.get(package_code, []):
        val = page_result.entities.get(date_field)
        if val and date_field in row:
            row[date_field] = val

    # Re-derive extra_document / document_rank based on final row state
    presence_flags = _presence_flags_for_package(package_code)
    any_presence = any(int(row.get(f, 0) or 0) == 1 for f in presence_flags)

    if not any_presence and doc_type == "unknown":
        row["extra_document"] = 1
        row["document_rank"] = EXTRA_DOCUMENT_RANK
    else:
        # If any presence flag fires, assign rank from doc_type
        # (prefer rank of the strongest matching doc_type if known)
        row["extra_document"] = 0
        if doc_type != "unknown":
            row["document_rank"] = infer_document_rank(package_code, doc_type)
        else:
            # find minimum rank among fired presence flags
            fired_ranks = [RANK_MAP[package_code][f]
                           for f in presence_flags
                           if int(row.get(f, 0) or 0) == 1
                           and f in RANK_MAP.get(package_code, {})]
            if fired_ranks:
                row["document_rank"] = min(fired_ranks)
            else:
                row["document_rank"] = EXTRA_DOCUMENT_RANK
                row["extra_document"] = 1

    return row
