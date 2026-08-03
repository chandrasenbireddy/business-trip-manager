"""Unit test for agents.memory.get_airbnb_context's not_connected vs
cookie_expired distinction (spec FR-029) — the two must not collapse into
the same "connected: true" shape, or a traveler who never connected an
account sees a "reconnect" nudge instead of "connect." Written during
Polish (T108/T110) after a real coverage run showed AirbnbAccountContext
at 0% (it was constructed nowhere).
"""

from unittest.mock import AsyncMock, patch

import pytest

from agents.memory import get_airbnb_context


@pytest.mark.asyncio
async def test_not_connected_reports_connected_false():
    with patch("agents.memory.fetch_airbnb_account", AsyncMock(return_value={"status": "not_connected"})):
        context = await get_airbnb_context("traveler@example.com")
    assert context["connected"] is False


@pytest.mark.asyncio
async def test_expired_reports_connected_true_cookie_expired():
    with patch("agents.memory.fetch_airbnb_account", AsyncMock(return_value={"status": "cookie_expired"})):
        context = await get_airbnb_context("traveler@example.com")
    assert context["connected"] is True
    assert context["cookie_status"] == "expired"


@pytest.mark.asyncio
async def test_valid_session_reports_connected_true_cookie_valid_with_data():
    with patch(
        "agents.memory.fetch_airbnb_account",
        AsyncMock(
            return_value={
                "upcoming_reservations": [],
                "past_stays": [],
                "wishlist": [{"listing_id": "w1"}],
            }
        ),
    ):
        context = await get_airbnb_context("traveler@example.com")
    assert context["connected"] is True
    assert context["cookie_status"] == "valid"
    assert context["wishlist"] == [{"listing_id": "w1"}]
