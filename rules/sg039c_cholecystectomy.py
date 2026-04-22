"""SG039C -- Cholecystectomy rule engine."""
from __future__ import annotations
from typing import List, Optional, Tuple

from pipeline.models import PageResult, Evidence, RuleResult
from rules.common import positive_rule, negative_rule

CLINICAL_CONDITION_KEYWORDS = [
    "acute cholecystitis", "chronic cholecystitis", "biliary colic",
    "cholelithiasis", "gallstone", "cholecystitis",
]

USG_CALCULI_KEYWORDS = ["calculus", "calculi", "gallstone", "cholelithiasis"]

PAIN_KEYWORDS = ["ruq pain", "epigastric pain", "abdominal pain",
                 "tenderness", "pain"]

PREV_SURGERY_KEYWORDS = ["h/o surgery", "previous surgery", "laparotomy",
                         "previous abdominal surgery", "prior surgery"]

PRESENCE_DOCTYPE_MAP = {
    "clinical_notes": "clinical_notes",
    "usg_report": "usg_report",
    "lft_report": "lft_report",
    "operative_notes": "operative_notes",
    "pre_anesthesia": "pre_anesthesia",
    "discharge_summary": "discharge_summary",
    "photo_evidence": "photo_evidence",
    "histopathology": "histopathology",
}

CLINICAL_CONDITION_DOCTYPES = {"clinical_notes", "discharge_summary",
                               "operative_notes", "histopathology",
                               "unknown"}


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


def evaluate_page_sg039c(pr: PageResult) -> List[RuleResult]:
    results: List[RuleResult] = []
    text = (pr.ocr.text if pr.ocr else "") or ""
    text_lower = text.lower()
    doc_type = pr.doc_type or "unknown"
    page_num = pr.page_number

    # 1. Presence flags
    presence_flags = ["clinical_notes", "usg_report", "lft_report",
                      "operative_notes", "pre_anesthesia", "discharge_summary",
                      "photo_evidence", "histopathology"]
    for flag in presence_flags:
        mapped = PRESENCE_DOCTYPE_MAP.get(flag)
        if mapped and doc_type == mapped:
            ev = _evidence(page_num, text[:120], f"sg039c.{flag}.doctype")
            results.append(positive_rule(flag, [ev], rule_path=f"sg039c.{flag}.doctype"))
        else:
            results.append(negative_rule(flag))

    # 2. clinical_condition: only fires for clinical-bearing doc types
    if doc_type in CLINICAL_CONDITION_DOCTYPES:
        kw, span = _any_keyword(text_lower, CLINICAL_CONDITION_KEYWORDS)
        if kw:
            ev = _evidence(page_num, span,
                           f"sg039c.clinical_condition.{kw.replace(' ', '_')}")
            results.append(positive_rule("clinical_condition", [ev],
                                         rule_path="sg039c.clinical_condition"))
        else:
            results.append(negative_rule("clinical_condition"))
    else:
        results.append(negative_rule("clinical_condition"))

    # 3. usg_calculi: requires doc_type == usg_report AND keyword
    if doc_type == "usg_report":
        kw, span = _any_keyword(text_lower, USG_CALCULI_KEYWORDS)
        if kw:
            ev = _evidence(page_num, span,
                           f"sg039c.usg_calculi.{kw.replace(' ', '_')}")
            results.append(positive_rule("usg_calculi", [ev],
                                         rule_path="sg039c.usg_calculi"))
        else:
            results.append(negative_rule("usg_calculi"))
    else:
        results.append(negative_rule("usg_calculi"))

    # 4. pain_present
    kw, span = _any_keyword(text_lower, PAIN_KEYWORDS)
    if kw:
        ev = _evidence(page_num, span,
                       f"sg039c.pain_present.{kw.replace(' ', '_').replace('/', '_')}")
        results.append(positive_rule("pain_present", [ev],
                                     rule_path="sg039c.pain_present"))
    else:
        results.append(negative_rule("pain_present"))

    # 5. previous_surgery
    kw, span = _any_keyword(text_lower, PREV_SURGERY_KEYWORDS)
    if kw:
        ev = _evidence(page_num, span,
                       f"sg039c.previous_surgery.{kw.replace(' ', '_').replace('/', '_')}")
        results.append(positive_rule("previous_surgery", [ev],
                                     rule_path="sg039c.previous_surgery"))
    else:
        results.append(negative_rule("previous_surgery"))

    return results
