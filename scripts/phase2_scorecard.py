"""Phase-2 scorecard: per-package, per-field positive-fire counts +
schema validity + token usage placeholder."""
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline.run import run_batch
from pipeline.schemas import BINARY_FIELDS_PER_PACKAGE
from pipeline.validate import validate_output_rows

if __name__ == "__main__":
    results = run_batch()
    print("\n=== Phase 2 Scorecard ===")
    print(f"Cases processed: {len(results)}")
    total_rows = sum(len(rows) for rows, _ in results.values())
    print(f"Total rows emitted: {total_rows}\n")

    per_pkg_rows = defaultdict(list)
    for case_id, (rows, _) in results.items():
        if not rows:
            continue
        pkg = rows[0]["procedure_code"]
        per_pkg_rows[pkg].extend(rows)

    for pkg, rows in sorted(per_pkg_rows.items()):
        ok, issues = validate_output_rows(pkg, rows)
        flag_stats = {}
        for f in BINARY_FIELDS_PER_PACKAGE[pkg]:
            positives = sum(1 for r in rows if int(r.get(f, 0) or 0) == 1)
            flag_stats[f] = (positives, len(rows))
        extra_pos = sum(1 for r in rows if int(r.get("extra_document", 0) or 0) == 1)
        rank99 = sum(1 for r in rows if int(r.get("document_rank", 0) or 0) == 99)
        print(f"  {pkg}: {len(rows)} rows, schema_ok={ok}, extra_doc={extra_pos}, rank99={rank99}")
        for f, (p, n) in sorted(flag_stats.items()):
            if p > 0:
                print(f"    {f}: {p}/{n} positive")
    print("\nDone.")
