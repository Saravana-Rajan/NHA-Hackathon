"""Stage-A document-type classifier: keyword rules with evidence emission.

Each rule entry has:
  - must_have_any: at least one of these phrases must appear
  - nice: extra signals; each adds to the score
  - threshold: minimum total score for the label to fire

The classifier scores every candidate label, picks the highest above threshold.
Unknown is returned if nothing exceeds threshold.
"""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from pipeline.models import PageOCR, Evidence

_TUNED_THRESHOLDS_PATH = Path(__file__).resolve().parent / "tuned_thresholds.json"


@dataclass
class Hit:
    keyword: str
    span: str  # the surrounding text (up to 80 chars)


DOCTYPE_RULES: Dict[str, Dict] = {
    "discharge_summary": {
        "must_have_any": ["discharge summary"],
        "nice": ["date of discharge", "d.o.d", "dod:", "course in hospital",
                 "follow up", "at the time of discharge", "discharged in stable"],
        "threshold": 1.0,
    },
    "cbc_hb_report": {
        "must_have_any": ["haemoglobin", "hemoglobin", "hb:", "hb -", "hb :"],
        "nice": ["mcv", "mchc", "mch ", "platelet", "wbc", "rbc", "g/dl",
                 "complete blood count", "cbc"],
        "threshold": 1.0,
    },
    "lft_report": {
        "must_have_any": ["liver function test", "lft", "sgpt", "sgot",
                          "alt:", "ast:", "bilirubin"],
        "nice": ["alkaline phosphatase", "total protein", "albumin"],
        "threshold": 1.0,
    },
    "usg_report": {
        "must_have_any": ["ultrasound", "usg ", "sonography", "u.s.g"],
        "nice": ["gall bladder", "calculus", "calculi", "impression",
                 "abdomen", "pelvic", "cholelithiasis"],
        "threshold": 1.0,
    },
    "operative_notes": {
        "must_have_any": ["operative notes", "operation notes", "op notes",
                          "procedure performed"],
        "nice": ["surgeon", "anaesthetist", "laparoscopic",
                 "cholecystectomy", "arthroplasty", "total knee"],
        "threshold": 1.0,
    },
    "pre_anesthesia": {
        "must_have_any": ["pre-anesthesia", "pre anaesthesia", "pre-anaesthetic",
                          "pac", "paed check", "fitness for anaesthesia"],
        "nice": ["asa grade", "mallampati", "nbm", "informed consent"],
        "threshold": 1.0,
    },
    "histopathology": {
        "must_have_any": ["histopathology", "histopath", "biopsy report",
                          "microscopy"],
        "nice": ["specimen", "sections examined", "diagnosis:", "impression"],
        "threshold": 1.0,
    },
    "xray_ct_knee": {
        "must_have_any": ["x-ray knee", "xray knee", "x ray knee",
                          "ct knee", "radiograph", "radiological",
                          "osteoarthritis"],
        "nice": ["knee joint", "tibiofemoral", "patellofemoral",
                 "joint space", "osteophytes"],
        "threshold": 1.0,
    },
    "post_op_xray": {
        "must_have_any": ["post operative x-ray", "post-op xray",
                          "post op x ray", "postoperative radiograph"],
        "nice": ["implant", "prosthesis"],
        "threshold": 1.0,
    },
    "post_op_photo": {
        "must_have_any": ["post op photo", "post-operative photograph",
                          "postop photograph"],
        "nice": [],
        "threshold": 1.0,
    },
    "photo_evidence": {
        "must_have_any": ["specimen photograph", "intra op photo",
                          "intraoperative photograph"],
        "nice": [],
        "threshold": 1.0,
    },
    "implant_invoice": {
        "must_have_any": ["implant invoice", "implant sticker",
                          "implant details", "implant - ", "prosthesis invoice"],
        "nice": ["serial number", "lot no", "batch no", "manufacturer"],
        "threshold": 1.0,
    },
    "indoor_case": {
        "must_have_any": ["indoor case paper", "ipd notes", "ipd file",
                          "admission record", "case paper"],
        "nice": ["vital signs", "intake output", "nursing notes"],
        "threshold": 1.0,
    },
    "treatment_details": {
        "must_have_any": ["treatment given", "medication chart",
                          "blood transfusion", "packed cells",
                          "prbc", "transfusion record"],
        "nice": ["iv antibiotics", "fluids"],
        "threshold": 1.0,
    },
    "vitals_treatment": {
        "must_have_any": ["vital signs", "vital chart", "temperature chart",
                          "pulse chart", "tpr chart"],
        "nice": ["bp", "pulse", "temp", "respiratory rate", "sp02"],
        "threshold": 1.0,
    },
    "investigation_pre": {
        "must_have_any": ["investigation", "blood culture", "widal",
                          "typhidot", "peripheral smear"],
        "nice": ["esr", "crp", "malaria", "dengue"],
        "threshold": 1.0,
    },
    "investigation_post": {
        # same signals as pre; context (date vs admission) differentiates them
        "must_have_any": ["repeat investigation", "follow up cbc",
                          "post treatment"],
        "nice": [],
        "threshold": 1.0,
    },
    "clinical_notes": {
        "must_have_any": ["clinical note", "history of presenting",
                          "chief complaint", "c/o ", "presenting complaint",
                          "history taken"],
        "nice": ["examination", "diagnosis:", "provisional diagnosis",
                 "plan of management"],
        "threshold": 1.0,
    },
}

