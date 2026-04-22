"""Extract text from claim PDFs + analyze filename tokens."""
import fitz
import json
import os
import re
from collections import Counter, defaultdict

BASE = r"C:\Users\sarav\NHA-Hackathon\Datasets\filesofdata\Claims"

SAMPLES = {
    "MG006A": ["CMJAY_TR_CMJAY_2025_R3_1022010623", "PMJAY_BR_S_2025_R3_1021667188"],
    "MG064A": ["PMJAY_AR_S_2025_R3_1021475536", "PMJAY_CG_2025_R2_2026031610017035"],
    "SB039A": ["CMJAY_TR_CMJAY_2025_R3_1021740400", "PMJAY_DL_S_G_R1_1021048216"],
    "SG039C": ["PMJAY_ANI_S_2025_R3_1018876421", "PMJAY_CG_2025_R2_1022167154"],
}

def extract_pdf_text(path):
    out = []
    try:
        with fitz.open(path) as doc:
            for i, page in enumerate(doc):
                out.append((i, page.get_text("text") or "",
                            len(page.get_images(full=True) or []),
                            len(page.get_drawings() or [])))
    except Exception as e:
        out.append((-1, f"__ERROR__ {e}", 0, 0))
    return out

def filename_tail_token(fn):
    """Extract the document-type hint token from the filename.
    Pattern: <NNNNNN>__<case_id>__<tail>.<ext>
    We want the <tail> stripped of extension."""
    stem = os.path.splitext(fn)[0]
    parts = stem.split("__")
    if len(parts) >= 3:
        return parts[-1].upper()
    return stem.upper()

def main():
    total_files = 0
    total_pdf_pages = 0
    total_text_pages = 0
    per_pkg_tail_counts = defaultdict(Counter)
    per_pkg_ext_counts = defaultdict(Counter)
    per_pkg_sample_files = defaultdict(list)
    per_pkg_text_len_hist = defaultdict(list)

    # Also scan ALL folders in each package for richer filename stats
    all_folder_tail_counts = defaultdict(Counter)
    all_folder_count = defaultdict(int)

    # Scope-A: deep scan (the 8 sample folders)
    for pkg, cases in SAMPLES.items():
        for case in cases:
            folder = os.path.join(BASE, pkg, case)
            if not os.path.isdir(folder):
                continue
            for fn in sorted(os.listdir(folder)):
                full = os.path.join(folder, fn)
                ext = os.path.splitext(fn)[1].lower()
                per_pkg_ext_counts[pkg][ext] += 1
                total_files += 1
                tail = filename_tail_token(fn)
                per_pkg_tail_counts[pkg][tail] += 1
                per_pkg_sample_files[pkg].append(fn)
                if ext == ".pdf":
                    pages = extract_pdf_text(full)
                    for pi, text, nimg, ndraw in pages:
                        if pi >= 0:
                            total_pdf_pages += 1
                            if len(text.strip()) > 20:
                                total_text_pages += 1
                            per_pkg_text_len_hist[pkg].append(len(text or ""))

    # Scope-B: broader filename scan over ALL cases in each package
    for pkg in SAMPLES:
        pkg_dir = os.path.join(BASE, pkg)
        if not os.path.isdir(pkg_dir):
            continue
        for case in os.listdir(pkg_dir):
            case_dir = os.path.join(pkg_dir, case)
            if not os.path.isdir(case_dir):
                continue
            for fn in os.listdir(case_dir):
                tail = filename_tail_token(fn)
                all_folder_tail_counts[pkg][tail] += 1
                all_folder_count[pkg] += 1

    report = {
        "total_files_deep": total_files,
        "total_pdf_pages_deep": total_pdf_pages,
        "total_text_pages_deep": total_text_pages,
        "per_pkg_ext": {k: dict(v) for k, v in per_pkg_ext_counts.items()},
        "per_pkg_tail_deep": {k: v.most_common(40) for k, v in per_pkg_tail_counts.items()},
        "per_pkg_all_cases_count": dict(all_folder_count),
        "per_pkg_tail_all": {k: v.most_common(60) for k, v in all_folder_tail_counts.items()},
    }
    outp = r"C:\Users\sarav\NHA-Hackathon\docs\_analysis_report.json"
    with open(outp, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
