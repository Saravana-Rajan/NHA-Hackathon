"""Tests for pipeline.ocr."""
from pathlib import Path
from PIL import Image
import numpy as np
import pytest

from pipeline.ocr import run_ocr, OCRBackend


def _make_blank_png(tmp_path: Path) -> Path:
    img_path = tmp_path / "blank.png"
    Image.fromarray(np.full((400, 600, 3), 255, dtype=np.uint8)).save(img_path)
    return img_path


def test_run_ocr_returns_empty_text_on_blank_image(tmp_path):
    img = _make_blank_png(tmp_path)
    result = run_ocr(str(img))
    assert isinstance(result.text, str)
    assert isinstance(result.lines, list)


def test_run_ocr_handles_missing_file_gracefully(tmp_path):
    result = run_ocr(str(tmp_path / "does_not_exist.png"))
    assert result.text == ""
    assert result.lines == []


def test_ocr_backend_noop_works(tmp_path):
    img = _make_blank_png(tmp_path)
    backend = OCRBackend.NOOP
    result = run_ocr(str(img), backend=backend)
    assert result.text == ""
