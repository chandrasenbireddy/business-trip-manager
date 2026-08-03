"""Embedding generation for conversation_turns.embedding (data-model.md, PRD AR-04).

Uses NVIDIA NIM (same NVIDIA_API_KEY as model routing). When the key is
absent, returns None so callers keep recency/destination-match retrieval.
"""

import logging
import os

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
# 1024-d — matches migration 0009_embedding_dim_1024.sql
_EMBED_MODEL = "nvidia/nv-embedqa-e5-v5"
_EMBED_DIM = 1024
# Bounded so a slow provider can never stall a trip-creation transaction.
_EMBED_TIMEOUT_SECONDS = 10.0


async def embed(text: str, input_type: str = "passage") -> list[float] | None:
    """Embed `text`, or return None if embedding is unavailable.

    Never raises: embeddings are a retrieval-quality feature, so a provider
    outage degrades to recency/destination-match retrieval rather than
    failing the caller (trip creation stores the turn either way).

    E5/NV-EmbedQA models need `input_type` — "passage" when indexing stored
    turns, "query" at retrieval time. The hosted catalog only accepts it via
    extra_body; the `-passage`/`-query` model-name suffixes are a self-hosted
    NIM convention and 404 here.
    """
    api_key = os.environ.get("NVIDIA_API_KEY") or os.environ.get("EMBEDDING_API_KEY")
    if not api_key:
        return None

    try:
        client = AsyncOpenAI(base_url=_NIM_BASE_URL, api_key=api_key, timeout=_EMBED_TIMEOUT_SECONDS)
        response = await client.embeddings.create(
            model=_EMBED_MODEL,
            input=text,
            extra_body={"input_type": input_type},
        )
        vector = list(response.data[0].embedding)
    except Exception as exc:  # noqa: BLE001 — no embedding failure may reach the caller
        logger.warning(
            "embedding unavailable model=%s input_type=%s error_type=%s",
            _EMBED_MODEL,
            input_type,
            type(exc).__name__,
        )
        return None

    if len(vector) != _EMBED_DIM:
        logger.warning("unexpected embedding dim=%s model=%s", len(vector), _EMBED_MODEL)
        return None
    return vector
