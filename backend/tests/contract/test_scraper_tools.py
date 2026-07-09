"""Contract test for search_flights/search_airbnb (contracts/agent-tools.md, NFR-02).

T027 — written before scrapers/flights.py (T034) and scrapers/airbnb.py (T035)
exist; MUST fail until then. Verifies the retry-once-then-error contract: a
source that fails MUST be retried exactly once before raising/degrading — never
zero retries, never unbounded retries.
"""

from unittest.mock import AsyncMock, patch

import pytest

from scrapers.airbnb import search_airbnb
from scrapers.flights import search_flights


@pytest.mark.asyncio
async def test_search_flights_retries_once_then_raises():
    with patch("scrapers.flights._run_browser_search", AsyncMock(side_effect=TimeoutError)) as mock_search:
        with pytest.raises(TimeoutError):
            await search_flights(origin="RUH", destination="JED", depart_date="2026-11-10")
    assert mock_search.await_count == 2  # original attempt + exactly one retry


@pytest.mark.asyncio
async def test_search_flights_succeeds_on_retry():
    with patch(
        "scrapers.flights._run_browser_search",
        AsyncMock(side_effect=[TimeoutError, [{"flight": "SV123"}]]),
    ) as mock_search:
        result = await search_flights(origin="RUH", destination="JED", depart_date="2026-11-10")
    assert result == [{"flight": "SV123"}]
    assert mock_search.await_count == 2


@pytest.mark.asyncio
async def test_search_airbnb_computes_distance_from_reference_point():
    with patch(
        "scrapers.airbnb._run_browser_search",
        AsyncMock(return_value=[{"listing_id": "abc", "lat": 24.762, "lng": 46.635}]),
    ):
        result = await search_airbnb(
            destination="Riyadh",
            reference_point={"lat": 24.764, "lng": 46.639},
            checkin="2026-11-10",
            checkout="2026-11-13",
        )
    assert "distance_km" in result[0]


@pytest.mark.asyncio
async def test_search_airbnb_retries_once_then_raises():
    with patch("scrapers.airbnb._run_browser_search", AsyncMock(side_effect=TimeoutError)) as mock_search:
        with pytest.raises(TimeoutError):
            await search_airbnb(
                destination="Riyadh",
                reference_point={"lat": 24.764, "lng": 46.639},
                checkin="2026-11-10",
                checkout="2026-11-13",
            )
    assert mock_search.await_count == 2
