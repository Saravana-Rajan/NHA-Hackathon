"""Episode-timeline construction.

Produces a chronological ordered list of canonical events:
  Admission -> Diagnostic Investigation -> Procedure (Package)
    -> Post-Procedure Monitoring -> Discharge

Each event has a temporal_validity label derived from date ordering.
"""
from __future__ import annotations
import re
from datetime import datetime
from typing import List, Optional

from pipeline.models import PageResult, TimelineEvent, Evidence

CANONICAL_EVENTS = [
    "Admission",
    "Diagnostic Investigation",
    "Procedure (Package)",
    "Post-Procedure Monitoring",
    "Discharge",
]

DOCTYPE_TO_EVENT = {
    "clinical_notes": "Admission",
    "investigation_pre": "Diagnostic Investigation",
    "cbc_hb_report": "Diagnostic Investigation",
    "usg_report": "Diagnostic Investigation",
    "lft_report": "Diagnostic Investigation",
    "xray_ct_knee": "Diagnostic Investigation",
    "operative_notes": "Procedure (Package)",
    "treatment_details": "Procedure (Package)",
    "pre_anesthesia": "Procedure (Package)",
    "post_hb_report": "Post-Procedure Monitoring",
    "vitals_treatment": "Post-Procedure Monitoring",
    "post_op_photo": "Post-Procedure Monitoring",
    "post_op_xray": "Post-Procedure Monitoring",
    "implant_invoice": "Post-Procedure Monitoring",
    "histopathology": "Post-Procedure Monitoring",
    "discharge_summary": "Discharge",
}


def _parse_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d-%b-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(str(raw), fmt)
        except Exception:
            continue
    return None


def _first_date(text: str) -> Optional[str]:
    pats = [r"\d{1,2}-\d{1,2}-\d{2,4}", r"\d{1,2}/\d{1,2}/\d{2,4}",
            r"\d{1,2}-[A-Za-z]{3}-\d{2,4}"]
    for p in pats:
        m = re.search(p, text or "")
        if m:
            return m.group(0)
    return None


_DOA_TEXT_RE = re.compile(
    r"(?:date\s*of\s*admission|admission\s*date|doa)\s*[:\-]?\s*"
    r"(\d{1,2}[-/][A-Za-z0-9]{1,9}[-/]\d{2,4})",
    re.IGNORECASE,
)
_DOD_TEXT_RE = re.compile(
    r"(?:date\s*of\s*discharge|discharge\s*date|dod)\s*[:\-]?\s*"
    r"(\d{1,2}[-/][A-Za-z0-9]{1,9}[-/]\d{2,4})",
    re.IGNORECASE,
)


def _extract_doa(pr: PageResult) -> Optional[str]:
    if pr.entities and pr.entities.get("doa"):
        return pr.entities.get("doa")
    text = pr.ocr.text if pr.ocr else ""
    m = _DOA_TEXT_RE.search(text or "")
    return m.group(1) if m else None


def _extract_dod(pr: PageResult) -> Optional[str]:
    if pr.entities and pr.entities.get("dod"):
        return pr.entities.get("dod")
    text = pr.ocr.text if pr.ocr else ""
    m = _DOD_TEXT_RE.search(text or "")
    return m.group(1) if m else None


def _update_event(events_by_type, event_type, date_obj, display_date, source, evidence):
    """Set or replace the event only if the new date is earlier (or existing has no date)."""
    prev = events_by_type.get(event_type)
    if prev is None:
        events_by_type[event_type] = (date_obj, display_date, source, evidence)
        return
    if date_obj and (prev[0] is None or date_obj < prev[0]):
        events_by_type[event_type] = (date_obj, display_date, source, evidence)


def build_episode_timeline(package_code: str, pages: List[PageResult]) -> List[TimelineEvent]:
    if not pages:
        return []

    events_by_type = {}  # event_type -> (date_obj, display_date, source_doc, evidence)

    for pr in pages:
        doc_type = pr.doc_type or "unknown"
        event_type = DOCTYPE_TO_EVENT.get(doc_type)

        # Special case: discharge_summary can yield BOTH an Admission (from doa)
        # and a Discharge (from dod) event.
        if doc_type == "discharge_summary":
            doa = _extract_doa(pr)
            if doa:
                doa_obj = _parse_date(doa)
                evidence = [Evidence(page_number=pr.page_number,
                                     text_span=(pr.ocr.text[:100] if pr.ocr and pr.ocr.text else ""),
                                     rule_id="timeline.Admission.from_discharge_summary")]
                _update_event(events_by_type, "Admission", doa_obj, doa, pr.file_name, evidence)
            dod = _extract_dod(pr)
            if dod:
                dod_obj = _parse_date(dod)
                evidence = [Evidence(page_number=pr.page_number,
                                     text_span=(pr.ocr.text[:100] if pr.ocr and pr.ocr.text else ""),
                                     rule_id="timeline.Discharge.from_discharge_summary")]
                _update_event(events_by_type, "Discharge", dod_obj, dod, pr.file_name, evidence)
            if doa or dod:
                # discharge_summary was handled via entity/text extraction above
                continue

        if not event_type:
            continue

        # Prefer entity-extracted dates
        display_date = None
        if pr.entities:
            if event_type == "Admission":
                display_date = pr.entities.get("doa") or pr.entities.get("pre_date")
            elif event_type == "Discharge":
                display_date = pr.entities.get("dod")
            elif event_type == "Diagnostic Investigation":
                display_date = pr.entities.get("pre_date")
            elif event_type == "Post-Procedure Monitoring":
                display_date = pr.entities.get("post_date")
        if not display_date:
            display_date = _first_date(pr.ocr.text if pr.ocr else "")

        date_obj = _parse_date(display_date)
        evidence = [Evidence(page_number=pr.page_number,
                             text_span=(pr.ocr.text[:100] if pr.ocr and pr.ocr.text else ""),
                             rule_id=f"timeline.{event_type}.from_{doc_type}")]
        _update_event(events_by_type, event_type, date_obj, display_date, pr.file_name, evidence)

    # Chronology check for temporal_validity
    admission = events_by_type.get("Admission", (None,))[0]
    procedure = events_by_type.get("Procedure (Package)", (None,))[0]
    discharge = events_by_type.get("Discharge", (None,))[0]

    ordered: List[TimelineEvent] = []
    for idx, ev_type in enumerate(CANONICAL_EVENTS, start=1):
        if ev_type not in events_by_type:
            continue
        date_obj, display_date, source, evidence = events_by_type[ev_type]
        validity = "Valid"
        if ev_type == "Diagnostic Investigation" and procedure and date_obj and date_obj <= procedure:
            validity = "Before procedure"
        if ev_type == "Post-Procedure Monitoring" and procedure and date_obj and date_obj < procedure:
            validity = "Chronology error"
        if ev_type == "Discharge" and admission and date_obj and date_obj < admission:
            validity = "Chronology error"
        if ev_type == "Discharge" and procedure and date_obj and date_obj > procedure:
            validity = "After treatment"
        ordered.append(TimelineEvent(
            sequence=idx,
            event_type=ev_type,
            date=display_date,
            source_document=source,
            temporal_validity=validity,
            evidence=evidence,
        ))
    # Re-sequence after filtering
    for i, e in enumerate(ordered, start=1):
        e.sequence = i
    return ordered
