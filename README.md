# NHA Hackathon — Problem Statement 01

Clinical Document Classification & Compliance to STG requirements.

## Quick start (local)

```bash
pip install -r requirements.txt
python -m pytest tests/ -q                # 150+ tests
python scripts/build_submission.py --dry-run
python scripts/build_submission.py        # full run with EasyOCR
```

## Quick start (NHA sandbox)

```bash
git clone <this-repo-url> NHA-Hackathon
cd NHA-Hackathon
pip install -r requirements.txt
jupyter lab notebooks/nha_ps1_submission.ipynb
```

Set `NHA_CLIENT_ID` and `NHA_CLIENT_SECRET` environment variables, then run all cells.

## Repo layout

```
pipeline/           # OCR, classifier, timeline, LLM wrappers, schemas
rules/              # package-specific STG rule engines
notebooks/          # Jupyter entrypoints (submission + sandbox skeletal)
scripts/            # scorecard, submission builder, threshold tuner
tests/              # 150+ unit tests
prompts/            # LLM prompt templates
labels/             # gold-label examples from official output guidelines
docs/               # submission README, data analysis
```

## Packages

- **MG064A** — Severe anemia
- **SG039C** — Laparoscopic cholecystectomy
- **MG006A** — Enteric fever
- **SB039A** — Total knee replacement

See `docs/SUBMISSION_README.md` for full submission instructions.
