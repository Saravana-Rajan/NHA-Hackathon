"""Package schemas, aliases, and rank maps.

Single source of truth for exact output keys per package.
Any mismatch = submission rejected unevaluated.
"""
from __future__ import annotations
from typing import Dict, List

PACKAGE_CODES: List[str] = ["MG064A", "SG039C", "MG006A", "SB039A"]

PACKAGE_SCHEMAS: Dict[str, List[str]] = {
    "MG064A": [
        "case_id", "link", "procedure_code", "page_number",
        "clinical_notes", "cbc_hb_report", "indoor_case",
        "treatment_details", "post_hb_report", "discharge_summary",
        "severe_anemia", "common_signs", "significant_signs",
        "life_threatening_signs", "extra_document", "document_rank",
    ],
    "SG039C": [
        "case_id", "S3_link/DocumentName", "procedure_code", "page_number",
        "clinical_notes", "usg_report", "lft_report", "operative_notes",
        "pre_anesthesia", "discharge_summary", "photo_evidence",
        "histopathology", "clinical_condition", "usg_calculi",
        "pain_present", "previous_surgery", "extra_document", "document_rank",
    ],
    "MG006A": [
        "case_id", "S3_link/DocumentName", "procedure_code", "page_number",
        "clinical_notes", "investigation_pre", "pre_date", "vitals_treatment",
        "investigation_post", "post_date", "discharge_summary", "poor_quality",
        "fever", "symptoms", "extra_document", "document_rank",
    ],
    "SB039A": [
        "case_id", "link", "procedure_code", "page_number",
        "clinical_notes", "xray_ct_knee", "indoor_case", "operative_notes",
        "implant_invoice", "post_op_photo", "post_op_xray", "discharge_summary",
        "doa", "dod", "arthritis_type", "post_op_implant_present",
        "age_valid", "extra_document", "document_rank",
    ],
}

# Field sets per package for fast validation
DATE_FIELDS_PER_PACKAGE: Dict[str, List[str]] = {
    "MG064A": [],
    "SG039C": [],
    "MG006A": ["pre_date", "post_date"],
    "SB039A": ["doa", "dod"],
}

BINARY_FIELDS_PER_PACKAGE: Dict[str, List[str]] = {
    pkg: [
        k for k in fields
        if k not in {"case_id", "link", "S3_link/DocumentName",
                     "procedure_code", "page_number", "document_rank"}
        and k not in DATE_FIELDS_PER_PACKAGE.get(pkg, [])
    ]
    for pkg, fields in PACKAGE_SCHEMAS.items()
}

# Canonical rank ordering per package
RANK_MAP: Dict[str, Dict[str, int]] = {
    "MG064A": {
        "clinical_notes": 1,
        "cbc_hb_report": 2,
        "indoor_case": 2,
        "treatment_details": 3,
        "post_hb_report": 4,
        "discharge_summary": 5,
    },
    "SG039C": {
        "clinical_notes": 1,
        "usg_report": 2,
        "lft_report": 3,
        "pre_anesthesia": 4,
        "operative_notes": 5,
        "discharge_summary": 5,
        "histopathology": 6,
        "photo_evidence": 6,
    },
    "MG006A": {
        "clinical_notes": 1,
        "investigation_pre": 2,
        "vitals_treatment": 3,
        "investigation_post": 4,
        "discharge_summary": 5,
    },
    "SB039A": {
        "clinical_notes": 1,
        "xray_ct_knee": 2,
        "indoor_case": 3,
        "operative_notes": 4,
        "implant_invoice": 5,
        "post_op_photo": 6,
        "post_op_xray": 6,
        "discharge_summary": 7,
    },
}

EXTRA_DOCUMENT_RANK = 99


def link_key_for_package(package_code: str) -> str:
    """Return the correct link key name for the given package."""
    if package_code in ("MG064A", "SB039A"):
        return "link"
    return "S3_link/DocumentName"
