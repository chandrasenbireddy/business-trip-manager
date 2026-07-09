"""Unit test for tools/model_router.py's fallback path (research.md §3, NFR-06).

No prior story exercised the fallback branch itself — every agent-level test
mocked the primary call succeeding. Written during Polish (T108) after a real
coverage run showed this file at 55%.
"""

from unittest.mock import AsyncMock

import pytest

from tools.model_router import call_with_fallback, fallback_model, primary_model


def test_primary_and_fallback_model_come_from_models_yaml():
    assert primary_model("orchestrator") != fallback_model("orchestrator")


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
