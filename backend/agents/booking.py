"""Booking agent: execute_booking is the single most safety-critical boundary
in the system (constitution Principle IX) — unreachable unless
session_status == "confirmed". No refactor may remove this check.

spec FR-010/FR-011/FR-012/FR-016.
"""

from agents.base import traced
from tools import events, secrets


class BookingGateError(Exception):
    """Raised when execute_booking is called outside session_status == 'confirmed'."""


@traced("booking.book_flight", tool_name="book_flight")
async def book_flight(itinerary: dict) -> dict:
    # v1: open the provider link / pre-fill — no stored payment, no autonomous
    # purchase (spec FR-012). Real implementation drives a browser-use session
    # to the provider's booking page with fields pre-filled.
    flight = itinerary.get("flight") or itinerary.get("selections", {}).get("flight", {})
    return {"status": "link_ready", "provider_url": flight.get("provider_url", "")}


@traced("booking.book_airbnb", tool_name="book_airbnb")
async def book_airbnb(itinerary: dict) -> dict:
    accommodation = itinerary.get("accommodation") or itinerary.get("selections", {}).get("accommodation", {})
    return {"status": "link_ready", "provider_url": accommodation.get("provider_url", "")}


@traced("booking.add_to_calendar", tool_name="add_to_calendar")
async def add_to_calendar(itinerary: dict, calendar_credentials_ref: str) -> dict:
    """Uses the traveler's own OAuth token reference (spec FR-015)."""
    token = secrets.resolve(calendar_credentials_ref)
    # Real implementation calls the Google/Microsoft Calendar API with `token`.
    return {"status": "ok"}


@traced("booking.send_email", tool_name="send_email")
async def send_email(itinerary: dict, cost_summary: dict, recipient_address: str) -> dict:
    """Sent via the platform's transactional email credential, not the
    traveler's own account (spec FR-016, research.md §7 — resolved during
    /speckit-analyze, finding C3).
    """
    api_key = secrets.resolve("btm/transactional_email_api_key")
    # Real implementation calls the transactional email provider with `api_key`.
    return {"status": "ok"}


@traced("booking.execute_booking")
async def execute_booking(session_id: str, session_status: str, itinerary: dict) -> dict:
    if session_status != "confirmed":
        raise BookingGateError(
            f"execute_booking called with session_status={session_status!r}; "
            "MUST be 'confirmed' (constitution Principle IX)"
        )

    # Each step is reported independently, not collapsed into one status
    # (spec Edge Cases) — a calendar failure must not mask a successful flight step.
    results = {}
    for step, coro in (
        ("flight", book_flight(itinerary)),
        ("accommodation", book_airbnb(itinerary)),
    ):
        try:
            results[step] = await coro
            await events.publish(session_id, "booking_progress", {"step": step, "status": "ok"})
        except Exception as exc:  # noqa: BLE001 — one step's failure must not abort the others
            results[step] = {"status": "failed", "error": str(exc)}
            await events.publish(session_id, "booking_progress", {"step": step, "status": "failed"})

    try:
        results["calendar"] = await add_to_calendar(itinerary, calendar_credentials_ref=f"{session_id}/google_calendar_token")
        await events.publish(session_id, "booking_progress", {"step": "calendar", "status": "ok"})
    except Exception as exc:  # noqa: BLE001
        results["calendar"] = {"status": "failed", "error": str(exc)}
        await events.publish(session_id, "booking_progress", {"step": "calendar", "status": "failed"})

    try:
        results["email"] = await send_email(itinerary, cost_summary={}, recipient_address="")
        await events.publish(session_id, "booking_progress", {"step": "email", "status": "ok"})
    except Exception as exc:  # noqa: BLE001
        results["email"] = {"status": "failed", "error": str(exc)}
        await events.publish(session_id, "booking_progress", {"step": "email", "status": "failed"})

    await events.publish(session_id, "booking_complete", {"itinerary": itinerary, "report_url": ""})
    return {"status": "booking", "steps": results}
