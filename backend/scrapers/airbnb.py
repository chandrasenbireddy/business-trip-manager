"""Airbnb scraper: browser-use with distance-from-reference-point (NFR-02: retry once then error)."""

import math

from browser_use import Agent as BrowserAgent
from browser_use.llm.openai.chat import ChatOpenAI

from agents.base import traced
from tools.model_router import ModelRateLimitError, call_with_fallback, client_config, primary_model


def _browser_llm(which: str = "primary") -> ChatOpenAI:
    cfg = client_config("scraper_airbnb", which)
    return ChatOpenAI(
        model=cfg["model"],
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        max_retries=0,
    )


async def _run_browser_search(destination: str, checkin: str, checkout: str, notes: str, broaden: bool) -> list[dict]:
    task = f"Search Airbnb for stays in {destination} from {checkin} to {checkout}. Return listing_id, price, lat, lng, rating."
    if notes:
        task += f" The traveler said: {notes!r} — take that into account."
    if broaden:
        task += " No results at the exact dates — widen the search to +/- 2 days and a larger radius."
    async def _invoke(model_id: str):
        which = "primary" if model_id == primary_model("scraper_airbnb") else "fallback"
        browser_agent = BrowserAgent(task=task, llm=_browser_llm(which), max_failures=1, final_response_after_failure=False)
        result = await browser_agent.run()
        if not result.is_successful():
            errors = " ".join(str(error) for error in result.errors() if error).lower()
            if "timeout" in errors or "timed out" in errors:
                raise TimeoutError("browser LLM timed out")
            if "429" in errors or "rate limit" in errors or "rate_limit" in errors:
                raise ModelRateLimitError("browser LLM rate-limited")
            raise RuntimeError("browser LLM failed")
        return result

    return await call_with_fallback("scraper_airbnb", _invoke)


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
