# NHA Hackathon — Claim Data Analysis

Scope: all 4 packages under `Datasets/filesofdata/Claims/` (40 cases total) and the rasterized outputs under `pipeline_outputs/`. Generated 2026-04-22.

---

## 1. Dataset shape

### Cases per package (all four packages have exactly 10 cases)

| Package | Domain             | Cases | Total files | Avg files/case | Min | Max |
|---------|--------------------|-------|-------------|----------------|-----|-----|
| MG006A  | Enteric fever      | 10    | 139         | 13.9           | 3   | 28  |
| MG064A  | Anemia             | 10    | 114*        | 11.4           | 5   | 29  |
| SB039A  | TKR                | 10    | 98          | 9.8            | 7   | 13  |
| SG039C  | Cholecystectomy    | 10    | 93          | 9.3            | 5   | 21  |
| **All** |                    | **40**| **444**     | **11.1**       | 3   | 29  |

\* MG064A count includes 10 `.DS_Store` macOS stray files that should be filtered.

### File type distribution

| Package | .pdf | .jpg | .jpeg | other |
|---------|-----:|-----:|------:|------:|
| MG006A  | 80   | 24   | 35    | 0     |
| MG064A  | 70   | 29   | 5     | 10 (.DS_Store) |
| SB039A  | 45   | 36   | 17    | 0     |
| SG039C  | 50   | 31   | 12    | 0     |
| **Total** | **245** | **120** | **69** | **10** |

- 55% of source files are PDFs, 45% are loose images (.jpg/.jpeg). No `.png` sources.
- Implication: the pipeline must rasterize PDFs *and* ingest standalone images. Both paths are already exercised by `pipeline_outputs/`.

---

## 2. Per-package filename patterns

Source filenames follow the convention `NNNNNN__<CASE_ID>__<HOSPITAL_LABEL>.<ext>`. The **hospital label** is what hospitals typed and it is the only reusable signal.

### MG006A (enteric fever) — sampled labels

`SUDHAN_DB.pdf`, `babyofjesminadarlong.pdf`, `Investigation_Jesmina_darlong_12.pdf`, `Cn_Jesmina_darlong_12.pdf`, `DC_JESMINA_DARLONG_14.pdf`, `CBC.pdf`, `CASE_SHEET.pdf`, `ICP_CHART.pdf`, `BEDSIDE_12.jpg`, `INTAKE_OUTPUT.pdf`, `SUMMARY.pdf`, `Pt_avtar_singh_blood_investigation_report.pdf`, `ENHANCEMENT*`, `ENC*`, `PH*`

Observed recurring tokens: `PT` (13), `ENHANCEMENT` (12), `ENC` (8), `BEDSIDE` (6), `DC`/`DP` (5), `PH` (5), `INVES*` (4), `CBC`, `CASE_SHEET`, `ICP`, `INTAKE_OUTPUT`.

**Patterns:** `CBC`, `INVESTIGATION*`, `BEDSIDE*` (vitals/nurse chart), `CASE_SHEET`/`CN` (clinical notes), `DC`/`DP`/`SUMMARY` (discharge summary), `ICP` (indoor-case-paper), `PH` (pharmacy).

### MG064A (anemia)

`usg.jpeg`, `ALL_REPORTS.pdf`, `INV.pdf`, `ICP.pdf`, `NOTES.pdf`, `DISC.pdf`, `TREATMENT.pdf`, `CBC.pdf`, `RFT.pdf`, `FEEDBACK_FORM.pdf`, `ICP_NOTES.pdf`, `INTAKE_OUTPUT.pdf`, `MS_DIS.jpg`, `ADIT.jpeg`, `JUSTIFICATION*` (5), `DEVI*` (9, patient name).

Tokens: `DISCHARGE` (7), `JUSTIFICATION` (5), `ICP` (4), `FEEDBACK` (3), `BILL` (3), `DIS*`, `NOTES*`, `TREATMENT`, `CBC`.

**Patterns:** `CBC`, `ALL_REPORTS`/`INV` (bundled investigations), `ICP*` (indoor case), `NOTES`/`CN` (clinical notes), `DIS*`/`DISCHARGE*` (discharge summary), `TREATMENT`, `JUSTIFICATION` (claim justification = extra).

