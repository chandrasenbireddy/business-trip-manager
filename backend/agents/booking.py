"""Booking agent: execute_booking is the single most safety-critical boundary
in the system (constitution Principle IX) — unreachable unless
session_status == "confirmed". No refactor may remove this check.

spec FR-010/FR-011/FR-012/FR-016.
"""

from agents.base import traced
from agents.models.cost import record_cost_event
from agents.models.tenant import OrganizationTravelPolicy
from tools import events, secrets
from tools.model_router import primary_model


class BookingGateError(Exception):
    """Raised when execute_booking is called outside session_status == 'confirmed'."""


def needs_approval(total_cost: float, policy: OrganizationTravelPolicy) -> bool:
    """spec FR-019: a confirmed itinerary above the tenant's threshold pauses
    booking and notifies the designated approver — this is the check the
    confirm route uses to decide whether to call execute_booking at all.
    """
    return policy.approval_threshold is not None and total_cost > policy.approval_threshold


@traced("booking.notify_approver", tool_name="notify_approver")
async def notify_approver(session_id: str, approver_email: str | None) -> dict:
    """Real implementation sends this via the transactional email service —
    stubbed the same way as send_email pending a live provider (spec FR-019).
    """
    return {"status": "ok", "approver": approver_email}


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
    secrets.resolve(calendar_credentials_ref)
    # Real implementation uses the resolved token to call the Google/Microsoft Calendar API.
    return {"status": "ok"}


@traced("booking.send_email", tool_name="send_email")
async def send_email(itinerary: dict, cost_summary: dict, recipient_address: str) -> dict:
    """Sent via the platform's transactional email credential, not the
    traveler's own account (spec FR-016, research.md §7 — resolved during
    /speckit-analyze, finding C3).
    """
    secrets.resolve("btm/transactional_email_api_key")
    # Real implementation uses the resolved key to call the transactional email provider.
    return {"status": "ok"}


@traced("booking.execute_booking")
async def execute_booking(
    session_id: str, session_status: str, itinerary: dict, tenant_id: str | None = None, user_id: str | None = None
) -> dict:
    if session_status != "confirmed":
        raise BookingGateError(
            f"execute_booking called with session_status={session_status!r}; "
            "MUST be 'confirmed' (constitution Principle IX)"
        )

    # spec FR-021/FR-023. tenant_id/user_id are optional so this dedicated
    # gate test (T028) — which uses a session_id with no real DB row behind
    # it — can exercise the gate without also needing cost-recording infra.
    if tenant_id and user_id:
        await record_cost_event(tenant_id, session_id, user_id, agent_type="booking", model_id=primary_model("booking"))

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
