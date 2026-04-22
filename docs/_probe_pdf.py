"""Probe a single PDF to understand why no text is extracted."""
import fitz
import os
import sys

BASE = r"C:\Users\sarav\NHA-Hackathon\Datasets\filesofdata\Claims"

# Probe a handful
samples = [
    ("MG006A", "CMJAY_TR_CMJAY_2025_R3_1022010623", "000585__CMJAY_TR_CMJAY_2025_R3_1022010623__SUDHAN_DB.pdf"),
    ("MG006A", "CMJAY_TR_CMJAY_2025_R3_1022010623", "000591__CMJAY_TR_CMJAY_2025_R3_1022010623__SUDAM.pdf"),
    ("MG064A", "PMJAY_CG_2025_R2_2026031610017035", "000982__PMJAY_CG_2025_R2_2026031610017035__INVESTIGATION.pdf"),
    ("MG064A", "PMJAY_CG_2025_R2_2026031610017035", "000983__PMJAY_CG_2025_R2_2026031610017035__CASESHEET.pdf"),
    ("MG064A", "PMJAY_CG_2025_R2_2026031610017035", "000988__PMJAY_CG_2025_R2_2026031610017035__DIS-MEDICINE.pdf"),
    ("SB039A", "CMJAY_TR_CMJAY_2025_R3_1021740400", "000522__CMJAY_TR_CMJAY_2025_R3_1021740400__INITIAL_ASSESSMENT.pdf"),
    ("SB039A", "CMJAY_TR_CMJAY_2025_R3_1021740400", "000524__CMJAY_TR_CMJAY_2025_R3_1021740400__DIS.pdf"),
    ("SB039A", "CMJAY_TR_CMJAY_2025_R3_1021740400", "000525__CMJAY_TR_CMJAY_2025_R3_1021740400__OT_NOTE.pdf"),
    ("SB039A", "PMJAY_DL_S_G_R1_1021048216", "000189__PMJAY_DL_S_G_R1_1021048216__Sheela-81-100_11zon.pdf"),
    ("SG039C", "PMJAY_CG_2025_R2_1022167154", "000633__PMJAY_CG_2025_R2_1022167154__Discharge_Summary.pdf"),
    ("SG039C", "PMJAY_CG_2025_R2_1022167154", "000634__PMJAY_CG_2025_R2_1022167154__Detailed_operative_notes.pdf"),
]

for pkg, case, fn in samples:
    p = os.path.join(BASE, pkg, case, fn)
    print(f"\n==== {fn}  ====")
    print(f"   size: {os.path.getsize(p)/1024:.1f} KB")
    with fitz.open(p) as doc:
        print(f"   pages: {doc.page_count}")
        print(f"   metadata: {doc.metadata}")
        for i, page in enumerate(doc):
            text = page.get_text("text") or ""
            blocks = page.get_text("blocks") or []
            images = page.get_images(full=True) or []
            drawings = page.get_drawings() or []
            print(f"   p{i}: text_len={len(text)} blocks={len(blocks)} images={len(images)} drawings={len(drawings)}")
            if text.strip():
                print(f"      snippet: {text[:200]!r}")
            if i > 2: break
