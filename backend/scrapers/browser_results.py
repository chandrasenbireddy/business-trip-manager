"""Parse browser-use AgentHistoryList into list[dict] option rows."""

from __future__ import annotations

import json
import re
from typing import Any


def listings_from_browser_result(result: Any) -> list[dict]:
    """browser-use `Agent.run()` returns AgentHistoryList, not list[dict].

    Prefer structured JSON from `final_result()`; fall back to scanning
    extracted_content strings for a JSON array/object of listings.
    """
    if result is None:
        return []
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]

    candidates: list[Any] = []
    final = result.final_result() if hasattr(result, "final_result") else None
    if final is not None:
        candidates.append(final)
    if hasattr(result, "extracted_content"):
        candidates.extend(result.extracted_content() or [])

    for candidate in candidates:
        parsed = _coerce_listings(candidate)
        if parsed:
            return parsed
    return []


def _coerce_listings(value: Any) -> list[dict]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in ("results", "listings", "flights", "options", "stays"):
            nested = value.get(key)
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
        return [value]
    if isinstance(value, str):
        return _coerce_listings(_parse_json_blob(value))
    return []


def _parse_json_blob(text: str) -> Any:
    stripped = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", stripped, re.DOTALL | re.IGNORECASE)
    if fence:
        stripped = fence.group(1).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    for opener, closer in (("[", "]"), ("{", "}")):
        start, end = stripped.find(opener), stripped.rfind(closer)
        if start >= 0 and end > start:
            try:
                return json.loads(stripped[start : end + 1])
            except json.JSONDecodeError:
                continue
    return None
