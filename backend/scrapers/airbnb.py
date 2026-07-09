"""Airbnb scraper: browser-use with distance-from-reference-point (NFR-02: retry once then error)."""

import math

from browser_use import Agent as BrowserAgent
from browser_use.llm.ollama.chat import ChatOllama

from agents.base import traced
from tools.model_router import client_config


def _browser_llm() -> ChatOllama:
    cfg = client_config("scraper_airbnb")
    return ChatOllama(model=cfg["model"], host=cfg["base_url"])


async def _run_browser_search(destination: str, checkin: str, checkout: str, notes: str, broaden: bool) -> list[dict]:
    task = f"Search Airbnb for stays in {destination} from {checkin} to {checkout}. Return listing_id, price, lat, lng, rating."
    if notes:
        task += f" The traveler said: {notes!r} — take that into account."
    if broaden:
        task += " No results at the exact dates — widen the search to +/- 2 days and a larger radius."
    browser_agent = BrowserAgent(task=task, llm=_browser_llm())
    return await browser_agent.run()


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@traced("scraper.search_airbnb", tool_name="search_airbnb")
async def search_airbnb(
    destination: str,
    reference_point: dict,
    checkin: str,
    checkout: str,
    notes: str = "",
    broaden: bool = False,
) -> list[dict]:
    """Retry exactly once on failure before raising (NFR-02). Every result gets
    `distance_km` from `reference_point` (spec FR-003).
    """
    try:
        listings = await _run_browser_search(destination, checkin, checkout, notes, broaden)
    except Exception:
        listings = await _run_browser_search(destination, checkin, checkout, notes, broaden)

    for listing in listings:
        listing["distance_km"] = round(
            _haversine_km(reference_point["lat"], reference_point["lng"], listing["lat"], listing["lng"]),
            2,
        )
    return listings
