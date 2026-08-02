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


async def embed(text: str) -> list[float] | None:
    api_key = os.environ.get("NVIDIA_API_KEY") or os.environ.get("EMBEDDING_API_KEY")
    if not api_key:
        return None

    client = AsyncOpenAI(base_url=_NIM_BASE_URL, api_key=api_key)
    # Store turns as passages; retrieval queries should use input_type=query.
    response = await client.embeddings.create(
        model=f"{_EMBED_MODEL}-passage",
        input=text,
    )
    vector = list(response.data[0].embedding)
    if len(vector) != 1024:
        logger.warning("unexpected embedding dim=%s model=%s", len(vector), _EMBED_MODEL)
    return vector
