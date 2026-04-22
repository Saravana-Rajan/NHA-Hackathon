"""Replay the organizer example rows through our pipeline.

The output-ps-1.pdf contains 2 sample rows per package.  These are captured
verbatim in labels/example_rows.json.  This test doesn't run the full pipeline
(we don't have the matching original PDFs); instead it verifies that our
schema + key order matches exactly.
"""
import json
from pathlib import Path
from pipeline.validate import validate_output_rows
from pipeline.schemas import PACKAGE_SCHEMAS

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_PATH = REPO_ROOT / "labels" / "example_rows.json"


def test_example_rows_schema_matches():
    with open(EXAMPLES_PATH) as f:
        examples = json.load(f)
    for pkg, rows in examples.items():
        # SB039A example uses "s3_link" alias; our schema uses "link".
        # Translate it before validation.
        if pkg == "SB039A":
            rows = [{**r, "link": r.pop("s3_link", r.get("link", ""))} for r in rows]
            # reorder keys to match schema
            schema = PACKAGE_SCHEMAS[pkg]
            rows = [{k: r.get(k) for k in schema} for r in rows]
        ok, issues = validate_output_rows(pkg, rows)
        assert ok, f"{pkg} example rows fail schema: {issues}"