### SB039A (TKR)

`INITIAL_ASSESSMENT.pdf`, `XRAY.jpeg`, `POST_XRAY.jpeg`, `OT_NOTE.pdf`, `DIS.pdf`, `FEEDBACK.jpeg`, `BARCODE.jpg`, `X_RAY.pdf`, `CS.pdf`, `icp.pdf`, `SDS.pdf`, `DC.jpg`, `Sheela-1-20_11zon.pdf` (paginated chunks), `Pravakar_naik_feedback.pdf`, `IMG20260328*.jpg` (phone photos).

Tokens: patient-name prefixes dominate (`SHEELA` 13, `PRAVAKAR` 10, `PUSHPA` 9), then `X`/`XRAY`, `INITIAL`, `DIS`, `IMG2026*`, `OT`, `FEED`.

**Patterns:** `XRAY`/`X_RAY`/`POST_XRAY` (imaging; `POST*` indicates post-op), `OT_NOTE`/`OT` (operative notes), `INITIAL_ASSESSMENT`/`CS` (clinical notes), `SDS`/`DIS`/`DC` (discharge), `FEEDBACK`, `IMG20260*` (raw phone photos → likely photo_evidence or implant sticker), `BARCODE`.

### SG039C (cholecystectomy)

`CLINICAL_NOTE.pdf`, `usg.pdf`, `USG.jpeg`, `discharge_summary.pdf`, `HOSPITAL_BILL.pdf`, `pharmacy.pdf`, `OPERATIVE_NOTE.pdf`, `OT_NOTE*`, `OTNOTES1`, `CBC.jpeg`, `ENDOSCOPY.jpeg`, `RFTLFT.jpg`, `DFORM.jpg`, `CHOI*` (5, likely cholecystectomy/patient), `FEEDBACK_14567.jpeg`.

Tokens: `DISCHARGE` (9), `USG` (6), `CLINICAL` (5), `CHOI` (5), `FEEDBACK` (4), `DIS`/`DFORM`, `CBC` (3), `OT`/`OTNOTE*`.

**Patterns:** `USG`/`ULTRASOUND` (unique & strong), `CLINICAL_NOTE*`, `OPERATIVE_NOTE`/`OT_NOTE*`/`OTNOTES*`, `DISCHARGE*`/`DIS*`/`DFORM`, `RFTLFT`/`LFT` (liver function), `CBC`, `HOSPITAL_BILL`/`PHARMACY` (admin → extra).

---

## 3. OCR feasibility check

`pipeline_outputs/` contains one subfolder per case_id, each holding pre-rasterized PNGs of the form `NNNNNN__<case>__<label>__pNNN.png`.

| Package | Cases rasterized | PNG pages |
|---------|------------------|-----------|
| MG006A  | 10               | 397       |
| MG064A  | 10               | 317       |
| SB039A  | 10               | 406       |
| SG039C  | 10               | 288       |
| **Total** | **40**         | **1408**  |

All 40 cases are fully rasterized. Average ~35 pages/case; the classifier has to fire on ~1,400 pages in total.

### Size-based feasibility (proxy for legibility)

Across all 1408 PNGs: **min 21.2 KB, median 461 KB, mean 721 KB, max 5.6 MB**. Per-package spot checks:

- **MG006A:** 435 KB – 3.6 MB (e.g. `SUDHAN_DB__p001.png` = 1.94 MB, `CASE__p001.png` = 3.6 MB) — page scans.
- **MG064A:** 159 KB – 863 KB (e.g. `ALL_REPORTS__p001.png` = 347 KB, `print_report__p001.png` = 159 KB) — some lower-DPI scans; smallest are OK but tight.
- **SB039A:** 35 KB – 700 KB (e.g. `INITIAL_ASSESSMENT__p002.png` = 35 KB is suspicious/near-empty; `CS__p001.png` = 700 KB is healthy).
- **SG039C:** 229 KB – 2.6 MB (e.g. `usg__p001.png` = 2.6 MB — USG plate; `OPERATIVE_NOTE__p001.png` = 1.5 MB).

