"""Contract test for admin endpoints (contracts/bff-api.md).

T066 — written before api/routes/admin.py exists (T072/T073/T076); MUST fail
until then. A non-admin caller MUST get 403, not a filtered/empty response.
"""


def test_put_policy_requires_admin(client, auth_cookies):
    res = client.put("/admin/policy", json={"approval_threshold": 1000}, cookies=auth_cookies)
    assert res.status_code == 403


def test_get_approval_events_requires_admin(client, auth_cookies):
    res = client.get("/admin/approval-events", cookies=auth_cookies)
    assert res.status_code == 403


def test_get_cost_usage_requires_admin(client, auth_cookies):
    res = client.get("/admin/cost-usage", cookies=auth_cookies)
    assert res.status_code == 403


def test_put_policy_succeeds_for_admin(client, admin_cookies):
    res = client.put(
        "/admin/policy",
        json={"approval_threshold": 1000, "approved_airlines": ["SV"]},
        cookies=admin_cookies,
    )
    assert res.status_code == 200
    assert res.json()["policy"]["approval_threshold"] == 1000


def test_get_approval_events_succeeds_for_admin(client, admin_cookies):
    res = client.get("/admin/approval-events", cookies=admin_cookies)
    assert res.status_code == 200
    assert "events" in res.json()


def test_get_cost_usage_succeeds_for_admin(client, admin_cookies):
    res = client.get("/admin/cost-usage", cookies=admin_cookies)
    assert res.status_code == 200
    assert "total" in res.json()
