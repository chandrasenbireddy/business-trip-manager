"""WaitlistEntry (data-model.md) — spec FR-031/FR-032.

pending -> approved -> invited -> active. An expired, unused token doesn't
transition state automatically but blocks activation (FR-032) — re-inviting
issues a fresh token rather than reviving the expired one.

waitlist rows aren't tenant-scoped (there's no tenant yet at "pending") —
these queries use tools.db_context.untenanted_connection, not tenant_connection.
"""

import secrets as _secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from tools.db_context import untenanted_connection

TOKEN_EXPIRY_HOURS = 72


@dataclass
class WaitlistEntry:
    email: str
    status: str
    activation_token: str | None = None
    token_expires_at: datetime | None = None


async def submit_request(email: str) -> WaitlistEntry:
    async with untenanted_connection() as conn:
        await conn.execute(
            "INSERT INTO waitlist (email, status) VALUES ($1, 'pending') ON CONFLICT (email) DO NOTHING",
            email,
        )
    return WaitlistEntry(email=email, status="pending")


async def approve_and_invite(email: str) -> WaitlistEntry:
    """Admin action (FR-032): issues a fresh, single-use, 72-hour token —
    always fresh, even for a re-invite of a previously-expired one.
    """
    token = uuid.uuid4().hex + _secrets.token_hex(16)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRY_HOURS)
    async with untenanted_connection() as conn:
        row = await conn.fetchrow(
            "UPDATE waitlist SET status = 'invited', invited_at = now(), activation_token = $1, token_expires_at = $2 "
            "WHERE email = $3 RETURNING email",
            token,
            expires_at,
            email,
        )
    if row is None:
        raise ValueError(f"No waitlist entry for {email!r}")
    return WaitlistEntry(email=email, status="invited", activation_token=token, token_expires_at=expires_at)


async def get_by_token(token: str) -> WaitlistEntry | None:
    async with untenanted_connection() as conn:
        row = await conn.fetchrow("SELECT * FROM waitlist WHERE activation_token = $1", token)
    if row is None:
        return None
    return WaitlistEntry(row["email"], row["status"], row["activation_token"], row["token_expires_at"])


def is_token_valid(entry: WaitlistEntry) -> bool:
    """spec FR-032: an expired token MUST NOT grant access. `status == "invited"`
    excludes a token that's already been consumed (activate() flips it to
    "active", so a reused token no longer matches an "invited" row at all).
    """
    if entry.status != "invited" or entry.token_expires_at is None:
        return False
    return datetime.now(timezone.utc) <= entry.token_expires_at


async def activate(email: str) -> None:
    async with untenanted_connection() as conn:
        await conn.execute("UPDATE waitlist SET status = 'active' WHERE email = $1", email)
