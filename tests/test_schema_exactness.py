"""The ship-readiness test: every case produces schema-valid rows."""
from pathlib import Path
import pytest

from pipeline.run import run_case, CLAIMS_ROOT
from pipeline.validate import validate_output_rows
from pipeline.ingest import discover_cases


@pytest.mark.parametrize(
    "case_id,package_code",
    [
        (case_id, pkg)
        for case_id, (_, pkg) in discover_cases(CLAIMS_ROOT).items()
    ],
)
def test_case_produces_schema_valid_rows(case_id, package_code, tmp_path):
    rows, _ = run_case(case_id, package_code, work_dir=tmp_path)
    assert rows, f"Empty row list for {case_id}"
    ok, issues = validate_output_rows(package_code, rows)
    assert ok, f"Schema mismatch for {case_id}: {issues}"
