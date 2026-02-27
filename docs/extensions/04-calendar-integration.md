# Extension 04: Google Calendar Integration

## Overview

Integrate with Google Calendar to import calendar events as OTJ activities. Events tagged with a configurable label (e.g. "OTJ") are surfaced for one-click import. Users select which events to bring in, and they become Activity records with sensible defaults.

**Complexity drivers:** Google Calendar API (REST), OAuth scope expansion, timezone handling, event-to-activity mapping heuristics, deduplication, and token refresh management.

---

## Prerequisites

- Existing Google OAuth already configured (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`)
- Need to add `https://www.googleapis.com/auth/calendar.readonly` to OAuth scopes
- New dependency: `google-api-python-client>=2.100`

---

## Step-by-step Implementation

### 1. Add dependency

**File:** `pyproject.toml`

Add `"google-api-python-client>=2.100"` to `dependencies`. Run `uv sync`.

### 2. Expand OAuth scopes

**File:** `src/otj_helper/routes/auth.py`

Change the `client_kwargs` in `init_oauth()`:

```python
client_kwargs={
    "scope": "openid email profile https://www.googleapis.com/auth/calendar.readonly"
},
```

Note: existing users will need to re-authenticate.

### 3. Store OAuth access/refresh tokens on User

**File:** `src/otj_helper/models.py`

Add columns to `User`:

```python
google_access_token = db.Column(db.Text, nullable=True)
google_refresh_token = db.Column(db.Text, nullable=True)
google_token_expiry = db.Column(db.DateTime, nullable=True)
```

**File:** `src/otj_helper/app.py` -- add migrations:

```python
"ALTER TABLE app_user ADD COLUMN google_access_token TEXT",
"ALTER TABLE app_user ADD COLUMN google_refresh_token TEXT",
"ALTER TABLE app_user ADD COLUMN google_token_expiry DATETIME",
```

### 4. Store tokens during OAuth callback

**File:** `src/otj_helper/routes/auth.py`

In `callback()`, after `token = oauth.google.authorize_access_token()`:

```python
user.google_access_token = token.get("access_token")
user.google_refresh_token = token.get("refresh_token")
if token.get("expires_at"):
    from datetime import datetime
    user.google_token_expiry = datetime.utcfromtimestamp(token["expires_at"])
db.session.commit()
```

### 5. Create the Google Calendar service helper

**New file:** `src/otj_helper/google_calendar.py`

Key functions:

- `_get_credentials(user)` -- Build `google.oauth2.credentials.Credentials` from stored tokens
- `get_calendar_service(user)` -- Return a `googleapiclient.discovery.build("calendar", "v3", ...)` service
- `fetch_events(user, days_back=30, query="OTJ")` -- Query primary calendar for recent events matching the search term. Return list of dicts with: `id`, `summary`, `start` (datetime), `end` (datetime or None), `duration_hours` (float), `description` (str). Handle both all-day events (`date` field, default 8h) and timed events (`dateTime` field, compute delta).

### 6. Create the calendar import routes

**New file:** `src/otj_helper/routes/calendar.py`

```python
bp = Blueprint("calendar", __name__, url_prefix="/calendar")
```

Routes:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/calendar/import` | Show importable events with search form (query, days_back) |
| POST | `/calendar/import` | Import selected events as Activities |

GET logic:
1. Call `fetch_events(g.user, days_back, query)`
2. Check existing activities for `gcal:<event_id>` in notes field (dedup)
3. Mark events as `already_imported` if found
4. Render template with events list

POST logic:
1. Read `event_ids` from form checkboxes
2. Fetch events again to get fresh data
3. For each selected event, create an `Activity` with:
   - `title` = event summary
   - `description` = event description
   - `activity_date` = event start date
   - `duration_hours` = computed from start/end
   - `activity_type` = "training_course" (default)
   - `notes` = `gcal:<event_id>` (for dedup)
   - `evidence_quality` = "draft"
4. Commit, flash success count, redirect to activities list

### 7. Create the import template

**New file:** `src/otj_helper/templates/calendar/import.html`

Extends `base.html`. Contains:
- Search form: text input for query (default "OTJ"), select for days back (7/14/30/60), submit
- Table of events: checkbox, date, title, duration, description preview
- "Already imported" badge for deduped events (checkbox disabled)
- "Import selected" submit button with CSRF token
- Empty state message when no events found

### 8. Register blueprint and add navigation

**File:** `src/otj_helper/app.py`

```python
from otj_helper.routes.calendar import bp as calendar_bp
app.register_blueprint(calendar_bp)
```

**File:** `src/otj_helper/templates/base.html`

Add "Calendar" link to nav bar: `url_for('calendar.import_events')`.

### 9. Write tests

**New file:** `tests/test_calendar.py`

Mock the Google Calendar API since it requires real credentials:

```python
from unittest.mock import patch

def test_import_page_redirects_without_tokens(_with_spec, client):
    """Import page redirects with flash if calendar not configured."""
    resp = client.get("/calendar/import", follow_redirects=True)
    assert resp.status_code == 200

@patch("otj_helper.google_calendar.fetch_events")
def test_import_page_shows_events(mock_fetch, _with_spec, client):
    """Events from calendar API are rendered on the page."""
    from datetime import datetime
    mock_fetch.return_value = [{
        "id": "evt1", "summary": "OTJ Workshop",
        "start": datetime(2024, 3, 15, 9, 0),
        "end": datetime(2024, 3, 15, 12, 0),
        "duration_hours": 3.0, "description": "Test",
        "already_imported": False,
    }]
    resp = client.get("/calendar/import")
    assert resp.status_code == 200
    assert b"OTJ Workshop" in resp.data
```

---

## Files Changed Summary

| File | Action | Description |
|------|--------|-------------|
| `pyproject.toml` | Edit | Add `google-api-python-client` dependency |
| `src/otj_helper/models.py` | Edit | Add token columns to User |
| `src/otj_helper/app.py` | Edit | Migrations, register blueprint |
| `src/otj_helper/routes/auth.py` | Edit | Expand scopes, store tokens |
| `src/otj_helper/google_calendar.py` | Create | Calendar API service helper |
| `src/otj_helper/routes/calendar.py` | Create | Import routes |
| `src/otj_helper/templates/calendar/import.html` | Create | Event import UI |
| `src/otj_helper/templates/base.html` | Edit | Add "Calendar" nav link |
| `tests/test_calendar.py` | Create | Mocked integration tests |

---

## Security Considerations

- **Token storage:** OAuth tokens stored in DB. Encrypt at rest in production.
- **Scope minimisation:** Only `calendar.readonly` requested -- app cannot modify calendar.
- **Dedup via notes:** Calendar event IDs stored in `notes` field for import dedup. A dedicated column would be cleaner for production.
- **Token refresh:** `google-auth` handles token refresh automatically if refresh token is stored.

---

## Testing Checklist

- [ ] `uv run pytest tests/test_calendar.py` -- all pass
- [ ] `uv run pytest` -- existing tests still pass
- [ ] Manual: navigate to Calendar > Import, verify search form
- [ ] Manual: with real Google credentials, verify events load
- [ ] Manual: import events, verify they appear in Activities
- [ ] Manual: re-visit import, verify "Already imported" badges
