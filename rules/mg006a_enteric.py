"""MG006A -- Enteric Fever rule engine."""
from __future__ import annotations
import re
from typing import List

from pipeline.models import PageResult, Evidence, RuleResult
from rules.common import positive_rule, negative_rule

FEVER_TEMP_F_THRESHOLD = 101.0
FEVER_TEMP_C_THRESHOLD = 38.3

TEMP_F_PATTERN = re.compile(r"(?:temp(?:erature)?|t\s*=?)\s*[:\-]?\s*(\d{2,3}(?:\.\d+)?)\s*[degree]?\s*f",
                            re.IGNORECASE)
TEMP_C_PATTERN = re.compile(r"(?:temp(?:erature)?|t\s*=?)\s*[:\-]?\s*(\d{2}(?:\.\d+)?)\s*[degree]?\s*c",
                            re.IGNORECASE)
FEVER_WORD_PATTERN = re.compile(r"\b(fever|pyrexia)\b", re.IGNORECASE)

SYMPTOMS = ["headache", "dizziness", "muscle pain", "joint pain",
            "myalgia", "arthralgia", "weakness", "malaise"]

PRESENCE_DOCTYPE_MAP = {
    "clinical_notes": "clinical_notes",
    "investigation_pre": "investigation_pre",
    "investigation_post": "investigation_post",
    "vitals_treatment": "vitals_treatment",
    "discharge_summary": "discharge_summary",
}


def _evidence(page_number, snippet, rule_id):
    return Evidence(page_number=page_number, text_span=snippet[:120], rule_id=rule_id)


def evaluate_page_mg006a(pr: PageResult) -> List[RuleResult]:
    results: List[RuleResult] = []
    text = (pr.ocr.text if pr.ocr else "") or ""
    text_lower = text.lower()
    doc_type = pr.doc_type or "unknown"
    page_num = pr.page_number

    presence_flags = ["clinical_notes", "investigation_pre",
                      "vitals_treatment", "investigation_post",
                      "discharge_summary"]
    for flag in presence_flags:
        mapped = PRESENCE_DOCTYPE_MAP.get(flag)
        if mapped and doc_type == mapped:
            ev = _evidence(page_num, text[:120], f"mg006a.{flag}.doctype")
            results.append(positive_rule(flag, [ev], rule_path=f"mg006a.{flag}"))
        else:
            results.append(negative_rule(flag))

    # poor_quality from quality module
    is_poor = bool(pr.quality.get("is_poor")) if pr.quality else False
    if is_poor:
        ev = _evidence(page_num, "quality.is_poor=True", "mg006a.poor_quality")
        results.append(positive_rule("poor_quality", [ev],
                                     rule_path="mg006a.poor_quality"))
    else:
        results.append(negative_rule("poor_quality"))

    # fever
    fever_fired = False
    # temp in F
    for m in TEMP_F_PATTERN.finditer(text):
        try:
            val = float(m.group(1))
            if val >= FEVER_TEMP_F_THRESHOLD and val < 115:
                ev = _evidence(page_num, m.group(0), "mg006a.fever.f_ge_101")
                results.append(positive_rule("fever", [ev],
                                             rule_path="mg006a.fever"))
                fever_fired = True
                break
        except ValueError:
            continue
    # temp in C
    if not fever_fired:
        for m in TEMP_C_PATTERN.finditer(text):
            try:
                val = float(m.group(1))
                if val >= FEVER_TEMP_C_THRESHOLD and val < 45:
                    ev = _evidence(page_num, m.group(0), "mg006a.fever.c_ge_38.3")
                    results.append(positive_rule("fever", [ev],
                                                 rule_path="mg006a.fever"))
                    fever_fired = True
                    break
            except ValueError:
                continue
    if not fever_fired:
        # also fire on explicit "fever" word if present (lower confidence)
        if FEVER_WORD_PATTERN.search(text):
            # only count if clinical_notes doc type to reduce false positives
            if doc_type == "clinical_notes":
                ev = _evidence(page_num, "fever mention",
                               "mg006a.fever.word")
                results.append(positive_rule("fever", [ev],
                                             confidence=0.6,
                                             rule_path="mg006a.fever"))
                fever_fired = True
    if not fever_fired:
        results.append(negative_rule("fever"))

    # symptoms
    sym_fired = False
    for kw in SYMPTOMS:
        if kw in text_lower:
            start = max(0, text_lower.find(kw) - 30)
            ev = _evidence(page_num, text_lower[start:start+80],
                           f"mg006a.symptoms.{kw.replace(' ', '_')}")
            results.append(positive_rule("symptoms", [ev],
                                         rule_path="mg006a.symptoms"))
            sym_fired = True
            break
    if not sym_fired:
        results.append(negative_rule("symptoms"))

    return results
