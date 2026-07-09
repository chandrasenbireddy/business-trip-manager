"""Embedding generation for conversation_turns.embedding (data-model.md, PRD AR-04).

ponytail: no embedding provider is wired up yet — returns None until one is
configured via EMBEDDING_API_KEY. Every caller already treats a missing
embedding as "fall back to recency/destination-match only" (memory.py),
so this is a safe no-op until then, not a blocking gap.
"""

import os


async def embed(text: str) -> list[float] | None:
    if not os.environ.get("EMBEDDING_API_KEY"):
        return None
    raise NotImplementedError("wire up the real embedding provider call here")
