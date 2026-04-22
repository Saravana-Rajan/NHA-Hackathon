"""MG064A -- Severe Anemia rule engine."""
from __future__ import annotations
import re
from typing import List

from pipeline.models import PageResult, Evidence, RuleResult
from rules.common import positive_rule, negative_rule

# STG Section 3.2: severe anemia threshold
SEVERE_ANEMIA_HB_THRESHOLD = 7.0

HB_PATTERNS = [
    re.compile(r"(?:haemoglobin|hemoglobin|hb)\s*[:\-]?\s*(\d+\.?\d*)\s*(?:g\s*/\s*dl|gm/dl|g%)?",
               re.IGNORECASE),
    re.compile(r"\bhb\s*[:\-]?\s*(\d+\.?\d*)\b", re.IGNORECASE),
]

COMMON_SIGNS = ["pallor", "fatigue", "weakness", "tiredness", "lethargy"]
SIGNIFICANT_SIGNS = ["tachycardia", "breathless", "dyspnea", "dyspnoea",
                     "palpitation", "syncope"]
LIFE_THREATENING_SIGNS = ["cardiac failure", "heart failure", "hypoxia",
                          "shock", "altered sensorium", "gasping"]


def _evidence(page_number, snippet, rule_id) -> Evidence:
    return Evidence(page_number=page_number, text_span=snippet[:120], rule_id=rule_id)


def _any_keyword(text_lower: str, keywords: List[str]):
    """Return (matched_keyword, surrounding_snippet) or (None, None)."""
    for kw in keywords:
        idx = text_lower.find(kw)
        if idx >= 0:
            start = max(0, idx - 30)
            end = min(len(text_lower), idx + len(kw) + 30)
            return kw, text_lower[start:end]
    return None, None


def _extract_hb(text: str):
    for pat in HB_PATTERNS:
        for m in pat.finditer(text):
            try:
                val = float(m.group(1))
                if 1.0 < val < 25.0:  # sane Hb range
                    return val, m.group(0)
            except ValueError:
                continue
    return None, None


PRESENCE_DOCTYPE_MAP = {
    "clinical_notes": "clinical_notes",
    "cbc_hb_report": "cbc_hb_report",
    "indoor_case": "indoor_case",
    "treatment_details": "treatment_details",
    # post_hb_report is a cbc_hb_report that appears after treatment; we flag
    # cbc_hb_report here and let the assembler decide pre vs post via document_rank.
    "discharge_summary": "discharge_summary",
}


def evaluate_page_mg064a(pr: PageResult) -> List[RuleResult]:
    results: List[RuleResult] = []
    text = (pr.ocr.text if pr.ocr else "") or ""
    text_lower = text.lower()
    doc_type = pr.doc_type or "unknown"
    page_num = pr.page_number

    # 1. Presence flags from doc type
    flags = ["clinical_notes", "cbc_hb_report", "indoor_case",
             "treatment_details", "post_hb_report", "discharge_summary"]
    for flag in flags:
        fired = False
        if flag == "post_hb_report":
            # post_hb_report = cbc_hb_report on a page ranked after treatment; defer to assembler.
            # Default to 0 here; assembler may upgrade.
            results.append(negative_rule(flag))
            continue
        mapped = PRESENCE_DOCTYPE_MAP.get(flag)
        if mapped and doc_type == mapped:
            ev = _evidence(page_num, text[:120], f"mg064a.{flag}.doctype")
            results.append(positive_rule(flag, [ev], rule_path=f"mg064a.{flag}.doctype"))
            fired = True
        if not fired:
            results.append(negative_rule(flag))

    # 2. Severe anemia from Hb value
    hb, hb_span = _extract_hb(text)
    if hb is not None and hb < SEVERE_ANEMIA_HB_THRESHOLD:
        ev = _evidence(page_num, f"Hb={hb} g/dL ({hb_span})",
                       f"mg064a.severe_anemia.hb_below_{SEVERE_ANEMIA_HB_THRESHOLD}")
        results.append(positive_rule("severe_anemia", [ev],
                                     rule_path="mg064a.severe_anemia"))
    else:
        results.append(negative_rule("severe_anemia"))

    # 3. Signs
    for flag, keywords in [("common_signs", COMMON_SIGNS),
                           ("significant_signs", SIGNIFICANT_SIGNS),
                           ("life_threatening_signs", LIFE_THREATENING_SIGNS)]:
        kw, span = _any_keyword(text_lower, keywords)
        if kw:
            ev = _evidence(page_num, span, f"mg064a.{flag}.{kw}")
            results.append(positive_rule(flag, [ev], rule_path=f"mg064a.{flag}"))
        else:
            results.append(negative_rule(flag))

    return results
