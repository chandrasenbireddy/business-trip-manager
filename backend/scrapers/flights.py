"""Flights scraper: browser-use against Google Flights/Kayak (NFR-02: retry once then error)."""

from browser_use import Agent as BrowserAgent

from agents.base import traced


async def _run_browser_search(
    origin: str, destination: str, depart_date: str, return_date: str | None, notes: str, broaden: bool
) -> list[dict]:
    task = (
        f"Search Google Flights for a flight from {origin} to {destination} "
        f"departing {depart_date}" + (f" returning {return_date}" if return_date else "") +
        ". Return the top results as price, airline, departure/arrival time, stops."
    )
    if notes:
        task += f" The traveler said: {notes!r} — take that into account."
    if broaden:
        task += " No results at the exact dates — widen the search to +/- 2 days."
    browser_agent = BrowserAgent(task=task)
    return await browser_agent.run()


@traced("scraper.search_flights", tool_name="search_flights")
async def search_flights(
    origin: str,
    destination: str,
    depart_date: str,
    return_date: str | None = None,
    notes: str = "",
    broaden: bool = False,
) -> list[dict]:
    """Retry exactly once on failure before raising (NFR-02) — never zero, never unbounded."""
    try:
        return await _run_browser_search(origin, destination, depart_date, return_date, notes, broaden)
    except Exception:
        return await _run_browser_search(origin, destination, depart_date, return_date, notes, broaden)
