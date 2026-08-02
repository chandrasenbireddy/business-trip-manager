"""Flights scraper: browser-use against Google Flights/Kayak (NFR-02: retry once then error)."""

from browser_use import Agent as BrowserAgent
from browser_use.llm.openai.chat import ChatOpenAI

from agents.base import traced
from tools.model_router import ModelRateLimitError, call_with_fallback, client_config, primary_model


def _browser_llm(which: str = "primary") -> ChatOpenAI:
    cfg = client_config("scraper_flights", which)
    return ChatOpenAI(
        model=cfg["model"],
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        max_retries=0,
    )


async def _run_browser_search(
    origin: str,
    destination: str,
    depart_date: str,
    return_date: str | None,
    notes: str,
    broaden: bool,
) -> list[dict]:
    task = (
        f"Search Google Flights for a flight from {origin} to {destination} "
        f"departing {depart_date}"
        + (f" returning {return_date}" if return_date else "")
        + ". Return the top results as price, airline, departure/arrival time, stops."
    )
    if notes:
        task += f" The traveler said: {notes!r} — take that into account."
    if broaden:
        task += " No results at the exact dates — widen the search to +/- 2 days."
    async def _invoke(model_id: str):
        which = "primary" if model_id == primary_model("scraper_flights") else "fallback"
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

    return await call_with_fallback("scraper_flights", _invoke)


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
