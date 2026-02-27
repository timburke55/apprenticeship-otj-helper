# Extension 03: Real-time Features with Server-Sent Events (SSE)

## Overview

Add real-time updates to the dashboard using Server-Sent Events (SSE). When a user logs a new activity in another tab/window, the dashboard automatically updates its summary cards and recent activities list without a full page refresh. SSE is chosen over WebSockets because it is simpler, works with Flask's standard request handling, and only requires server-to-client push.

**Complexity drivers:** Event broadcasting, connection lifecycle management, multi-tab coordination, data serialisation for streaming, graceful reconnection, and memory management for long-lived connections.

---

## Prerequisites

No new dependencies required. SSE works with Flask's built-in `Response` streaming. For production with multiple workers, a Redis pub/sub layer would be needed, but for this PoC we use an in-process event queue.

---

## Step-by-step Implementation

### 1. Create the SSE event manager

**New file:** `src/otj_helper/sse.py`

```python
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
```

### 2. Create the SSE streaming route

**New file:** `src/otj_helper/routes/events.py`

```python
"""SSE streaming endpoint for real-time dashboard updates."""

import queue

from flask import Blueprint, Response, g, stream_with_context

from otj_helper.auth import login_required
from otj_helper import sse

bp = Blueprint("events", __name__, url_prefix="/events")


@bp.route("/stream")
@login_required
def stream():
    """SSE endpoint. Sends keepalive comment every 30s to prevent proxy timeouts."""
    user_id = g.user.id
    client_queue = sse.subscribe(user_id)

    @stream_with_context
    def generate():
        try:
            while True:
                try:
                    message = client_queue.get(timeout=30)
                    yield message
                except queue.Empty:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            pass
        finally:
            sse.unsubscribe(user_id, client_queue)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
```

### 3. Publish events when activities are saved or deleted

**File:** `src/otj_helper/routes/activities.py`

At the end of `_save_activity()`, after `db.session.commit()` and before the `flash()` and redirect:

```python
from otj_helper import sse
sse.publish(g.user.id, "activity_saved", {
    "id": activity.id,
    "title": activity.title,
    "duration_hours": round(activity.duration_hours, 1),
    "activity_date": activity.activity_date.isoformat(),
    "ksbs": [k.natural_code for k in activity.ksbs],
})
```

In `delete()`, after `db.session.commit()`:

```python
from otj_helper import sse
sse.publish(g.user.id, "activity_deleted", {"id": activity_id})
```

### 4. Register the events blueprint

**File:** `src/otj_helper/app.py`

```python
from otj_helper.routes.events import bp as events_bp
app.register_blueprint(events_bp)
```

### 5. Add SSE client JavaScript to the dashboard

**File:** `src/otj_helper/templates/dashboard.html`

Add at the end of the existing `<script>` block:

```javascript
// Real-time updates via SSE
(function () {
    if (typeof EventSource === 'undefined') return;

    const evtSource = new EventSource('/events/stream');

    evtSource.addEventListener('activity_saved', function (e) {
        showUpdateBanner('Activity updated -- refreshing...');
        setTimeout(function () { window.location.reload(); }, 1500);
    });

    evtSource.addEventListener('activity_deleted', function (e) {
        showUpdateBanner('Activity deleted -- refreshing...');
        setTimeout(function () { window.location.reload(); }, 1500);
    });

    evtSource.onerror = function () {
        var dot = document.getElementById('sse-status');
        if (dot) {
            dot.className = 'inline-flex h-2 w-2 rounded-full bg-red-400';
            dot.title = 'Disconnected -- reconnecting...';
        }
    };

    evtSource.onopen = function () {
        var dot = document.getElementById('sse-status');
        if (dot) {
            dot.className = 'inline-flex h-2 w-2 rounded-full bg-green-400';
            dot.title = 'Connected -- real-time updates active';
        }
    };

    function showUpdateBanner(text) {
        var existing = document.getElementById('sse-banner');
        if (existing) existing.remove();
        var banner = document.createElement('div');
        banner.id = 'sse-banner';
        banner.className = 'mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 mt-2';
        banner.innerHTML = '<div class="rounded-md p-3 bg-indigo-50 text-indigo-700 text-sm font-medium">' + text + '</div>';
        document.querySelector('main').prepend(banner);
    }
})();
```

### 6. Add connection status indicator to dashboard header

**File:** `src/otj_helper/templates/dashboard.html`

Modify the header `<div>` to include a small status dot:

```html
<div class="flex items-center gap-2 mb-8">
    <h1 class="text-2xl font-bold text-gray-900">OTJ Training Dashboard</h1>
    <span id="sse-status" class="inline-flex h-2 w-2 rounded-full bg-gray-300" title="Real-time updates"></span>
</div>
```

### 7. Write tests

**New file:** `tests/test_sse.py`

```python
"""Tests for the SSE event system."""

from otj_helper import sse


def test_publish_subscribe():
    """Published events are received by subscribers."""
    q = sse.subscribe(user_id=999)
    sse.publish(999, "test_event", {"msg": "hello"})
    message = q.get(timeout=1)
    assert "test_event" in message
    assert "hello" in message
    sse.unsubscribe(999, q)


def test_unsubscribe_cleans_up():
    """After unsubscribe, no queues remain for the user."""
    q = sse.subscribe(user_id=998)
    sse.unsubscribe(998, q)
    sse.publish(998, "test", {})  # Should not raise


def test_stream_endpoint_returns_event_stream(_with_spec, client):
    """GET /events/stream returns text/event-stream content type."""
    resp = client.get("/events/stream")
    assert resp.content_type.startswith("text/event-stream")
```

---

## Files Changed Summary

| File | Action | Description |
|------|--------|-------------|
| `src/otj_helper/sse.py` | Create | In-process pub/sub event manager |
| `src/otj_helper/routes/events.py` | Create | SSE streaming endpoint |
| `src/otj_helper/routes/activities.py` | Edit | Publish events on save/delete |
| `src/otj_helper/app.py` | Edit | Register events blueprint |
| `src/otj_helper/templates/dashboard.html` | Edit | Add SSE client JS + status indicator |
| `tests/test_sse.py` | Create | Unit + integration tests |

---

## Architecture Notes

- **Single-process limitation:** The in-memory `_subscribers` dict only works within a single Gunicorn worker. For multi-worker production, replace with Redis pub/sub.
- **Keepalive:** A comment (`: keepalive\n\n`) is sent every 30s to prevent reverse proxies from closing idle connections.
- **Auto-reconnect:** The browser's `EventSource` API automatically reconnects on connection loss.
- **Full page reload:** For this PoC, the SSE handler triggers a page reload rather than surgically updating DOM elements. A future enhancement could use JSON payloads to update specific cards/charts.

---

## Security Considerations

- **Authentication:** `/events/stream` uses `@login_required`.
- **User isolation:** Events published to a specific `user_id`'s subscriber list only.
- **Memory:** Each client holds a queue with `maxsize=50`. Stale clients are cleaned up when their queue fills.

---

## Testing Checklist

- [ ] `uv run pytest tests/test_sse.py` -- all pass
- [ ] `uv run pytest` -- existing tests still pass
- [ ] Manual: open dashboard in two tabs, log activity in one, see banner in the other
- [ ] Manual: check green status dot appears when connected
- [ ] Manual: kill server, check dot turns red, restart, check it reconnects
