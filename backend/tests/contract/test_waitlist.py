"""Contract test for POST /waitlist and the admin-approval -> invite-issuance
flow (72-hour expiry, single-use token, spec FR-032).

T096 — written before these endpoints exist (T099/T100); MUST fail until then.
"""

from datetime import datetime, timedelta, timezone

from agents.models.waitlist import approve_and_invite, get_by_token, is_token_valid


def test_post_waitlist_is_unauthenticated_and_returns_pending(client):
    res = client.post("/waitlist", json={"email": "newuser@example.com"})
    assert res.status_code == 200
    assert res.json()["status"] == "pending"


def test_admin_approval_requires_admin(client, auth_cookies):
    client.post("/waitlist", json={"email": "another@example.com"})
    res = client.post("/admin/waitlist/another@example.com/approve", cookies=auth_cookies)
    assert res.status_code == 403


async def test_approve_and_invite_issues_a_72_hour_single_use_token():
    email = "invitee@example.com"
    from agents.models.waitlist import submit_request

    await submit_request(email)
    entry = await approve_and_invite(email)

    assert entry.activation_token is not None
    assert entry.status == "invited"
    expected_expiry = datetime.now(timezone.utc) + timedelta(hours=72)
    assert abs((entry.token_expires_at - expected_expiry).total_seconds()) < 5

    fetched = await get_by_token(entry.activation_token)
    assert is_token_valid(fetched)


async def test_expired_token_is_rejected():
    email = "expired@example.com"
    from agents.models.waitlist import submit_request

    await submit_request(email)
    entry = await approve_and_invite(email)

    from tools.db_context import untenanted_connection

    async with untenanted_connection() as conn:
        await conn.execute(
            "UPDATE waitlist SET token_expires_at = $1 WHERE email = $2",
            datetime.now(timezone.utc) - timedelta(hours=1),
            email,
        )

    fetched = await get_by_token(entry.activation_token)
    assert not is_token_valid(fetched)


async def test_reinviting_issues_a_fresh_token_not_reviving_the_old_one():
    email = "reinvite@example.com"
    from agents.models.waitlist import submit_request

    await submit_request(email)
    first = await approve_and_invite(email)
    second = await approve_and_invite(email)

    assert first.activation_token != second.activation_token
    stale = await get_by_token(first.activation_token)
    # the old token no longer matches any row's *current* activation_token
    assert stale is None
