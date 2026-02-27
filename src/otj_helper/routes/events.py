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
        """Yield SSE messages from the client queue, with keepalive comments."""
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
