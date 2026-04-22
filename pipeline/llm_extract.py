"""LLM-based date extraction for the fields regex can't reliably recover."""
from __future__ import annotations
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from pipeline.llm import LLMClient, LLMMode

DEFAULT_MODEL = "gemma-3-4b"  # cheapest vision-capable arbiter
DATE_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "date_extract.md"

TARGET_MODELS = {
    "gemma-3-4b": 4096,
    "ministral-3b": 4096,
    "ministral-8b": 4096,
    "nemotron-nano-30b": 4096,
    "gemma-3-12b": 4096,
}


def _read_prompt() -> str:
    if DATE_PROMPT_PATH.exists():
        return DATE_PROMPT_PATH.read_text(encoding="utf-8")
    return "Return a JSON object with extracted dates in DD-MM-YYYY format."


DATE_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)


def _parse_llm_response(resp_text: str) -> Dict[str, Optional[str]]:
    if not resp_text:
        return {}
    m = DATE_RE.search(resp_text)
    blob = m.group(0) if m else resp_text
    try:
        data = json.loads(blob)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


_NORMALIZE_FMTS = [
    "%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y",
    "%d-%b-%Y", "%d-%B-%Y", "%d %b %Y", "%d %B %Y",
    "%d-%b-%y", "%d %b %y",
]


def _normalize_dd_mm_yyyy(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    v = str(value).strip()
    for fmt in _NORMALIZE_FMTS:
        try:
            dt = datetime.strptime(v, fmt)
            return dt.strftime("%d-%m-%Y")
        except Exception:
            continue
    # last resort: if already matches DD-MM-YYYY
    if re.match(r"^\d{2}-\d{2}-\d{4}$", v):
        return v
    return None


def extract_dates_llm(
    client: LLMClient,
    page_text: str,
    target_fields: List[str],
    model: str = DEFAULT_MODEL,
) -> Dict[str, Optional[str]]:
    if not page_text or not target_fields:
        return {k: None for k in target_fields}
    prompt = _read_prompt()
    instruction = (
        prompt
        + "\n\nTarget fields for THIS page: "
        + ", ".join(target_fields)
        + "\n\nDOCUMENT TEXT:\n```\n"
        + page_text[:4000]  # cap for token economy
        + "\n```"
    )
    resp = client.complete(
        model=model,
        messages=[{"role": "user", "content": instruction}],
        metadata={"use_case": "date_extract"},
    )
    parsed = _parse_llm_response(resp.get("content", ""))
    return {k: _normalize_dd_mm_yyyy(parsed.get(k)) for k in target_fields}
