"""The single most safety-critical contract in the system (constitution Principle IX).

T028 — written before agents/booking.py (T041) exists; MUST fail until then.
`execute_booking` MUST be unreachable unless session.status == "confirmed".
No refactor of booking.py may ever remove this check.
"""

import pytest

from agents.booking import BookingGateError, execute_booking


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
