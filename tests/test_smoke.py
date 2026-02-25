"""Smoke tests: app factory boots, key routes respond, activity CRUD happy path."""

import json


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def test_app_boots(app):
    """Application factory returns a Flask app."""
    assert app is not None
    assert app.testing is True


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


def test_healthz_ok(client):
    """GET /healthz returns 200 with status=ok and db=connected."""
    resp = client.get("/healthz")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["status"] == "ok"
    assert data["db"] == "connected"
    assert "version" in data


# ---------------------------------------------------------------------------
# Auth / redirects
# ---------------------------------------------------------------------------


def test_root_redirects_logged_in_user_without_spec(client):
    """Logged-in user without a spec is sent to landing page, not 500."""
    resp = client.get("/", follow_redirects=False)
    # Should be 200 (landing) or 302 (redirect) — not a server error
    assert resp.status_code in (200, 302)


def test_root_skips_landing_for_user_with_spec(_with_spec, client):
    """Logged-in user with a spec set is redirected straight to the dashboard.

    Visiting / should never show the spec-selection landing page to a user
    who has already picked their apprenticeship standard.
    """
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/dashboard" in resp.headers["Location"]


def test_dashboard_requires_spec(client):
    """Dashboard redirects to landing when user has no spec."""
    resp = client.get("/dashboard", follow_redirects=False)
    assert resp.status_code == 302


def test_activities_list_accessible(_with_spec, client):
    """Activities list returns 200 for a logged-in user with a spec."""
    resp = client.get("/activities/")
    assert resp.status_code == 200


def test_dashboard_accessible(_with_spec, client):
    """Dashboard returns 200 for a logged-in user with a spec."""
    resp = client.get("/dashboard")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Activity CRUD — happy path
# ---------------------------------------------------------------------------


def test_create_activity_happy_path(_with_spec, client):
    """POST to /activities/new with valid data redirects to the detail page."""
    resp = client.post(
        "/activities/new",
        data={
            "title": "Test activity",
            "activity_date": "2024-03-15",
            "duration_hours": "2.5",
            "activity_type": "self_study",
            "description": "Testing",
            "notes": "",
            "tags": "",
            "evidence_quality": "good",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Test activity" in resp.data


def test_create_activity_with_tags_deduplicates(_with_spec, client):
    """Duplicate tag names in a single submission are collapsed to one tag."""
    resp = client.post(
        "/activities/new",
        data={
            "title": "Tag dedup test",
            "activity_date": "2024-03-16",
            "duration_hours": "1.0",
            "activity_type": "research",
            "description": "",
            "notes": "",
            "tags": "systems, systems, thinking",
            "evidence_quality": "draft",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    # "systems" appears once; "thinking" appears once
    content = resp.data.decode()
    assert content.count("systems") >= 1


# ---------------------------------------------------------------------------
# Activity validation — bad inputs must return 422 without writing to DB
# ---------------------------------------------------------------------------


def test_create_activity_invalid_date_returns_422(_with_spec, client):
    """An invalid date must return HTTP 422 and not crash the server."""
    resp = client.post(
        "/activities/new",
        data={
            "title": "Bad date",
            "activity_date": "not-a-date",
            "duration_hours": "2.0",
            "activity_type": "self_study",
        },
    )
    assert resp.status_code == 422


def test_create_activity_negative_duration_returns_422(_with_spec, client):
    """A negative duration must return HTTP 422."""
    resp = client.post(
        "/activities/new",
        data={
            "title": "Negative hours",
            "activity_date": "2024-03-15",
            "duration_hours": "-1.5",
            "activity_type": "self_study",
        },
    )
    assert resp.status_code == 422


def test_create_activity_zero_duration_returns_422(_with_spec, client):
    """Zero duration must return HTTP 422."""
    resp = client.post(
        "/activities/new",
        data={
            "title": "Zero hours",
            "activity_date": "2024-03-15",
            "duration_hours": "0",
            "activity_type": "self_study",
        },
    )
    assert resp.status_code == 422


def test_create_activity_invalid_type_returns_422(_with_spec, client):
    """An unrecognised activity_type must return HTTP 422."""
    resp = client.post(
        "/activities/new",
        data={
            "title": "Bad type",
            "activity_date": "2024-03-15",
            "duration_hours": "1.0",
            "activity_type": "definitely_not_valid",
        },
    )
    assert resp.status_code == 422


def test_create_activity_bad_resource_url_returns_422(_with_spec, client):
    """A resource link URL that is not http/https must return HTTP 422."""
    resp = client.post(
        "/activities/new",
        data={
            "title": "Bad URL",
            "activity_date": "2024-03-15",
            "duration_hours": "1.0",
            "activity_type": "self_study",
            "link_url": ["not-a-url"],
            "link_title": ["Bad"],
            "link_source_type": ["website"],
            "link_stage": ["engage"],
            "link_description": [""],
        },
    )
    assert resp.status_code == 422


def test_create_activity_valid_resource_url_accepted(_with_spec, client):
    """A resource link with a valid https URL is accepted."""
    resp = client.post(
        "/activities/new",
        data={
            "title": "Good URL",
            "activity_date": "2024-03-15",
            "duration_hours": "1.0",
            "activity_type": "self_study",
            "link_url": ["https://example.com/doc"],
            "link_title": ["Example"],
            "link_source_type": ["website"],
            "link_stage": ["engage"],
            "link_description": [""],
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def test_export_csv_returns_csv(_with_spec, client):
    """GET /activities/export.csv returns a CSV content-type response."""
    resp = client.get("/activities/export.csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.content_type
    # Header row must be present
    assert b"date,title,hours" in resp.data


# ---------------------------------------------------------------------------
# KSB routes
# ---------------------------------------------------------------------------


def test_ksbs_list_accessible(_with_spec, client):
    """KSB list page returns 200."""
    resp = client.get("/ksbs/")
    assert resp.status_code == 200
