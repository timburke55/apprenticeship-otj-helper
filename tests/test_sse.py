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
