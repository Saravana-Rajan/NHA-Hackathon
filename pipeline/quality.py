"""Page quality estimation.

Heuristics (CPU-only, no external models):
  * blur_score: variance of Laplacian (lower = blurrier). Optional -- requires cv2.
  * text_density: OCR character count.
  * is_poor = (blur_score < 100) OR (text_density < 50)
"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict


def estimate_page_quality(image_path: str, extracted_text: str) -> Dict[str, Any]:
    blur = None
    try:
        import cv2
        if image_path and Path(image_path).exists():
            img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            if img is not None:
                blur = float(cv2.Laplacian(img, cv2.CV_64F).var())
    except Exception:
        blur = None

    text_density = len((extracted_text or "").strip())
    is_poor = False
    reasons = []
    if blur is not None and blur < 100:
        is_poor = True
        reasons.append(f"blur_score={blur:.1f}<100")
    if text_density < 50:
        is_poor = True
        reasons.append(f"text_density={text_density}<50")

    return {
        "is_poor": is_poor,
        "blur_score": blur,
        "text_density": text_density,
        "reasons": reasons,
    }
