"""Pytest fixtures for NHA PS-01 tests."""
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CLAIMS_ROOT = REPO_ROOT / "Datasets" / "filesofdata" / "Claims"


@pytest.fixture
def claims_root() -> Path:
    """Root directory of claim case folders."""
    assert CLAIMS_ROOT.exists(), f"Expected claims at {CLAIMS_ROOT}"
    return CLAIMS_ROOT


@pytest.fixture
def sample_mg006a_case(claims_root: Path) -> Path:
    """A real MG006A case folder."""
    case = claims_root / "MG006A" / "CMJAY_TR_CMJAY_2025_R3_1022010623"
    assert case.exists(), f"Sample case missing at {case}"
    return case


@pytest.fixture
def all_package_codes():
    return ["MG064A", "SG039C", "MG006A", "SB039A"]
