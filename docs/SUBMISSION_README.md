# NHA PS-01 Submission Guide

This document explains how to generate the per-package submission JSON
for the NHA Hackathon Problem Statement 1 pipeline, both locally and in
the official NHA sandbox.

## What gets produced

One JSON file per package, under `submission_outputs/`:

```
submission_outputs/
  MG064A.json   # severe anemia
  SG039C.json   # laparoscopic cholecystectomy
  MG006A.json   # enteric fever
  SB039A.json   # total knee replacement
```

Every object inside each file is a single page row and uses the exact
ordered key list from `pipeline/schemas.py :: PACKAGE_SCHEMAS`. Key
mismatches cause the NHA evaluator to reject the submission unevaluated,
so do not edit these files by hand.

## Run locally

Prerequisites: Python 3.10+, the packages in `requirements.txt`, and
(optionally) `NHA_CLIENT_ID` / `NHA_CLIENT_SECRET` in the environment
if you want the LLM-backed fields to be populated.

```bash
# smoke test - no OCR, no LLM, just verifies wiring and writes empty JSONs
python scripts/build_submission.py --dry-run

# full run - EasyOCR on every case in Datasets/filesofdata/Claims
python scripts/build_submission.py
```

Outputs land in `submission_outputs/` and the script prints row counts
and LLM token usage at the end.

## Run in the NHA sandbox

The NHA sandbox (`https://aaehackathonsbx.nhaad.in/notebook/...`) is a
hosted Jupyter environment with `NHAclient` pre-installed.

1. Upload the whole repo (zip, then extract) into the notebook workspace,
   preserving the `pipeline/`, `rules/`, `scripts/`, and `Datasets/`
   directories.
2. Open `notebooks/nha_ps1_submission.ipynb`.
3. In a shell cell or the notebook launcher, export credentials:
   ```bash
   export NHA_CLIENT_ID=...
   export NHA_CLIENT_SECRET=...
   ```
   (Or set them through the sandbox's environment UI.)
4. Run all cells top-to-bottom. Cell 2 walks up from the current
   directory to find the folder that contains `pipeline/`, so the
   notebook works whether the repo is at `/home/jovyan/repo` or
   anywhere else.
5. Download `submission_outputs/*.json` for upload to the evaluator.

## Expected output layout

After a successful run the repo looks like:

```
submission_outputs/
  MG064A.json  # list[dict] - one dict per page for MG064A cases
  SG039C.json
  MG006A.json
  SB039A.json
pipeline_outputs/
  <case_id>/   # per-case rasterized pages + OCR caches (intermediate)
```

`pipeline_outputs/` is the working directory used for cached page
images and OCR text - you do NOT need to ship it. Only the four files
under `submission_outputs/` are submitted.

## Token budget and caching

The NHA LLM proxy caps each allowed model (Ministral 3B/8B, Nemotron
Nano 30B, Gemma 3 4B/12B) at 4,000,000 input tokens for the whole
competition. To stay well under that ceiling:

- `pipeline/llm.py :: LLMClient` keeps an in-memory SHA-1 cache keyed
  on `(model, messages, metadata)`. Identical prompts within a run are
  served from cache and never re-billed. Watch `cache_hits` /
  `cache_misses` in Cell 7.
- Rule-based fields (vitals, dates, binary signs) are populated
  deterministically from OCR + regex - no LLM calls at all.
- LLM usage is scoped to classifier tie-breaks and a small set of
  narrative-extraction prompts. Prefer Ministral 3B for routing /
  yes-no questions; escalate to Gemma 3 12B or Nemotron Nano only for
  longer-context tasks.
- The client stamps every request with `problem_statement=1` metadata
  so the NHA proxy can account usage to the correct PS bucket.

If a run's `total_input_tokens` starts approaching the cap, review
`pipeline/llm_extract.py` prompts for length regressions and confirm
the cache is being hit (high `cache_hits`, low `cache_misses`).

## Troubleshooting

- **`ModuleNotFoundError: pipeline`**: Cell 2 failed to locate the repo
  root. Make sure `pipeline/` is a sibling of `notebooks/`.
- **LLM mode prints `dry_run` unexpectedly**: credentials are missing
  or empty. Set `NHA_CLIENT_ID` and `NHA_CLIENT_SECRET` and re-run
  Cells 3 and 4.
- **Schema rejection from NHA evaluator**: re-generate the JSONs; do
  not edit them by hand. `PACKAGE_SCHEMAS` in `pipeline/schemas.py` is
  the single source of truth for keys and order.
