"""Phase-1 scorecard: counts of rows per case, schema validity."""
import json
import sys
from pathlib import Path

# Ensure the repo root is on sys.path so `pipeline` is importable when
# invoked as `python scripts/phase1_scorecard.py`.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from pipeline.run import run_batch
from pipeline.validate import validate_output_rows

if __name__ == "__main__":
    results = run_batch()
    print(f"Cases processed: {len(results)}")
    total_rows = sum(len(rows) for rows, _ in results.values())
    print(f"Total rows emitted: {total_rows}")
    per_pkg_counts = {}
    for case_id, (rows, _) in results.items():
        pkg = rows[0]["procedure_code"] if rows else "?"
        per_pkg_counts.setdefault(pkg, 0)
        per_pkg_counts[pkg] += len(rows)
    print("Rows per package:", per_pkg_counts)

    bad = 0
    for case_id, (rows, _) in results.items():
        pkg = rows[0]["procedure_code"] if rows else "?"
        ok, _issues = validate_output_rows(pkg, rows)
        if not ok:
            bad += 1
            print(f"  SCHEMA FAIL: {case_id}")
    print(f"Schema-valid cases: {len(results) - bad}/{len(results)}")

    # Dump a sample row per package for eyeball
    seen = set()
    for case_id, (rows, _) in results.items():
        if not rows:
            continue
        pkg = rows[0]["procedure_code"]
        if pkg in seen:
            continue
        seen.add(pkg)
        print(f"\nSample row for {pkg} ({case_id}, page 1):")
        print(json.dumps(rows[0], indent=2))
