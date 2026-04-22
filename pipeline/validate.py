"""Schema-exactness validation.

If this fails, the submission is rejected unevaluated. Zero tolerance.
"""
from __future__ import annotations
from typing import Any, Dict, List, Tuple

from pipeline.schemas import (
    PACKAGE_SCHEMAS,
    BINARY_FIELDS_PER_PACKAGE,
    DATE_FIELDS_PER_PACKAGE,
)


def validate_output_rows(
    package_code: str,
    rows: List[Dict[str, Any]],
) -> Tuple[bool, List[str]]:
    """Check key names and order against the package schema."""
    if package_code not in PACKAGE_SCHEMAS:
        return False, [f"Unknown package: {package_code}"]
    expected = PACKAGE_SCHEMAS[package_code]
    issues: List[str] = []
    for i, row in enumerate(rows):
        actual = list(row.keys())
        if actual != expected:
            issues.append(
                f"Row {i}: key mismatch.\n"
                f"  expected: {expected}\n"
                f"  got:      {actual}"
            )
    return len(issues) == 0, issues


def validate_row_types(
    package_code: str,
    row: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """Check per-field types and value ranges."""
    issues: List[str] = []
    if package_code not in PACKAGE_SCHEMAS:
        return False, [f"Unknown package: {package_code}"]

    binary_fields = BINARY_FIELDS_PER_PACKAGE[package_code]
    date_fields = DATE_FIELDS_PER_PACKAGE.get(package_code, [])

    # page_number must be positive int
    if not isinstance(row.get("page_number"), int) or row["page_number"] < 1:
        issues.append(f"page_number must be positive int, got {row.get('page_number')!r}")

    # document_rank must be int (0 is fine during phase 1 dev, 1..N or 99 in final)
    if not isinstance(row.get("document_rank"), int):
        issues.append(f"document_rank must be int, got {row.get('document_rank')!r}")

    # binary flags
    for k in binary_fields:
        v = row.get(k)
        if v not in (0, 1):
            issues.append(f"{k} must be 0 or 1, got {v!r}")

    # date fields: str or None
    for k in date_fields:
        v = row.get(k)
        if v is not None and not isinstance(v, str):
            issues.append(f"{k} must be str or None, got {type(v).__name__}")

    return len(issues) == 0, issues


def compute_field_level_f1(
    package_code: str,
    predicted_rows: List[Dict[str, Any]],
    gold_rows: List[Dict[str, Any]],
) -> Dict[str, Dict[str, float]]:
    """Compute per-field precision/recall/F1.

    Alignment is by page_number. Gold rows that cannot be aligned to a
    predicted row (or vice versa) are counted as missing matches.
    Returns {field_name: {precision, recall, f1}}.
    """
    fields = BINARY_FIELDS_PER_PACKAGE[package_code]
    by_page_pred = {r["page_number"]: r for r in predicted_rows}
    by_page_gold = {r["page_number"]: r for r in gold_rows}
    pages = sorted(set(by_page_pred) | set(by_page_gold))
    metrics: Dict[str, Dict[str, float]] = {}
    for field in fields:
        tp = fp = fn = 0
        for p in pages:
            pv = int(by_page_pred.get(p, {}).get(field, 0) or 0)
            gv = int(by_page_gold.get(p, {}).get(field, 0) or 0)
            if pv == 1 and gv == 1:
                tp += 1
            elif pv == 1 and gv == 0:
                fp += 1
            elif pv == 0 and gv == 1:
                fn += 1
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        metrics[field] = {"precision": prec, "recall": rec, "f1": f1,
                          "tp": tp, "fp": fp, "fn": fn}
    return metrics


def check_provenance_coverage(
    package_code: str,
    rows: List[Dict[str, Any]],
    evidence_per_page: Dict[int, int],
) -> Tuple[float, List[str]]:
    """Return (coverage_ratio, list_of_pages_with_missing_evidence).

    `evidence_per_page[page_number]` is the count of Evidence objects collected
    for positive flags on that page. A page with >=1 positive flag needs
    >=1 evidence entry to count as covered.
    """
    fields = BINARY_FIELDS_PER_PACKAGE[package_code]
    covered = 0
    needed = 0
    missing_pages: List[str] = []
    for row in rows:
        p = row["page_number"]
        has_positive = any(int(row.get(f, 0) or 0) == 1 for f in fields)
        if has_positive:
            needed += 1
            if evidence_per_page.get(p, 0) >= 1:
                covered += 1
            else:
                missing_pages.append(f"page={p}")
    ratio = (covered / needed) if needed else 1.0
    return ratio, missing_pages
