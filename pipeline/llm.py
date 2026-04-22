"""LLM client wrapper.

Wraps the provided NHAclient (from code/nha_client.py) with:
  - mandatory metadata injection (problem_statement=1)
  - in-memory prompt cache (dedupes identical calls during a run)
  - dry-run mode for tests (no network)
  - input/output token accounting
"""
from __future__ import annotations
import hashlib
import json
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "code") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "code"))


class LLMMode(str, Enum):
    LIVE = "live"
    DRY_RUN = "dry_run"


def _hash_messages(model: str, messages: List[dict], metadata: dict) -> str:
    payload = json.dumps(
        {"m": model, "msg": messages, "meta": metadata},
        sort_keys=True, default=str,
    )
    return hashlib.sha1(payload.encode()).hexdigest()


class LLMClient:
    """Unified interface over NHA's LLM proxy."""

    def __init__(
        self,
        mode: LLMMode = LLMMode.DRY_RUN,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        problem_statement: int = 1,
    ):
        self.mode = mode
        self.problem_statement = problem_statement
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.last_metadata: Dict[str, Any] = {}
        self._nha = None
        if mode == LLMMode.LIVE:
            assert client_id and client_secret, "LIVE mode needs credentials"
            from nha_client import NHAclient
            self._nha = NHAclient(client_id, client_secret)

    def complete(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
        **kwargs,
    ) -> Dict[str, Any]:
        """Send a chat-completion-style request.

        Returns a dict with at least {content, usage, model}.
        """
        md = dict(metadata or {})
        md.setdefault("problem_statement", self.problem_statement)
        self.last_metadata = md

        key = _hash_messages(model, messages, md)
        if use_cache and key in self.cache:
            self.cache_hits += 1
            return self.cache[key]
        self.cache_misses += 1

        if self.mode == LLMMode.DRY_RUN:
            resp = {
                "content": "[dry-run placeholder]",
                "usage": {"input_tokens": 0, "output_tokens": 0},
                "model": model,
            }
        else:
            raw = self._nha.completion(
                model=model, messages=messages, metadata=md, **kwargs,
            )
            content = ""
            try:
                content = raw["choices"][0]["message"]["content"]
            except Exception:
                content = str(raw)
            usage = raw.get("usage", {}) if isinstance(raw, dict) else {}
            in_tok = int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
            out_tok = int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0)
            self.total_input_tokens += in_tok
            self.total_output_tokens += out_tok
            resp = {
                "content": content,
                "usage": {"input_tokens": in_tok, "output_tokens": out_tok},
                "model": model,
                "raw": raw,
            }

        if use_cache:
            self.cache[key] = resp
        return resp
