"""Session close sets closed_at for episodic retrieval."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.models.session import update_session_status


@pytest.mark.asyncio
async def test_update_session_status_closed_sets_closed_at():
    conn = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("agents.models.session.tenant_connection", return_value=cm):
        await update_session_status("t1", "s1", "closed")

    sql = conn.execute.await_args.args[0]
    assert "closed_at = now()" in sql
    assert conn.execute.await_args.args[1:] == ("closed", "s1")


@pytest.mark.asyncio
async def test_update_session_status_other_does_not_touch_closed_at():
    conn = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("agents.models.session.tenant_connection", return_value=cm):
        await update_session_status("t1", "s1", "confirmed")

    sql = conn.execute.await_args.args[0]
    assert "closed_at" not in sql
