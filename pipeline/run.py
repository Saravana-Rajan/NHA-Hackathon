"""End-to-end batch runner.

Wires ingest -> OCR -> quality -> classifier -> (optional LLM arbiter) ->
rule engine -> (optional LLM date extract) -> assemble -> (optional
timeline) into a complete pass that produces schema-valid, rule-populated
rows for every case.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pipeline.arbiter import classify_via_llm_arbiter
from pipeline.assemble import populate_row_for_package
from pipeline.classifier import classify_document_type, PACKAGE_VALID_TYPES
from pipeline.ingest import (
    discover_cases,
    extract_pages,
    iter_case_files,
)
from pipeline.llm import LLMClient
from pipeline.llm_extract import extract_dates_llm
from pipeline.models import PageResult, RuleResult, TimelineEvent
from pipeline.ocr import run_ocr, OCRBackend
from pipeline.quality import estimate_page_quality
from pipeline.schemas import DATE_FIELDS_PER_PACKAGE
from pipeline.timeline import build_episode_timeline

from rules.common import group_multipage_doc_rank
from rules.mg064a_anemia import evaluate_page_mg064a
from rules.mg006a_enteric import evaluate_page_mg006a
from rules.sb039a_tkr import evaluate_page_sb039a
from rules.sg039c_cholecystectomy import evaluate_page_sg039c

REPO_ROOT = Path(__file__).resolve().parent.parent


def _resolve_claims_root() -> Path:
    """Pick the claims root, preferring evaluator-mounted paths.

    Resolution order:
      1. ``NHA_CLAIMS_ROOT`` env var (if set and exists).
      2. ``/mnt/databanks/input`` and common subpaths under it (NHA sandbox).
      3. Repo-local ``Datasets/filesofdata/Claims`` (developer machine).
    """
    env_override = os.environ.get("NHA_CLAIMS_ROOT", "").strip()
    if env_override:
        p = Path(env_override)
        if p.exists():
            return p

    databank_input = Path("/mnt/databanks/input")
    if databank_input.exists():
        for candidate in (
            databank_input / "filesofdata" / "Claims",
            databank_input / "Claims",
            databank_input,
        ):
            if candidate.exists():
                return candidate

    home_claims = Path.home() / "Claims"
    if home_claims.exists():
        return home_claims

    return REPO_ROOT / "Datasets" / "filesofdata" / "Claims"


def _resolve_work_root() -> Path:
    env_override = os.environ.get("NHA_WORK_ROOT", "").strip()
    if env_override:
        return Path(env_override)
    databank = Path("/mnt/databanks")
    if databank.exists() and os.access(databank, os.W_OK):
        return databank / "work"
    return REPO_ROOT / "pipeline_outputs"


CLAIMS_ROOT = _resolve_claims_root()
WORK_ROOT = _resolve_work_root()


RULE_EVALUATORS = {
    "MG064A": evaluate_page_mg064a,
    "MG006A": evaluate_page_mg006a,
    "SB039A": evaluate_page_sb039a,
    "SG039C": evaluate_page_sg039c,
}


def _evaluate_page(package_code: str, pr: PageResult) -> List[RuleResult]:
    fn = RULE_EVALUATORS.get(package_code)
    return fn(pr) if fn else []


def run_case(
    case_id: str,
    package_code: str,
    work_dir: Optional[Path] = None,
    ocr_backend: OCRBackend = OCRBackend.EASYOCR,
    llm_client: Optional[LLMClient] = None,
    use_arbiter: bool = False,
    extract_dates: bool = False,
    build_timeline: bool = True,
) -> Tuple[List[Dict[str, Any]], List[TimelineEvent]]:
    """Process a single case and return (rows, timeline).

    Optional LLM-driven phases (arbiter + date extraction) run only when a
    non-None ``llm_client`` is supplied along with the corresponding toggle.
    Timeline construction is pure regex/date logic and is on by default.
    """
    work_dir = work_dir or (WORK_ROOT / case_id)
    work_dir.mkdir(parents=True, exist_ok=True)

    # Locate case files
    case_dir = CLAIMS_ROOT / package_code / case_id
    files = iter_case_files(case_dir)
    rows: List[Dict[str, Any]] = []
    page_results: List[PageResult] = []

    for file_path in files:
        pages = extract_pages(file_path, case_id=case_id, out_dir=work_dir)
        for page in pages:
            ocr_result = run_ocr(page.image_path, backend=ocr_backend)
            quality = estimate_page_quality(page.image_path, ocr_result.text)
            doc_type, conf = classify_document_type(
                package_code, ocr_result, visual_tags={}
            )

            pr = PageResult(
                case_id=page.case_id,
                file_name=page.file_name,
                page_number=page.page_number,
                ocr=ocr_result,
                quality=quality,
                doc_type=doc_type,
                doc_type_confidence=conf,
            )

            # Stage C: LLM arbiter for unknown pages
            if (
                doc_type == "unknown"
                and use_arbiter
                and llm_client is not None
            ):
                candidates = PACKAGE_VALID_TYPES.get(package_code, [])
                arb_label, arb_conf, arb_ev = classify_via_llm_arbiter(
                    llm_client,
                    ocr_result.text,
                    candidates=candidates,
                    model="gemma-3-4b",
                )
                if arb_label and arb_label != "unknown":
                    pr.doc_type = arb_label
                    pr.doc_type_confidence = arb_conf
                    if arb_ev:
                        pr.evidence.extend(arb_ev)

            rule_results = _evaluate_page(package_code, pr)

            # Optional LLM date extraction: merge into pr.entities so
            # downstream rules & timeline can consume the dates.
            if extract_dates and llm_client is not None:
                target_fields = DATE_FIELDS_PER_PACKAGE.get(package_code, [])
                if target_fields:
                    page_text = ocr_result.text if ocr_result else ""
                    extracted = extract_dates_llm(
                        llm_client,
                        page_text,
                        target_fields=target_fields,
                        model="gemma-3-4b",
                    )
                    for k, v in extracted.items():
                        if v:
                            pr.entities[k] = v

            row = populate_row_for_package(package_code, pr, rule_results=rule_results)
            rows.append(row)
            page_results.append(pr)

    # Multi-page doc-rank grouping (rescue pages of same file if siblings classified)
    group_multipage_doc_rank(rows)

    # Optional episode timeline
    timeline: List[TimelineEvent] = []
    if build_timeline:
        timeline = build_episode_timeline(package_code, page_results)

    return rows, timeline


def run_batch(
    claims_root: Path = CLAIMS_ROOT,
    work_root: Path = WORK_ROOT,
    ocr_backend: OCRBackend = OCRBackend.EASYOCR,
    llm_client: Optional[LLMClient] = None,
    use_arbiter: bool = False,
    extract_dates: bool = False,
    build_timeline: bool = True,
) -> Dict[str, Tuple[List[Dict[str, Any]], List[TimelineEvent]]]:
    """Process every case under claims_root.

    Returns a mapping ``case_id -> (rows, timeline)``.
    """
    cases = discover_cases(claims_root)
    all_rows: Dict[str, Tuple[List[Dict[str, Any]], List[TimelineEvent]]] = {}
    for case_id, (_, pkg) in cases.items():
        case_work = work_root / case_id
        all_rows[case_id] = run_case(
            case_id,
            pkg,
            work_dir=case_work,
            ocr_backend=ocr_backend,
            llm_client=llm_client,
            use_arbiter=use_arbiter,
            extract_dates=extract_dates,
            build_timeline=build_timeline,
        )
    return all_rows
