"""The single most safety-critical contract in the system (constitution Principle IX).

T028 — written before agents/booking.py (T041) exists; MUST fail until then.
`execute_booking` MUST be unreachable unless session.status == "confirmed".
No refactor of booking.py may ever remove this check.
"""

import os
from unittest.mock import AsyncMock, patch

import pytest

from agents.booking import BookingGateError, execute_booking
from agents.models.cost import record_cost_event
from agents.models.session import create_session


@pytest.mark.asyncio
async def test_execute_booking_rejected_when_in_progress():
    with pytest.raises(BookingGateError):
        await execute_booking(session_id="s1", session_status="in_progress", itinerary={})


@pytest.mark.asyncio
async def test_execute_booking_rejected_when_awaiting_approval():
    with pytest.raises(BookingGateError):
        await execute_booking(session_id="s1", session_status="awaiting_approval", itinerary={})


@pytest.mark.asyncio
async def test_execute_booking_allowed_when_confirmed():
    result = await execute_booking(
        session_id="s1",
        session_status="confirmed",
        itinerary={"flight": {"provider_url": "https://example.com"}},
    )
    assert result["status"] in ("booking", "completed")


@pytest.mark.asyncio
async def test_execute_booking_sends_confirmation_email_to_the_real_traveler_with_a_real_cost_summary():
    """Polish (T109/T113): execute_booking previously called send_email with a
    hardcoded empty recipient_address and empty cost_summary regardless of the
    session's actual traveler/cost events — silently "succeeding" because the
    stubbed send_email ignores its args. Caught during a security/deployment
    review, not by any prior test.
    """
    if not os.environ.get("TEST_DATABASE_URL"):
        pytest.skip("no TEST_DATABASE_URL configured")

    session = await create_session("test-tenant", "traveler@example.com", trip_request={})
    await record_cost_event(
        "test-tenant",
        session.session_id,
        "traveler@example.com",
        agent_type="booking",
        model_id="m1",
        cost_usd=1.23,
    )

    with patch("agents.booking.send_email", AsyncMock(return_value={"status": "ok"})) as mock_send_email:
        await execute_booking(
            session_id=session.session_id,
            session_status="confirmed",
            itinerary={},
            tenant_id="test-tenant",
            user_id="traveler@example.com",
        )

    _, kwargs = mock_send_email.call_args
    assert kwargs["recipient_address"] == "traveler@example.com"
    assert kwargs["cost_summary"]["total"] == 1.23
