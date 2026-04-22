"""Entity-extraction helpers.

These are deterministic utility regexes used across rule engines.
Phase 2 expands the keyword sets; Phase 3 adds LLM-based date extraction.
"""
from __future__ import annotations
import re
from typing import List, Optional

DATE_PATTERNS = [
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    r"\b\d{1,2}-[A-Za-z]{3}-\d{2,4}\b",
    r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4}\b",
]

AGE_PATTERNS = [
    r"(?:age|aged)\s*[:\-]?\s*(\d{1,3})",
    r"(\d{1,3})\s*(?:yrs?|years?)\s*old",
]


def find_dates(text: str) -> List[str]:
    if not text:
        return []
    found: List[str] = []
    seen = set()
    for pat in DATE_PATTERNS:
        for m in re.findall(pat, text, flags=re.IGNORECASE):
            if m not in seen:
                seen.add(m)
                found.append(m)
    return found


def find_age(text: str) -> Optional[int]:
    if not text:
        return None
    for pat in AGE_PATTERNS:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            try:
                v = int(m.group(1))
                if 0 < v <= 120:
                    return v
            except ValueError:
                continue
    return None


def contains_any(text: str, keywords: List[str]) -> int:
    if not text:
        return 0
    lower = text.lower()
    return 1 if any(kw.lower() in lower for kw in keywords) else 0
