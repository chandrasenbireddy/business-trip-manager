"""Airbnb account tool (PRD AR-07) — not a full agent, called by the Memory
agent at session start (contracts/agent-tools.md).

spec FR-026 (fetch), FR-029 (graceful degradation on cookie_expired,
constitution Principle XI).
"""

from browser_use import Agent as BrowserAgent

from agents.base import traced
from tools import secrets


async def _run_authenticated_session(session_cookie: str) -> dict:
    task = (
        "Using the provided Airbnb session, retrieve: upcoming reservations "
        "(listing, dates, address, confirmation_code, total_price), past stays "
        "in the last 12 months (listing, dates, address, price_paid, user_rating), "
        "and saved wishlist listings."
    )
    browser_agent = BrowserAgent(task=task, session_cookie=session_cookie)
    return await browser_agent.run()


@traced("tools.fetch_airbnb_account", tool_name="fetch_airbnb_account")
async def fetch_airbnb_account(user_id: str) -> dict:
    """`{upcoming_reservations[], past_stays[], wishlist[]}` on success, or
    `{status: "cookie_expired"}` — the caller (agents/memory.py) MUST
    continue with anonymous search rather than propagate a failure (FR-029).
    A traveler who never connected an account at all hits the same
    `cookie_expired` path — from here, "no credential" and "expired
    credential" require the identical degrade-gracefully response.
    """
    try:
        session_cookie = secrets.resolve(f"{user_id}/airbnb_session_cookie")
    except Exception:
        return {"status": "cookie_expired"}

    try:
        result = await _run_authenticated_session(session_cookie)
    except Exception:
        # A session that browser-use can no longer authenticate with (expired
        # server-side) surfaces the same way as a missing credential.
        return {"status": "cookie_expired"}

    return {
        "upcoming_reservations": result.get("upcoming_reservations", []),
        "past_stays": result.get("past_stays", []),
        "wishlist": result.get("wishlist", []),
    }
