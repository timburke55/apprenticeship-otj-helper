"""Server-Sent Events (SSE) broadcast manager.

Maintains per-user queues of connected clients. When an event is published
for a user, it is pushed to all their connected SSE streams.
"""

import json
import queue
import threading
import logging

logger = logging.getLogger(__name__)

# Map of user_id -> list of queue.Queue instances (one per connected client)
_subscribers: dict[int, list[queue.Queue]] = {}
_lock = threading.Lock()


def subscribe(user_id: int) -> queue.Queue:
    """Register a new SSE client for the given user. Returns a Queue to read from."""
    q = queue.Queue(maxsize=50)
    with _lock:
        _subscribers.setdefault(user_id, []).append(q)
    return q


def unsubscribe(user_id: int, q: queue.Queue):
    """Remove a client queue when the SSE connection closes."""
    with _lock:
        clients = _subscribers.get(user_id, [])
        if q in clients:
            clients.remove(q)
        if not clients:
            _subscribers.pop(user_id, None)


def publish(user_id: int, event_type: str, data: dict):
    """Push an event to all connected SSE clients for the given user."""
    message = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    with _lock:
        clients = _subscribers.get(user_id, [])
        dead = []
        for q in clients:
            try:
                q.put_nowait(message)
            except queue.Full:
                dead.append(q)
        for q in dead:
            clients.remove(q)
