"""Fix: trip intake flow — handle_trip_request's origin resolution
(agents/orchestrator.py). Missing origin should either (a) resolve silently
from a stored home_city preference, or (b) pause with a clarifying question
tied to a real session — never guess, never ask if we already know.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from agents.orchestrator import MISSING_ORIGIN_QUESTION, _run_research_background, handle_trip_request

_BASE_DETAILS = {
    "destination": "Riyadh",
    "start_date": "2026-07-14",
    "end_date": "2026-07-17",
    "purpose": "kickoff",
    "budget": 1500,
    "reference_point": "KAFD",
}


@pytest.mark.asyncio
async def test_origin_present_in_description_is_used_directly():
    fake_session = SimpleNamespace(session_id="s1")
    with (
        patch(
            "agents.orchestrator._extract_trip_details",
            AsyncMock(return_value={**_BASE_DETAILS, "origin": "Austin, TX"}),
        ),
        patch("agents.orchestrator.create_session", AsyncMock(return_value=fake_session)),
        patch("agents.memory.store_turn", AsyncMock()),
        patch("agents.memory.get_preferences", AsyncMock()) as mock_get_preferences,
        patch("agents.orchestrator._schedule_research", Mock()) as mock_schedule,
    ):
        result = await handle_trip_request("desc", user_id="traveler@example.com", tenant_id="test-tenant")

    mock_get_preferences.assert_not_called()  # origin was already known — never even checks memory
    assert result == {"session_id": "s1", "status": "in_progress"}
    dispatched_details = mock_schedule.call_args.args[3]
    assert dispatched_details["origin"] == "Austin, TX"


@pytest.mark.asyncio
async def test_origin_absent_uses_stored_home_city_silently():
    fake_session = SimpleNamespace(session_id="s1")
    with (
        patch("agents.orchestrator._extract_trip_details", AsyncMock(return_value={**_BASE_DETAILS, "origin": None})),
        patch("agents.orchestrator.create_session", AsyncMock(return_value=fake_session)),
        patch("agents.memory.store_turn", AsyncMock()),
        patch(
            "agents.memory.get_preferences",
            AsyncMock(return_value={"preferences": [{"type": "home_city", "value": {"city": "Austin, TX"}, "version": 1}]}),
        ),
        patch("agents.orchestrator._schedule_research", Mock()) as mock_schedule,
    ):
        result = await handle_trip_request("desc", user_id="traveler@example.com", tenant_id="test-tenant")

    assert "clarifying_question" not in result
    assert result == {"session_id": "s1", "status": "in_progress"}
    dispatched_details = mock_schedule.call_args.args[3]
    assert dispatched_details["origin"] == "Austin, TX"


@pytest.mark.asyncio
async def test_origin_absent_and_no_home_city_returns_clarifying_question():
    fake_session = SimpleNamespace(session_id="s1")
    with (
        patch("agents.orchestrator._extract_trip_details", AsyncMock(return_value={**_BASE_DETAILS, "origin": None})),
        patch("agents.orchestrator.create_session", AsyncMock(return_value=fake_session)),
        patch("agents.memory.store_turn", AsyncMock()),
        patch("agents.memory.get_preferences", AsyncMock(return_value={"preferences": []})),
        patch("agents.orchestrator.update_session_status", AsyncMock()) as mock_update_status,
        patch("agents.orchestrator._schedule_research", Mock()) as mock_schedule,
    ):
        result = await handle_trip_request("desc", user_id="traveler@example.com", tenant_id="test-tenant")

    assert result == {"clarifying_question": MISSING_ORIGIN_QUESTION, "session_id": "s1"}
    mock_update_status.assert_awaited_once_with("test-tenant", "s1", "awaiting_clarification")
    mock_schedule.assert_not_called()


@pytest.mark.asyncio
async def test_background_research_failure_sets_clean_session_error_state():
    fake_session = SimpleNamespace(session_id="s1")
    with (
        patch("agents.orchestrator._dispatch_research", AsyncMock(side_effect=TimeoutError)),
        patch("agents.orchestrator.update_session_status", AsyncMock()) as mock_update_status,
        patch("agents.orchestrator.events.publish", AsyncMock()) as mock_publish,
    ):
        await _run_research_background(fake_session, "test-tenant", "traveler@example.com", _BASE_DETAILS)

    mock_update_status.assert_awaited_once_with("test-tenant", "s1", "research_failed")
    mock_publish.assert_awaited_once_with(
        "s1",
        "research_failed",
        {"status": "research_failed", "error_type": "TimeoutError"},
    )
