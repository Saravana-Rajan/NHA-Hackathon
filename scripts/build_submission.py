"""Build per-package submission JSON files for NHA PS-01.

Mirrors the steps in `notebooks/nha_ps1_submission.ipynb` so the logic is
testable outside Jupyter. Run with `--dry-run` to exercise the flow without
invoking the live NHA LLM proxy or the full OCR pass.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Make the repo importable regardless of where the script is launched from.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def load_credentials() -> Tuple[str, str]:
    """Return (client_id, client_secret) from env, or ("", "") if absent."""
    return (
        os.environ.get("NHA_CLIENT_ID", "") or "",
        os.environ.get("NHA_CLIENT_SECRET", "") or "",
    )


def build_llm_client(dry_run: bool):
    """Construct the LLMClient in the appropriate mode."""
    from pipeline.llm import LLMClient, LLMMode

    client_id, client_secret = load_credentials()
    if dry_run or not (client_id and client_secret):
        return LLMClient(mode=LLMMode.DRY_RUN, problem_statement=1)
    return LLMClient(
        mode=LLMMode.LIVE,
        client_id=client_id,
        client_secret=client_secret,
        problem_statement=1,
    )


def coerce_rows(result: Any) -> List[Dict[str, Any]]:
    """Accept either `rows` or `(rows, timeline)` from run_case."""
    if isinstance(result, tuple):
        return result[0]
    return result


def run_pipeline(dry_run: bool) -> Dict[str, List[Dict[str, Any]]]:
    """Execute the full batch and return {case_id: rows}."""
    from pipeline.ocr import OCRBackend

    if dry_run:
        # Avoid heavy OCR and filesystem walks in dry-run.
        return {}

    from pipeline.run import run_batch

    results = run_batch(ocr_backend=OCRBackend.EASYOCR)
    return {case_id: coerce_rows(res) for case_id, res in results.items()}


def discover_case_packages() -> Dict[str, str]:
    """Return {case_id: package_code} from the claims tree."""
    try:
        from pipeline.ingest import discover_cases
        from pipeline.run import CLAIMS_ROOT
    except Exception:
        return {}

    try:
        cases = discover_cases(CLAIMS_ROOT)
    except Exception:
        return {}
    return {case_id: pkg for case_id, (_, pkg) in cases.items()}


def group_rows_by_package(
    all_rows: Dict[str, List[Dict[str, Any]]],
    case_packages: Dict[str, str],
) -> Dict[str, List[Dict[str, Any]]]:
    """Fan case-level rows out into per-package buckets."""
    from pipeline.schemas import PACKAGE_CODES

    buckets: Dict[str, List[Dict[str, Any]]] = {pkg: [] for pkg in PACKAGE_CODES}
    for case_id, rows in all_rows.items():
        pkg = case_packages.get(case_id)
        if not pkg:
            # Fallback: infer from row payload if available.
            if rows and isinstance(rows[0], dict):
                pkg = rows[0].get("procedure_code")
        if pkg in buckets:
            buckets[pkg].extend(rows)
    return buckets


def filter_to_schema(
    rows: List[Dict[str, Any]], package_code: str
) -> List[Dict[str, Any]]:
    """Project each row to the exact ordered key list in PACKAGE_SCHEMAS."""
    from pipeline.schemas import PACKAGE_SCHEMAS

    schema_keys = PACKAGE_SCHEMAS[package_code]
    out: List[Dict[str, Any]] = []
    for row in rows:
        projected = {k: row.get(k) for k in schema_keys}
        out.append(projected)
    return out


def write_submissions(
    buckets: Dict[str, List[Dict[str, Any]]], out_dir: Path
) -> Dict[str, int]:
    """Write one JSON file per package. Returns {package: row_count}."""
    out_dir.mkdir(parents=True, exist_ok=True)
    counts: Dict[str, int] = {}
    for pkg, rows in buckets.items():
        projected = filter_to_schema(rows, pkg)
        path = out_dir / f"{pkg}.json"
        with path.open("w", encoding="utf-8") as fh:
            json.dump(projected, fh, indent=2, ensure_ascii=False)
        counts[pkg] = len(projected)
    return counts


def print_token_summary(llm_client) -> None:
    print("=== LLM usage ===")
    print(f"  total_input_tokens : {getattr(llm_client, 'total_input_tokens', 0)}")
    print(f"  total_output_tokens: {getattr(llm_client, 'total_output_tokens', 0)}")
    print(f"  cache_hits         : {getattr(llm_client, 'cache_hits', 0)}")
    print(f"  cache_misses       : {getattr(llm_client, 'cache_misses', 0)}")


def _default_out_dir() -> Path:
    """Pick the default output dir, preferring NHA-mounted paths."""
    env_override = os.environ.get("NHA_OUTPUT_DIR", "").strip()
    if env_override:
        return Path(env_override)
    if Path("/mnt/databanks").exists():
        return Path("/mnt/databanks/output")
    return REPO_ROOT / "submission_outputs"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build NHA PS-01 submission JSON files.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip OCR/LLM work; emit empty per-package JSON files for smoke-testing.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=_default_out_dir(),
        help="Output directory for <PACKAGE>.json files.",
    )
    args = parser.parse_args()

    print(f"[submission] repo_root = {REPO_ROOT}")
    print(f"[submission] out_dir   = {args.out}")
    print(f"[submission] dry_run   = {args.dry_run}")

    llm_client = build_llm_client(dry_run=args.dry_run)
    print(f"[submission] llm mode  = {llm_client.mode.value}")

    all_rows = run_pipeline(dry_run=args.dry_run)
    case_packages = discover_case_packages()
    buckets = group_rows_by_package(all_rows, case_packages)
    counts = write_submissions(buckets, args.out)

    print("[submission] per-package row counts:")
    for pkg, n in counts.items():
        print(f"  {pkg}: {n} rows -> {(args.out / f'{pkg}.json').as_posix()}")

    print_token_summary(llm_client)
    print("[submission] done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
