"""SB039A -- Total Knee Replacement rule engine."""
from __future__ import annotations
import re
from typing import List, Optional, Tuple

from pipeline.models import PageResult, Evidence, RuleResult
from pipeline.extract import find_age, find_dates
from rules.common import positive_rule, negative_rule

AGE_MIN_TKR = 60

ARTHRITIS_KEYWORDS = [
    "osteoarthritis", " oa ", "oa,", "oa.", "oa:",
    "rheumatoid arthritis", "rheumatoid", " ra ", "ra,", "ra.", "ra:",
    "post-traumatic arthritis", "post traumatic arthritis", "post-traumatic",
]

IMPLANT_KEYWORDS = ["serial", "lot", "batch", "manufacturer"]

IMPLANT_DOCTYPES = {"implant_invoice", "post_op_xray", "post_op_photo"}

PRESENCE_DOCTYPE_MAP = {
    "clinical_notes": "clinical_notes",
    "xray_ct_knee": "xray_ct_knee",
    "indoor_case": "indoor_case",
    "operative_notes": "operative_notes",
    "implant_invoice": "implant_invoice",
    "post_op_photo": "post_op_photo",
    "post_op_xray": "post_op_xray",
    "discharge_summary": "discharge_summary",
}

# Date of Admission / Date of Discharge labelled regexes
DOA_LABEL_PATTERN = re.compile(
    r"(?:date\s*of\s*admission|d\.?o\.?a\.?|admission\s*date)\s*[:\-]?\s*"
    r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}-[A-Za-z]{3}-\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})",
    re.IGNORECASE,
)
DOD_LABEL_PATTERN = re.compile(
    r"(?:date\s*of\s*discharge|d\.?o\.?d\.?|discharge\s*date)\s*[:\-]?\s*"
    r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}-[A-Za-z]{3}-\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})",
    re.IGNORECASE,
)


def _evidence(page_number, snippet, rule_id) -> Evidence:
    return Evidence(page_number=page_number, text_span=snippet[:120], rule_id=rule_id)


def _any_keyword(text_lower: str, keywords: List[str]) -> Tuple[Optional[str], Optional[str]]:
    for kw in keywords:
        idx = text_lower.find(kw)
        if idx >= 0:
            start = max(0, idx - 30)
            end = min(len(text_lower), idx + len(kw) + 30)
            return kw, text_lower[start:end]
    return None, None


def _extract_doa_dod(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Try labelled regex first; fall back to find_dates (earliest/latest)."""
    doa = None
    dod = None
    m = DOA_LABEL_PATTERN.search(text)
    if m:
        doa = m.group(1).strip()
    m = DOD_LABEL_PATTERN.search(text)
    if m:
        dod = m.group(1).strip()

    if doa and dod:
        return doa, dod

    # fallback: use find_dates ordering
    all_dates = find_dates(text)
    if not all_dates:
        return doa, dod

    def _parse_rough(d: str):
        # Try DD-MM-YYYY, DD/MM/YYYY, DD-Mon-YYYY
        for pat in (r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})",
                    r"(\d{1,2})-([A-Za-z]{3})-(\d{2,4})"):
            mm = re.match(pat, d)
            if mm:
                try:
                    g1 = int(mm.group(1))
                    g3 = int(mm.group(3)) if mm.group(3).isdigit() else 0
                    return (g3, _month_to_int(mm.group(2)), g1)
                except Exception:
                    continue
        return (0, 0, 0)

    sorted_dates = sorted(all_dates, key=_parse_rough)
    if not doa and sorted_dates:
        doa = sorted_dates[0]
    if not dod and len(sorted_dates) >= 2:
        dod = sorted_dates[-1]
    return doa, dod


def _month_to_int(tok: str) -> int:
    if not tok:
        return 0
    if tok.isdigit():
        try:
            return int(tok)
        except ValueError:
            return 0
    table = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    return table.get(tok.lower()[:3], 0)


def evaluate_page_sb039a(pr: PageResult) -> List[RuleResult]:
    results: List[RuleResult] = []
    text = (pr.ocr.text if pr.ocr else "") or ""
    text_lower = text.lower()
    doc_type = pr.doc_type or "unknown"
    page_num = pr.page_number

    # 1. Presence flags from doc type
    presence_flags = ["clinical_notes", "xray_ct_knee", "indoor_case",
                      "operative_notes", "implant_invoice", "post_op_photo",
                      "post_op_xray", "discharge_summary"]
    for flag in presence_flags:
        mapped = PRESENCE_DOCTYPE_MAP.get(flag)
        if mapped and doc_type == mapped:
            ev = _evidence(page_num, text[:120], f"sb039a.{flag}.doctype")
            results.append(positive_rule(flag, [ev], rule_path=f"sb039a.{flag}.doctype"))
        else:
            results.append(negative_rule(flag))

    # 2. arthritis_type via keyword match
    kw, span = _any_keyword(text_lower, ARTHRITIS_KEYWORDS)
    if kw:
        ev = _evidence(page_num, span, f"sb039a.arthritis_type.{kw.strip()}")
        results.append(positive_rule("arthritis_type", [ev],
                                     rule_path="sb039a.arthritis_type"))
    else:
        results.append(negative_rule("arthritis_type"))

    # 3. post_op_implant_present: doc_type in implant set AND implant keyword
    if doc_type in IMPLANT_DOCTYPES:
        kw2, span2 = _any_keyword(text_lower, IMPLANT_KEYWORDS)
        if kw2:
            ev = _evidence(page_num, span2, f"sb039a.post_op_implant_present.{kw2}")
            results.append(positive_rule("post_op_implant_present", [ev],
                                         rule_path="sb039a.post_op_implant_present"))
        else:
            results.append(negative_rule("post_op_implant_present"))
    else:
        results.append(negative_rule("post_op_implant_present"))

    # 4. age_valid: age >= 60 from find_age
    age = find_age(text)
    if age is not None and age >= AGE_MIN_TKR:
        ev = _evidence(page_num, f"age={age}", f"sb039a.age_valid.{age}")
        results.append(positive_rule("age_valid", [ev],
                                     rule_path="sb039a.age_valid"))
    else:
        results.append(negative_rule("age_valid"))

    # 5. doa/dod extraction: set on pr.entities (NOT returned as RuleResult)
    if doc_type == "discharge_summary" or DOA_LABEL_PATTERN.search(text) or DOD_LABEL_PATTERN.search(text):
        doa, dod = _extract_doa_dod(text)
        if doa:
            pr.entities["doa"] = doa
            pr.evidence.append(_evidence(page_num, f"DOA={doa}", "sb039a.doa"))
        if dod:
            pr.entities["dod"] = dod
            pr.evidence.append(_evidence(page_num, f"DOD={dod}", "sb039a.dod"))

    return results
