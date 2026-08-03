"""Unit tests for tools/embeddings.py NIM wiring."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools import embeddings


@pytest.mark.asyncio
async def test_embed_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    assert await embeddings.embed("hello") is None


@pytest.mark.asyncio
async def test_embed_calls_nim_when_nvidia_key_present(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)

    fake_response = MagicMock()
    fake_response.data = [MagicMock(embedding=[0.1] * 1024)]
    fake_client = MagicMock()
    fake_client.embeddings.create = AsyncMock(return_value=fake_response)
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=None)

    with patch("tools.embeddings.AsyncOpenAI", return_value=fake_client):
        vector = await embeddings.embed("trip to Riyadh")

    fake_client.embeddings.create.assert_awaited_once()
    call_kwargs = fake_client.embeddings.create.await_args.kwargs
    # The hosted NIM catalog rejects the self-hosted `-passage` model suffix.
    assert call_kwargs["model"] == "nvidia/nv-embedqa-e5-v5"
    assert call_kwargs["extra_body"] == {"input_type": "passage"}
    assert len(vector) == 1024


@pytest.mark.asyncio
async def test_embed_returns_none_when_provider_fails(monkeypatch):
    """An embedding outage must never fail the caller (trip creation)."""
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")

    fake_client = MagicMock()
    fake_client.embeddings.create = AsyncMock(side_effect=RuntimeError("404 page not found"))

    with patch("tools.embeddings.AsyncOpenAI", return_value=fake_client):
        assert await embeddings.embed("trip to Riyadh") is None


@pytest.mark.asyncio
async def test_embed_returns_none_on_unexpected_dimension(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")

    fake_response = MagicMock()
    fake_response.data = [MagicMock(embedding=[0.1] * 768)]
    fake_client = MagicMock()
    fake_client.embeddings.create = AsyncMock(return_value=fake_response)

    with patch("tools.embeddings.AsyncOpenAI", return_value=fake_client):
        assert await embeddings.embed("trip to Riyadh") is None
