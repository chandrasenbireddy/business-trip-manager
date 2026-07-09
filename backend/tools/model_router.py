"""Per-agent model routing + fallback (research.md §3, NFR-06).

Swapping a model for an agent role is a one-line change in models.yaml, never
a code change (resolves PRD Open Question 6).
"""

import functools
from pathlib import Path

import yaml
from opentelemetry import trace

_CONFIG_PATH = Path(__file__).parent.parent / "models.yaml"


@functools.lru_cache(maxsize=1)
def _routes() -> dict:
    return yaml.safe_load(_CONFIG_PATH.read_text())


def primary_model(agent_role: str) -> str:
    return _routes()[agent_role]["primary"]


def fallback_model(agent_role: str) -> str:
    return _routes()[agent_role]["fallback"]


async def call_with_fallback(agent_role: str, invoke, *args, **kwargs):
    """Call `invoke(model_id, *args, **kwargs)` with the agent's primary model;
    on failure or rate-limit, retry once with the fallback model and surface the
    switch in the current OTel span (NFR-06) rather than failing silently.
    """
    primary, fallback = primary_model(agent_role), fallback_model(agent_role)
    try:
        return await invoke(primary, *args, **kwargs)
    except Exception as exc:  # noqa: BLE001 — deliberately broad: any primary-model failure falls back
        span = trace.get_current_span()
        span.set_attribute("model.fallback_reason", str(exc))
        span.set_attribute("model.fallback_from", primary)
        span.set_attribute("model.fallback_to", fallback)
        return await invoke(fallback, *args, **kwargs)
