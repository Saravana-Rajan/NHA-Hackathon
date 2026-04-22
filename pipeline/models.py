"""Dataclass models for the NHA PS-01 pipeline.

Shared contracts between modules. Keep fields minimal and explicit.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Page:
    """A single page from an input file."""
    case_id: str
    file_name: str
    page_number: int
    image_path: str
    # Optional: when the page came from a PDF, these allow direct
    # text-layer extraction via PyMuPDF without re-rasterization.
    source_pdf_path: Optional[str] = None
    source_page_index: Optional[int] = None


@dataclass
class OCRLine:
    """One line of OCR output."""
    text: str
    bbox: Optional[List[int]] = None  # [x1, y1, x2, y2]
    confidence: Optional[float] = None


@dataclass
class PageOCR:
    """OCR result for a single page."""
    text: str = ""
    lines: List[OCRLine] = field(default_factory=list)


@dataclass
class Evidence:
    """Provenance citation for a rule decision.

    Required for every positive flag in order to earn the provenance
    component of the 40% rule-logic score.
    """
    page_number: int
    text_span: str
    rule_id: str
    bbox: Optional[List[int]] = None


@dataclass
class RuleResult:
    """Output of a single rule check."""
    field_name: str
    value: int
    confidence: float = 1.0
    evidence: List[Evidence] = field(default_factory=list)
    rule_path: str = ""


@dataclass
class PageResult:
    """All intermediate per-page analysis results."""
    case_id: str
    file_name: str
    page_number: int
    ocr: Optional[PageOCR] = None
    quality: Dict[str, Any] = field(default_factory=dict)
    doc_type: str = "unknown"
    doc_type_confidence: float = 0.0
    visual_tags: Dict[str, Any] = field(default_factory=dict)
    entities: Dict[str, Any] = field(default_factory=dict)
    output_row: Dict[str, Any] = field(default_factory=dict)
    evidence: List[Evidence] = field(default_factory=list)


@dataclass
class TimelineEvent:
    """One event in an episode timeline."""
    sequence: int
    event_type: str
    date: Optional[str]
    source_document: str
    temporal_validity: str
    evidence: List[Evidence] = field(default_factory=list)


@dataclass
class ClaimDecision:
    """Final adjudication of a claim."""
    case_id: str
    package_code: str
    decision: str  # PASS | CONDITIONAL | FAIL
    confidence: float
    reasons: List[str]
    missing_documents: List[str] = field(default_factory=list)
    rule_flags: List[str] = field(default_factory=list)
    timeline_flags: List[str] = field(default_factory=list)