Conclusion: the rasters are real scanned clinical pages, sizes are in the typical OCR-feasible range (>150 KB for text pages). A minority of ~20–50 KB pages in SB039A need flagging as possibly blank/degraded.

---

## 4. Gold label coverage

`labels/example_rows.json` only contains **schema templates** plus placeholder rows keyed by synthetic `case_id` values (`C1`, `C2`) — not real case_ids. The single real id referenced is `MAV/GJ/R3/2026032310030008` (SG039C), which corresponds to the actual folder `MAV_GJ_R3_2026032310030008` (slashes → underscores).

| Package | Gold case_ids present                                     | Matches a real folder?                      |
|---------|-----------------------------------------------------------|---------------------------------------------|
| MG006A  | `C1`, `C2` (placeholders)                                 | No — template rows only                     |
| MG064A  | `C1`, `C2` (placeholders)                                 | No — template rows only                     |
| SB039A  | `C1`, `C2` (placeholders)                                 | No — template rows only                     |
| SG039C  | `MAV/GJ/R3/2026032310030008`                              | Yes → `MAV_GJ_R3_2026032310030008`          |

**Flag:** `labels/example_rows.json` is not usable as gold truth. It is an example schema. None of the 40 real case_ids (except the one SG039C example) are annotated. A per-page gold set will have to be created or sourced before accuracy metrics can be computed.

Real case_ids that currently have **no** gold label (all 40 except the one SG039C example). See `Datasets/filesofdata/Claims/<PACKAGE>/` for the full list.

---

## 5. Recommended classifier improvements (filename-based)

These complement the OCR keyword rules in `pipeline/classifier.py::DOCTYPE_RULES`. Apply as a strong prior when the OCR score is close to threshold.

### Global (all packages)

1. If filename stem matches `/^(DIS|DISC|DC|DSCH|DISCHARGE|SUMMARY|SDS|DFORM)(_|\b)/i` → boost `discharge_summary` by +0.7.
2. If filename stem matches `/^(CN|CLINICAL|CASE_?SHEET|NOTES?|INITIAL_?ASSESSMENT)(_|\b)/i` → boost `clinical_notes` by +0.7.
3. If filename stem matches `/^(ICP|INTAKE_?OUTPUT|BEDSIDE|IPD)(_|\b)/i` → boost `indoor_case` / `vitals_treatment` by +0.6.
4. If filename stem matches `/FEEDBACK|BARCODE|BILL|PHARMACY|JUSTIFICATION/i` → boost `extra_document` by +0.6.

### MG006A (enteric fever)

5. `/CBC/i` → `investigation_pre|post` (+0.7). `/BEDSIDE|INTAKE_?OUTPUT|ICP/i` → `vitals_treatment` (+0.7).

### MG064A (anemia)

6. `/CBC|HB|HEMO|HAEMO/i` → `cbc_hb_report` (+0.7). `/ALL_?REPORTS|INV\b/i` → `cbc_hb_report` or `treatment_details` (+0.4, ambiguous).

### SG039C (cholecystectomy)

7. `/USG|ULTRASOUND|SONO/i` → `usg_report` (+0.8, very distinctive). `/RFTLFT|LFT|SGPT|SGOT/i` → `lft_report` (+0.7). `/OT_?NOTES?|OPERATIVE_?NOTE/i` → `operative_notes` (+0.8).

### SB039A (TKR)

8. `/X_?RAY|XRAY|RADIOGRAPH/i` + `/POST|PO\b/i` → `post_op_xray` (+0.8); else → `xray_ct_knee` (+0.7).
9. `/^IMG\d{8}/i` (phone photos) → `post_op_photo` or `photo_evidence` (+0.5, context-dependent).
10. `/IMPLANT|STICKER|INVOICE/i` → `implant_invoice` (+0.8).

### Implementation note

Add an optional `filename_regex` field per rule in `DOCTYPE_RULES`, or introduce a secondary `FILENAME_PRIORS` dict consulted by the scorer. Either way, filename priors should **augment** (not replace) OCR evidence and must be down-weighted when OCR strongly contradicts them.
