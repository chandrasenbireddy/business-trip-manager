"""Contract test for fetch_airbnb_account (contracts/agent-tools.md).

T078 — written before tools/airbnb_account.py exists (T081/T084); MUST fail
until then. Both failure statuses degrade gracefully rather than raising —
"no credential on file" (not_connected) and "an expired one" (cookie_expired)
are distinguished only for the reconnect-nudge UI's wording (fixed during
Polish, T108/T110: get_airbnb_context originally collapsed both into
"connected: true", which would show a "reconnect" nudge to someone who
never connected at all).
"""

from unittest.mock import AsyncMock, patch

import pytest

from tools.airbnb_account import fetch_airbnb_account


@pytest.mark.asyncio
async def test_no_connected_account_returns_not_connected():
    with patch("tools.airbnb_account.secrets.resolve", side_effect=Exception("secret not found")):
        result = await fetch_airbnb_account("traveler@example.com")
    assert result == {"status": "not_connected"}


@pytest.mark.asyncio
async def test_expired_session_returns_cookie_expired_not_an_exception():
    with (
        patch("tools.airbnb_account.secrets.resolve", lambda ref: "stale-cookie"),
        patch(
            "tools.airbnb_account._run_authenticated_session",
            AsyncMock(side_effect=Exception("auth failed")),
        ),
    ):
        result = await fetch_airbnb_account("traveler@example.com")
    assert result == {"status": "cookie_expired"}


@pytest.mark.asyncio
async def test_valid_session_returns_account_data():
    with (
        patch("tools.airbnb_account.secrets.resolve", lambda ref: "fresh-cookie"),
        patch(
            "tools.airbnb_account._run_authenticated_session",
            AsyncMock(
                return_value={
                    "upcoming_reservations": [{"listing_id": "r1"}],
                    "past_stays": [{"listing_id": "p1"}],
                    "wishlist": [{"listing_id": "w1"}],
                }
            ),
        ),
    ):
        result = await fetch_airbnb_account("traveler@example.com")
    assert result["upcoming_reservations"] == [{"listing_id": "r1"}]
    assert result["wishlist"] == [{"listing_id": "w1"}]
