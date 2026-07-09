"""In-process SSE event bus, keyed by session_id.

ponytail: an asyncio.Queue per session is enough for a single-instance
deployment; move to Redis pub/sub if/when btm-api runs multiple replicas.
"""

import asyncio
import json

_queues: dict[str, asyncio.Queue] = {}


def _queue(session_id: str) -> asyncio.Queue:
    return _queues.setdefault(session_id, asyncio.Queue())


async def publish(session_id: str, event: str, data: dict) -> None:
    await _queue(session_id).put((event, data))


async def subscribe(session_id: str):
    """Async generator of `(event, data)` tuples for use in an SSE response."""
    queue = _queue(session_id)
    while True:
        event, data = await queue.get()
        yield event, data
        if event in ("booking_complete", "error"):
            _queues.pop(session_id, None)
            return


def format_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
