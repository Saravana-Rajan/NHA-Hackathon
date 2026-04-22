"""Sweep DOCTYPE_RULES thresholds and pick the value that maximises per-doctype F1.

Output:
    stdout: a summary table (doctype, best_threshold, F1_at_best)
    file:   pipeline/tuned_thresholds.json  (loaded by pipeline.classifier at import)

Design:
    1. Load labels/example_rows.json as gold. Rows are keyed by (package_code,
       case_id, page_number).
    2. For each package, find cases on disk whose case_id matches a gold
       case_id (the gold "case_id" may use "/" separators while the filesystem
       uses "_"; we match on a normalised form).
    3. For every matched case we run a minimal OCR+classify pass to produce
       predicted rows comparable to gold rows: for each doctype field we
       populate a 0/1 based on the classifier's chosen label.
    4. For each doctype that has an entry in DOCTYPE_RULES we sweep its
       threshold from 0.30 to 0.95 step 0.05, re-classify, compute field-level
       F1 via pipeline.validate.compute_field_level_f1 and record the argmax.
    5. We skip any doctype whose gold has 0 positives or 0 negatives across
       the matched pages (printing "insufficient data for <doctype>").

OCR backend is NOOP and the LLM client is in DRY_RUN mode so this script is
safe to run without network/GPU. Real OCR tuning can be bolted on later by
swapping the backend argument.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline import classifier as classifier_mod
from pipeline.classifier import DOCTYPE_RULES, PACKAGE_VALID_TYPES, classify_document_type
from pipeline.ingest import extract_pages, iter_case_files
from pipeline.llm import LLMClient, LLMMode
from pipeline.ocr import OCRBackend, run_ocr, extract_text_from_pdf_page
from pipeline.models import PageOCR
from pipeline.schemas import BINARY_FIELDS_PER_PACKAGE
from pipeline.validate import compute_field_level_f1

try:
    from pipeline.run import run_case  # noqa: F401  (imported for parity with task spec)
except Exception:
    run_case = None

LABELS_PATH = REPO_ROOT / "labels" / "example_rows.json"
CLAIMS_ROOT = REPO_ROOT / "Datasets" / "filesofdata" / "Claims"
WORK_ROOT = REPO_ROOT / "pipeline_outputs" / "_tuning"
TUNED_OUT_PATH = REPO_ROOT / "pipeline" / "tuned_thresholds.json"

PACKAGES = ["MG064A", "SG039C", "MG006A", "SB039A"]


def _norm_case_id(case_id: str) -> str:
    """Fold path separators so gold ids like 'MAV/GJ/R3/...' match dir 'MAV_GJ_R3_...'."""
    return (case_id or "").replace("/", "_").replace("-", "_").replace(" ", "_").strip("_").lower()


def _call_run_case(case_id: str, package_code: str) -> List[Dict[str, Any]]:
    """Call pipeline.run.run_case, accepting tuple (rows, timeline) or plain list."""
    if run_case is None:
        return []
    work_dir = WORK_ROOT / case_id.replace("/", "_")
    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = run_case(
            case_id=case_id,
            package_code=package_code,
            work_dir=work_dir,
            ocr_backend=OCRBackend.NOOP,
        )
    except TypeError:
        # Older signature without ocr_backend kw
        result = run_case(case_id, package_code, work_dir)
    if isinstance(result, tuple):
        rows = result[0]
    else:
        rows = result
    return list(rows or [])


def _collect_page_ocr_for_case(case_id: str, package_code: str) -> List[Tuple[int, PageOCR, str]]:
    """Return list of (page_number, PageOCR, file_name) for each page in a case.

    Uses PDF text-layer extraction where possible (fast, no OCR needed). Falls
    back to NOOP (empty text) if extraction fails.
    """
    case_dir = CLAIMS_ROOT / package_code / case_id
    files = iter_case_files(case_dir)
    work_dir = WORK_ROOT / case_id.replace("/", "_")
    work_dir.mkdir(parents=True, exist_ok=True)
    out: List[Tuple[int, PageOCR, str]] = []
    running_page = 0
    for fp in files:
        pages = extract_pages(fp, case_id=case_id, out_dir=work_dir)
        for pg in pages:
            running_page += 1
            ocr: PageOCR
            if pg.source_pdf_path:
                ocr = extract_text_from_pdf_page(pg.source_pdf_path, pg.page_number)
            else:
                # image file -> NOOP text
                ocr = run_ocr(pg.image_path, backend=OCRBackend.NOOP)
            out.append((running_page, ocr, pg.file_name))
    return out


def _gold_rows_for_package(
    gold: Dict[str, List[Dict[str, Any]]],
    package_code: str,
) -> Dict[str, List[Dict[str, Any]]]:
    """Group gold rows by normalised case_id."""
    by_case: Dict[str, List[Dict[str, Any]]] = {}
    for row in gold.get(package_code, []):
        cid = _norm_case_id(row.get("case_id", ""))
        by_case.setdefault(cid, []).append(row)
    return by_case


def _find_matching_cases(package_code: str, gold_case_ids: List[str]) -> List[str]:
    """Return list of real case directory names for this package that match a gold case_id."""
    pkg_dir = CLAIMS_ROOT / package_code
    if not pkg_dir.exists():
        return []
    wanted = {_norm_case_id(c) for c in gold_case_ids}
    matches: List[str] = []
    for case_dir in sorted(pkg_dir.iterdir()):
        if not case_dir.is_dir():
            continue
        if _norm_case_id(case_dir.name) in wanted:
            matches.append(case_dir.name)
    return matches


def _classify_pages(package_code: str, pages: List[Tuple[int, PageOCR, str]]) -> Dict[int, str]:
    """Classify every page and return page_number -> doc_type_label."""
    out: Dict[int, str] = {}
    for page_number, ocr, _file_name in pages:
        label, _conf = classify_document_type(package_code, ocr, visual_tags={})
        out[page_number] = label
    return out


def _rows_from_labels(
    package_code: str,
    page_labels: Dict[int, str],
) -> List[Dict[str, Any]]:
    """Build skeletal rows for F1 computation: one binary per doctype field per page."""
    binary_fields = BINARY_FIELDS_PER_PACKAGE[package_code]
    rows: List[Dict[str, Any]] = []
    for page_number, label in page_labels.items():
        row: Dict[str, Any] = {"page_number": page_number}
        for f in binary_fields:
            row[f] = 1 if f == label else 0
        rows.append(row)
    return rows


def _sweep_thresholds_for_doctype(
    package_code: str,
    doctype: str,
    pages_per_case: Dict[str, List[Tuple[int, PageOCR, str]]],
    gold_by_case: Dict[str, List[Dict[str, Any]]],
) -> Tuple[float, float]:
    """Return (best_threshold, best_f1) for a single doctype."""
    original_threshold = DOCTYPE_RULES[doctype]["threshold"]
    thresholds = [round(0.30 + 0.05 * i, 2) for i in range(14)]  # 0.30 .. 0.95

    best_t = original_threshold
    best_f1 = -1.0
    try:
        for t in thresholds:
            DOCTYPE_RULES[doctype]["threshold"] = t

            predicted_rows: List[Dict[str, Any]] = []
            gold_rows: List[Dict[str, Any]] = []
            for case_id_norm, pages in pages_per_case.items():
                labels = _classify_pages(package_code, pages)
                preds = _rows_from_labels(package_code, labels)
                for r in preds:
                    r["_case"] = case_id_norm
                predicted_rows.extend(preds)
                for gr in gold_by_case.get(case_id_norm, []):
                    gold_rows.append({**gr, "_case": case_id_norm})

            # Align by (case, page_number): rewrite page_number to a unique composite
            def _pg(row: Dict[str, Any]) -> int:
                return hash((row.get("_case"), row.get("page_number"))) & 0x7FFFFFFF

            pred_aligned = [{**r, "page_number": _pg(r)} for r in predicted_rows]
            gold_aligned = [{**r, "page_number": _pg(r)} for r in gold_rows]

            metrics = compute_field_level_f1(package_code, pred_aligned, gold_aligned)
            f1 = metrics.get(doctype, {}).get("f1", 0.0)
            if f1 > best_f1:
                best_f1 = f1
                best_t = t
    finally:
        DOCTYPE_RULES[doctype]["threshold"] = original_threshold

    return best_t, max(0.0, best_f1)


def _has_enough_data(doctype: str, gold_by_case: Dict[str, List[Dict[str, Any]]]) -> bool:
    """Require >=1 positive and >=1 negative label for the doctype across all gold rows."""
    positives = 0
    negatives = 0
    for rows in gold_by_case.values():
        for r in rows:
            v = int(r.get(doctype, 0) or 0)
            if v == 1:
                positives += 1
            else:
                negatives += 1
    return positives >= 1 and negatives >= 1


def main() -> int:
    if not LABELS_PATH.exists():
        print(f"ERROR: {LABELS_PATH} not found.", file=sys.stderr)
        return 1

    with open(LABELS_PATH, "r", encoding="utf-8") as f:
        gold: Dict[str, List[Dict[str, Any]]] = json.load(f)

    # Warm up the LLM client in DRY_RUN mode (even though we don't call it, the
    # task asks us to construct one so downstream tuning can reuse it.)
    _llm = LLMClient(mode=LLMMode.DRY_RUN)

    best_per_doctype: Dict[str, Tuple[float, float]] = {}
    table_rows: List[Tuple[str, str, float, float, str]] = []

    for package_code in PACKAGES:
        gold_by_case = _gold_rows_for_package(gold, package_code)
        gold_case_ids = list(gold_by_case.keys())
        real_cases = _find_matching_cases(package_code, gold_case_ids)
        print(f"[{package_code}] gold cases={gold_case_ids} matched dirs={real_cases}")

        # Collect OCR per matched case. If nothing matches, we still loop so
        # we can emit 'insufficient data' messages for the package's doctypes.
        pages_per_case: Dict[str, List[Tuple[int, PageOCR, str]]] = {}
        for real_case_id in real_cases:
            pages = _collect_page_ocr_for_case(real_case_id, package_code)
            pages_per_case[_norm_case_id(real_case_id)] = pages

        candidate_doctypes = [
            dt for dt in PACKAGE_VALID_TYPES.get(package_code, [])
            if dt in DOCTYPE_RULES
        ]

        for doctype in candidate_doctypes:
            if not _has_enough_data(doctype, gold_by_case):
                print(f"  insufficient data for {doctype}")
                continue
            if not pages_per_case:
                print(f"  insufficient data for {doctype} (no runnable cases)")
                continue
            best_t, best_f1 = _sweep_thresholds_for_doctype(
                package_code, doctype, pages_per_case, gold_by_case,
            )
            prev = best_per_doctype.get(doctype)
            if prev is None or best_f1 > prev[1]:
                best_per_doctype[doctype] = (best_t, best_f1)
            table_rows.append((package_code, doctype, best_t, best_f1,
                               f"cases={len(pages_per_case)}"))

    # Summary table
    print("\n=== Threshold Tuning Summary ===")
    print(f"{'package':<8} {'doctype':<22} {'best_thr':>9} {'F1':>8}  notes")
    for pkg, dt, t, f1, notes in table_rows:
        print(f"{pkg:<8} {dt:<22} {t:>9.2f} {f1:>8.3f}  {notes}")

    print("\n=== Tuned Thresholds (best across packages per doctype) ===")
    tuned: Dict[str, float] = {dt: t for dt, (t, _f1) in best_per_doctype.items()}
    for dt, t in sorted(tuned.items()):
        print(f"  {dt}: {t:.2f}  (F1={best_per_doctype[dt][1]:.3f})")

    TUNED_OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TUNED_OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(tuned, f, indent=2, sort_keys=True)
    print(f"\nWrote {TUNED_OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
