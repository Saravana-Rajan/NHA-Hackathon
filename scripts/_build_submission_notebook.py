"""One-shot helper to (re)generate notebooks/nha_ps1_submission.ipynb.

Not part of the runtime pipeline; kept here so the notebook can be
regenerated deterministically from source.
"""
from __future__ import annotations

from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

REPO_ROOT = Path(__file__).resolve().parent.parent
NB_PATH = REPO_ROOT / "notebooks" / "nha_ps1_submission.ipynb"


CELL_1_MD = "# NHA PS-01 Submission - Clinical Document Classification Pipeline"

CELL_2_IMPORTS = '''\
# Ensure the repo root is on sys.path so `pipeline.*` and `rules.*` import
# both when this notebook runs locally and when uploaded to the NHA sandbox.
import os
import sys
from pathlib import Path

# The sandbox uploads the repo under a notebook-local path; locally the
# notebook sits at `<repo>/notebooks/`. Walk upward until we find a folder
# containing `pipeline/`.
_here = Path(os.getcwd()).resolve()
_candidates = [_here] + list(_here.parents)
REPO_ROOT = next(
    (p for p in _candidates if (p / "pipeline").is_dir()),
    _here,
)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

print("REPO_ROOT:", REPO_ROOT)

import json
'''

CELL_3_CREDS = '''\
# Credentials are read from the environment so we never embed secrets in
# the notebook. In the NHA sandbox set these via the notebook UI or shell.
NHA_CLIENT_ID = os.environ.get("NHA_CLIENT_ID")
NHA_CLIENT_SECRET = os.environ.get("NHA_CLIENT_SECRET")
print("have client id    :", bool(NHA_CLIENT_ID))
print("have client secret:", bool(NHA_CLIENT_SECRET))
'''

CELL_4_LLM = '''\
from pipeline.llm import LLMClient, LLMMode

if NHA_CLIENT_ID and NHA_CLIENT_SECRET:
    llm_client = LLMClient(
        mode=LLMMode.LIVE,
        client_id=NHA_CLIENT_ID,
        client_secret=NHA_CLIENT_SECRET,
        problem_statement=1,
    )
else:
    # No creds - fall back to DRY_RUN so the notebook still executes end-to-end.
    llm_client = LLMClient(mode=LLMMode.DRY_RUN, problem_statement=1)

print("LLM mode:", llm_client.mode.value)
'''

CELL_5_RUN = '''\
from pipeline.ocr import OCRBackend
from pipeline.run import run_batch, run_case, CLAIMS_ROOT, WORK_ROOT
from pipeline.ingest import discover_cases

# Full batch - EasyOCR primary backend.
# NOTE: `run_batch` may return either {case_id: rows} or {case_id: (rows, timeline)}
# once the Phase 3 timeline wiring lands. We normalise both below.
raw_results = run_batch(
    claims_root=CLAIMS_ROOT,
    work_root=WORK_ROOT,
    ocr_backend=OCRBackend.EASYOCR,
)

all_rows = {}
for case_id, result in raw_results.items():
    rows = result[0] if isinstance(result, tuple) else result
    all_rows[case_id] = rows

print(f"Processed {len(all_rows)} cases")
'''

CELL_6_EMIT = '''\
from pipeline.schemas import PACKAGE_CODES, PACKAGE_SCHEMAS

# Map each case to its package code via the claims directory tree.
case_packages = {
    case_id: pkg
    for case_id, (_, pkg) in discover_cases(CLAIMS_ROOT).items()
}

out_dir = REPO_ROOT / "submission_outputs"
out_dir.mkdir(parents=True, exist_ok=True)

buckets = {pkg: [] for pkg in PACKAGE_CODES}
for case_id, rows in all_rows.items():
    pkg = case_packages.get(case_id)
    if pkg is None and rows:
        pkg = rows[0].get("procedure_code")
    if pkg in buckets:
        buckets[pkg].extend(rows)

package_counts = {}
for pkg, rows in buckets.items():
    schema_keys = PACKAGE_SCHEMAS[pkg]
    projected = [{k: r.get(k) for k in schema_keys} for r in rows]
    out_path = out_dir / f"{pkg}.json"
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(projected, fh, indent=2, ensure_ascii=False)
    package_counts[pkg] = len(projected)
    print(f"wrote {out_path} ({len(projected)} rows)")
'''

CELL_7_TOKENS = '''\
print("=== LLM usage summary ===")
print(f"  total_input_tokens : {llm_client.total_input_tokens}")
print(f"  total_output_tokens: {llm_client.total_output_tokens}")
print(f"  cache_hits         : {llm_client.cache_hits}")
print(f"  cache_misses       : {llm_client.cache_misses}")
'''

CELL_8_MD = """\
## Submission complete

Per-package row counts are printed above. The JSON files live in
`submission_outputs/<PACKAGE>.json` and match the exact key order from
`pipeline/schemas.py :: PACKAGE_SCHEMAS`.

Next steps:
1. Spot-check a few rows per package (keys/order/values).
2. Zip `submission_outputs/` for upload to the NHA evaluation portal.
3. Confirm token usage is well under the 4M input cap per model.
"""


def build() -> None:
    nb = new_notebook()
    nb.cells = [
        new_markdown_cell(CELL_1_MD),
        new_code_cell(CELL_2_IMPORTS),
        new_code_cell(CELL_3_CREDS),
        new_code_cell(CELL_4_LLM),
        new_code_cell(CELL_5_RUN),
        new_code_cell(CELL_6_EMIT),
        new_code_cell(CELL_7_TOKENS),
        new_markdown_cell(CELL_8_MD),
    ]
    nb.metadata["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    nb.metadata["language_info"] = {"name": "python"}

    NB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with NB_PATH.open("w", encoding="utf-8") as fh:
        nbformat.write(nb, fh)
    print(f"wrote {NB_PATH} ({len(nb.cells)} cells)")


if __name__ == "__main__":
    build()
