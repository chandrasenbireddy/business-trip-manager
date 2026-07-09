"""Contract test for fetch_airbnb_account (contracts/agent-tools.md).

T078 — written before tools/airbnb_account.py exists (T081/T084); MUST fail
until then. `cookie_expired` degrades gracefully rather than raising —
"no credential on file" and "an expired one" both hit this same path.
"""

from unittest.mock import AsyncMock, patch

import pytest

from tools.airbnb_account import fetch_airbnb_account


@pytest.mark.asyncio
async def test_no_connected_account_returns_cookie_expired():
    with patch("tools.airbnb_account.secrets.resolve", side_effect=Exception("secret not found")):
        result = await fetch_airbnb_account("traveler@example.com")
    assert result == {"status": "cookie_expired"}


@pytest.mark.asyncio
async def test_expired_session_returns_cookie_expired_not_an_exception():
    with (
        patch("tools.airbnb_account.secrets.resolve", lambda ref: "stale-cookie"),
        patch("tools.airbnb_account._run_authenticated_session", AsyncMock(side_effect=Exception("auth failed"))),
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
