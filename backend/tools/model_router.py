"""Per-agent model routing + fallback (research.md §3, NFR-06).

Swapping a model for an agent role is a one-line change in models.yaml, never
a code change (resolves PRD Open Question 6).
"""

import functools
import logging
import os
from pathlib import Path

import yaml
from opentelemetry import trace

_CONFIG_PATH = Path(__file__).parent.parent / "models.yaml"
logger = logging.getLogger(__name__)


class ModelRateLimitError(RuntimeError):
    pass


@functools.lru_cache(maxsize=1)
def _config() -> dict:
    return yaml.safe_load(_CONFIG_PATH.read_text())


def _routes() -> dict:
    return {role: cfg for role, cfg in _config().items() if role != "providers"}


def primary_model(agent_role: str) -> str:
    return _routes()[agent_role]["primary"]["model"]


def fallback_model(agent_role: str) -> str | None:
    fallback = _routes()[agent_role].get("fallback")
    return fallback["model"] if fallback else None


def client_config(agent_role: str, which: str = "primary") -> dict:
    """{provider, model, base_url, api_key} for the client that actually calls
    the model. `api_key` is read fresh from `api_key_env` every call, never
    cached — same "resolve at point of use" discipline as tools/secrets.py,
    just sourced from the environment/.env instead of Secret Manager (this is
    a platform-level model credential, not a per-tenant/user one).
    """
    entry = _routes()[agent_role].get(which)
    if entry is None:
        raise KeyError(f"{agent_role!r} has no {which!r} entry in models.yaml")
    provider_cfg = _config()["providers"][entry["provider"]]
    api_key_env = provider_cfg.get("api_key_env")
    return {
        "provider": entry["provider"],
        "model": entry["model"],
        "base_url": provider_cfg["base_url"],
        "api_key": os.environ.get(api_key_env, "") if api_key_env else "",
    }


async def call_with_fallback(agent_role: str, invoke, *args, **kwargs):
    """Call `invoke(model_id, *args, **kwargs)` with the agent's primary model;
    on failure or rate-limit, retry once with the fallback model and surface the
    switch in the current OTel span (NFR-06) rather than failing silently.

    Roles with no `fallback` in models.yaml re-raise instead — most roles
    don't have one yet (see models.yaml's header comment).
    """
    primary, fallback = primary_model(agent_role), fallback_model(agent_role)
    primary_cfg = client_config(agent_role)
    try:
        result = await invoke(primary, *args, **kwargs)
        logger.info(
            "model call served role=%s provider=%s model=%s",
            agent_role,
            primary_cfg["provider"],
            primary,
        )
        return result
    except Exception as exc:  # noqa: BLE001 — deliberately broad: any primary-model failure falls back
        if fallback is None:
            raise
        exception_name = type(exc).__name__.lower()
        status_code = getattr(exc, "status_code", None)
        if isinstance(exc, TimeoutError) or "timeout" in exception_name:
            reason = "timeout"
        elif status_code == 429 or "ratelimit" in exception_name or "rate_limit" in exception_name:
            reason = "rate-limit"
        else:
            reason = "error"
        fallback_cfg = client_config(agent_role, "fallback")
        logger.warning(
            "model fallback fired role=%s from_provider=%s to_provider=%s reason=%s exception=%s",
            agent_role,
            primary_cfg["provider"],
            fallback_cfg["provider"],
            reason,
            type(exc).__name__,
        )
        span = trace.get_current_span()
        # ponytail: exception class only, never str(exc) — a provider SDK error can
        # echo the failed request (prompt/trip details) into its message, and
        # constitution Principle XII bans personal data in span attributes.
        span.set_attribute("model.fallback_reason", reason)
        span.set_attribute("model.fallback_exception", type(exc).__name__)
        span.set_attribute("model.fallback_from", primary)
        span.set_attribute("model.fallback_to", fallback)
        result = await invoke(fallback, *args, **kwargs)
        logger.info(
            "model call served role=%s provider=%s model=%s fallback_reason=%s",
            agent_role,
            fallback_cfg["provider"],
            fallback,
            reason,
        )
        return result
