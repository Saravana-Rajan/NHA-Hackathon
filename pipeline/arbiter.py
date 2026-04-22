"""Stage C LLM doctype arbiter.

Used when Stage A (keyword rules) and Stage B (visual) fail to produce a
confident doctype classification for a page. Asks an LLM to pick exactly
one label from a caller-supplied candidate list.

Kept in a standalone module (not `classifier.py`) to minimise merge
conflicts with parallel agents editing Stage A/B logic.
"""
from __future__ import annotations

import json as _json
import re as _re
from pathlib import Path as _Path
from typing import TYPE_CHECKING, List, Tuple

from pipeline.models import Evidence

if TYPE_CHECKING:  # pragma: no cover - import-time only for type checkers
    from pipeline.llm import LLMClient


ARBITER_MODEL = "gemma-3-4b"  # cheapest vision-capable
ARBITER_PROMPT_PATH = (
    _Path(__file__).resolve().parent.parent / "prompts" / "arbiter_doctype.md"
)


def _arbiter_prompt() -> str:
    if ARBITER_PROMPT_PATH.exists():
        return ARBITER_PROMPT_PATH.read_text(encoding="utf-8")
    return 'Return {"label":"X","reason":"..."} from the candidate list.'


_ARBITER_JSON_RE = _re.compile(r"\{[^{}]*\}", _re.DOTALL)


def _parse_arbiter_response(text: str) -> Tuple[str, str]:
    """Parse the arbiter JSON response.

    Tolerant of a JSON object embedded in surrounding prose. On any failure
    returns ("unknown", "").
    """
    if not text:
        return "unknown", ""
    m = _ARBITER_JSON_RE.search(text)
    blob = m.group(0) if m else text
    try:
        data = _json.loads(blob)
        if not isinstance(data, dict):
            return "unknown", ""
        return data.get("label", "unknown"), data.get("reason", "")
    except Exception:
        return "unknown", ""


def classify_via_llm_arbiter(
    llm_client: "LLMClient",
    page_text: str,
    candidates: List[str],
    model: str = ARBITER_MODEL,
) -> Tuple[str, float, List[Evidence]]:
    """Ask an LLM to choose among candidate doctypes for an ambiguous page.

    Returns (label, confidence, evidence_list).

    On dry-run (or any invalid/placeholder response), the label will not
    appear in the candidate list, and we return ("unknown", 0.0, []).
    For valid choices, confidence is a fixed 0.75 with a single Evidence
    entry citing the LLM's short reason.
    """
    prompt = _arbiter_prompt() + "\nCandidates: " + ", ".join(candidates)
    body = (
        prompt
        + "\n\nPage text:\n```\n"
        + (page_text[:3000] if page_text else "")
        + "\n```"
    )
    resp = llm_client.complete(
        model=model,
        messages=[{"role": "user", "content": body}],
        metadata={"use_case": "arbiter_doctype"},
    )
    label, reason = _parse_arbiter_response(resp.get("content", ""))
    if label not in candidates:
        label = "unknown"
    conf = 0.75 if label != "unknown" else 0.0
    if label != "unknown":
        ev = [
            Evidence(
                page_number=0,
                text_span=reason[:100],
                rule_id=f"arbiter.{label}.llm",
            )
        ]
    else:
        ev = []
    return label, conf, ev