def _apply_tuned_thresholds() -> None:
    """If pipeline/tuned_thresholds.json exists, override DOCTYPE_RULES[x]['threshold']."""
    try:
        if not _TUNED_THRESHOLDS_PATH.exists():
            return
        with open(_TUNED_THRESHOLDS_PATH, "r", encoding="utf-8") as f:
            tuned = json.load(f)
        if not isinstance(tuned, dict):
            return
        for doc_type, value in tuned.items():
            if doc_type in DOCTYPE_RULES and isinstance(value, (int, float)):
                DOCTYPE_RULES[doc_type]["threshold"] = float(value)
    except Exception:
        # Never let a broken tuning file break classification.
        return


_apply_tuned_thresholds()


# doc types never valid for a given package => excluded from that package's candidate set
PACKAGE_VALID_TYPES: Dict[str, List[str]] = {
    "MG064A": [
        "clinical_notes", "cbc_hb_report", "indoor_case",
        "treatment_details", "discharge_summary",
    ],
    "MG006A": [
        "clinical_notes", "investigation_pre", "investigation_post",
        "vitals_treatment", "discharge_summary",
    ],
    "SB039A": [
        "clinical_notes", "xray_ct_knee", "post_op_xray", "indoor_case",
        "operative_notes", "implant_invoice", "post_op_photo",
        "discharge_summary",
    ],
    "SG039C": [
        "clinical_notes", "usg_report", "lft_report", "operative_notes",
        "pre_anesthesia", "discharge_summary", "photo_evidence",
        "histopathology",
    ],
}


def _find_span(text: str, needle: str, window: int = 80) -> str:
    idx = text.lower().find(needle.lower())
    if idx < 0:
        return ""
    start = max(0, idx - window // 2)
    end = min(len(text), idx + len(needle) + window // 2)
    return text[start:end].replace("\n", " ").strip()


def _score_label(text_lower: str, rule: dict) -> Tuple[float, List[str]]:
    must_any = rule.get("must_have_any", [])
    nice = rule.get("nice", [])
    threshold = rule.get("threshold", 1.0)
    hits: List[str] = []
    score = 0.0
    if must_any:
        found_must = [kw for kw in must_any if kw in text_lower]
        if not found_must:
            return 0.0, []
        score += 1.0
        hits.extend(found_must)
    for kw in nice:
        if kw in text_lower:
            score += 0.25
            hits.append(kw)
    if score < threshold:
        return 0.0, []
    return score, hits


def classify_document_type(
    package_code: str,
    ocr: PageOCR,
    visual_tags: dict,
) -> Tuple[str, float]:
    """Return (doc_type_label, confidence_in_0_1)."""
    label, conf, _ = classify_document_type_with_evidence(package_code, ocr, visual_tags)
    return label, conf


def classify_document_type_with_evidence(
    package_code: str,
    ocr: PageOCR,
    visual_tags: dict,
) -> Tuple[str, float, List[Evidence]]:
    """Same as classify_document_type but also returns Evidence list for provenance."""
    text = ocr.text or ""
    if not text.strip():
        return "unknown", 0.0, []

    text_lower = text.lower()
    valid_types = PACKAGE_VALID_TYPES.get(package_code, list(DOCTYPE_RULES.keys()))

    best_label = "unknown"
    best_score = 0.0
    best_hits: List[str] = []

    for label in valid_types:
        rule = DOCTYPE_RULES.get(label)
        if not rule:
            continue
        score, hits = _score_label(text_lower, rule)
        if score > best_score:
            best_score = score
            best_label = label
            best_hits = hits

    if best_score <= 0:
        return "unknown", 0.0, []

    # Normalize score to 0-1 confidence.  Rule must_have alone = 1.0 score; each nice adds 0.25.
    # Cap at 1.0.
    conf = min(1.0, best_score / 2.0 + 0.3)  # so must_have_only -> 0.8, with nices -> 0.9-1.0

    evidence = [
        Evidence(
            page_number=1,   # caller should overwrite with real page number
            text_span=_find_span(text, kw),
            rule_id=f"classifier.{best_label}.{kw}",
        )
        for kw in best_hits[:3]  # cap at 3 pieces of evidence
    ]

    return best_label, conf, evidence
