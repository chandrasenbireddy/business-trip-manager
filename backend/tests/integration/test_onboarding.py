"""Integration test: waitlist submit -> admin approve -> invite -> combined
OAuth consent -> active user (spec Story 7).

T097 — written before the Story 7 implementation tasks (T098-T104) exist;
MUST fail until then.
"""

from unittest.mock import AsyncMock, patch


def test_full_onboarding_flow(client, admin_cookies):
    email = "onboarding-test@example.com"

    submit_res = client.post("/waitlist", json={"email": email})
    assert submit_res.status_code == 200
    assert submit_res.json()["status"] == "pending"

    # The BFF deliberately never echoes the raw activation token back over
    # HTTP (it only ever leaves via the invite email) — capture it from the
    # mocked send instead of a separate, cross-event-loop DB query.
    with patch("api.routes.waitlist._send_invite_email", AsyncMock()) as mock_send:
        approve_res = client.post(f"/admin/waitlist/{email}/approve", cookies=admin_cookies)
    assert approve_res.status_code == 200
    mock_send.assert_awaited_once()
    _, token = mock_send.call_args.args

    with patch("api.routes.auth.secrets.resolve", lambda ref: "fake-client-id"):
        login_res = client.get(f"/auth/login?token={token}", follow_redirects=False, cookies={})
    assert login_res.status_code in (302, 307)
    assert "accounts.google.com" in login_res.headers["location"]
    assert token in login_res.headers["location"]  # state param carries the invite through

    with patch(
        "api.routes.auth._exchange_code_for_identity",
        AsyncMock(return_value={"email": email, "sub": "google-sub-123"}),
    ):
        callback_res = client.get(f"/auth/callback?code=fake-code&state={token}", follow_redirects=False, cookies={})
    assert callback_res.status_code in (302, 307)
    assert "btm_session" in callback_res.cookies

    # spec Story 7's independent test: "landing in the product" — the session
    # cookie the callback set actually authenticates a real request.
    me_res = client.get("/users/me", cookies={"btm_session": callback_res.cookies["btm_session"]})
    assert me_res.status_code == 200
    assert me_res.json()["user_id"] == email


def test_reused_token_is_rejected(client, admin_cookies):
    email = "reuse-test@example.com"
    client.post("/waitlist", json={"email": email})
    with patch("api.routes.waitlist._send_invite_email", AsyncMock()) as mock_send:
        client.post(f"/admin/waitlist/{email}/approve", cookies=admin_cookies)
    _, token = mock_send.call_args.args

    with patch(
        "api.routes.auth._exchange_code_for_identity",
        AsyncMock(return_value={"email": email, "sub": "google-sub-456"}),
    ):
        first = client.get(f"/auth/callback?code=fake-code&state={token}", follow_redirects=False, cookies={})
        assert first.status_code in (302, 307)

        second = client.get(f"/auth/callback?code=fake-code-2&state={token}", follow_redirects=False, cookies={})
    # spec FR-032: a token already consumed (activate() flipped status away
    # from "invited") must not grant access a second time.
    assert second.status_code == 400
