"""Unit test for tools/model_router.py's fallback path (research.md §3, NFR-06)
and provider-client config (added when NVIDIA NIM was wired up as the primary
provider — see models.yaml's header comment).

No prior story exercised the fallback branch itself — every agent-level test
mocked the primary call succeeding. Written during Polish (T108) after a real
coverage run showed this file at 55%.
"""

import os
from unittest.mock import AsyncMock

import pytest

from tools.model_router import call_with_fallback, client_config, fallback_model, primary_model


def test_primary_and_fallback_model_come_from_models_yaml():
    assert primary_model("orchestrator") != fallback_model("orchestrator")


def test_roles_with_no_configured_fallback_return_none():
    # Only orchestrator has a real fallback today (models.yaml header comment)
    # — call_with_fallback must degrade to "raise the original error" for
    # every other role, not crash trying to invoke a None model.
    assert fallback_model("planner") is None


@pytest.mark.asyncio
async def test_call_with_fallback_uses_primary_on_success():
    invoke = AsyncMock(return_value="ok")
    result = await call_with_fallback("orchestrator", invoke)
    assert result == "ok"
    invoke.assert_awaited_once_with(primary_model("orchestrator"))


@pytest.mark.asyncio
async def test_call_with_fallback_retries_fallback_on_primary_failure():
    invoke = AsyncMock(side_effect=[Exception("rate limited"), "ok from fallback"])
    result = await call_with_fallback("orchestrator", invoke)
    assert result == "ok from fallback"
    assert invoke.await_count == 2
    first_call, second_call = invoke.await_args_list
    assert first_call.args[0] == primary_model("orchestrator")
    assert second_call.args[0] == fallback_model("orchestrator")


@pytest.mark.asyncio
async def test_call_with_fallback_propagates_if_fallback_also_fails():
    invoke = AsyncMock(side_effect=[Exception("primary down"), Exception("fallback down too")])
    with pytest.raises(Exception, match="fallback down too"):
        await call_with_fallback("orchestrator", invoke)


@pytest.mark.asyncio
async def test_call_with_fallback_raises_original_error_when_role_has_no_fallback():
    invoke = AsyncMock(side_effect=ValueError("no fallback for planner"))
    with pytest.raises(ValueError, match="no fallback for planner"):
        await call_with_fallback("planner", invoke)
    invoke.assert_awaited_once()


def test_client_config_resolves_nvidia_base_url_and_key_for_orchestrator_primary():
    os.environ["NVIDIA_API_KEY"] = "test-nvidia-key"
    try:
        cfg = client_config("orchestrator")
    finally:
        del os.environ["NVIDIA_API_KEY"]
    assert cfg["provider"] == "nvidia"
    assert cfg["base_url"] == "https://integrate.api.nvidia.com/v1"
    assert cfg["model"] == "nvidia/nemotron-3-ultra-550b-a55b"
    assert cfg["api_key"] == "test-nvidia-key"


def test_client_config_resolves_groq_fallback_for_orchestrator():
    cfg = client_config("orchestrator", which="fallback")
    assert cfg["provider"] == "groq"
    assert cfg["base_url"] == "https://api.groq.com/openai/v1"


def test_client_config_ollama_provider_has_no_api_key():
    cfg = client_config("scraper_flights")
    assert cfg["provider"] == "ollama"
    assert cfg["api_key"] == ""


def test_client_config_raises_for_missing_fallback():
    with pytest.raises(KeyError):
        client_config("planner", which="fallback")
