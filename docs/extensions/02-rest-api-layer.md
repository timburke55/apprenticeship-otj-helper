# Extension 02: REST API Layer

## Overview

Add a versioned JSON REST API (`/api/v1/`) alongside the existing HTML views. This enables external consumers (mobile apps, CLI tools, third-party integrations) to interact with the data programmatically. Includes token-based authentication, pagination, filtering, and full CRUD for activities.

**Complexity drivers:** API design, token authentication, serialisation/deserialisation, pagination, input validation for JSON payloads, error response standardisation, CORS, and versioning strategy.

---

## Prerequisites

- New dependencies: `flask-cors>=4.0` (CORS support)

---

## Step-by-step Implementation

### 1. Add dependencies

**File:** `pyproject.toml`

Add to `dependencies`:
```
"flask-cors>=4.0",
```

Run `uv sync`.

### 2. Create the API token model

**File:** `src/otj_helper/models.py`

Add a new model for API tokens:

```python
class ApiToken(db.Model):
    """A personal API token for programmatic access."""

    __tablename__ = "api_token"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("app_user.id"), nullable=False)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)  # SHA-256 hash
    name = db.Column(db.String(100), nullable=False, default="default")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    user = db.relationship("User", backref="api_tokens")
```

### 3. Add migration for the new table

**File:** `src/otj_helper/app.py`

Add to the `migrations` list in `_migrate_db()`:

```python
(
    "CREATE TABLE IF NOT EXISTS api_token ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
    "user_id INTEGER NOT NULL REFERENCES app_user(id), "
    "token_hash VARCHAR(64) UNIQUE NOT NULL, "
    "name VARCHAR(100) NOT NULL DEFAULT 'default', "
    "created_at DATETIME, "
    "last_used_at DATETIME, "
    "is_active BOOLEAN NOT NULL DEFAULT 1)"
),
```

### 4. Create the API authentication decorator

**New file:** `src/otj_helper/api_auth.py`

```python
"""API authentication via Bearer tokens."""

import hashlib
from functools import wraps

from flask import g, jsonify, request

from otj_helper.models import ApiToken, db


def api_auth_required(f):
    """Decorator: validate Bearer token from Authorization header.

    Sets g.user on success. Returns 401 JSON on failure.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header."}), 401

        raw_token = auth_header[7:]
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        api_token = ApiToken.query.filter_by(
            token_hash=token_hash, is_active=True
        ).first()
        if not api_token:
            return jsonify({"error": "Invalid or revoked API token."}), 401

        from datetime import datetime
        api_token.last_used_at = datetime.utcnow()
        db.session.commit()

        g.user = api_token.user
        return f(*args, **kwargs)

    return decorated
```

### 5. Create the v1 API blueprint

**New file:** `src/otj_helper/routes/api_v1.py`

Implement these endpoints:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/activities` | Paginated list, filters: `?page=`, `?per_page=`, `?ksb=`, `?type=`, `?tag=` |
| GET | `/api/v1/activities/<id>` | Single activity detail |
| POST | `/api/v1/activities` | Create activity from JSON body |
| PUT | `/api/v1/activities/<id>` | Update activity |
| DELETE | `/api/v1/activities/<id>` | Delete activity (returns 204) |
| GET | `/api/v1/ksbs` | List all KSBs for user's spec |
| GET | `/api/v1/stats` | Aggregate dashboard stats |

All endpoints use `@api_auth_required`. All queries scoped to `g.user.id`.

Serialise activities as:
```json
{
    "id": 1,
    "title": "...",
    "description": "...",
    "notes": "...",
    "activity_date": "2024-03-15",
    "duration_hours": 2.5,
    "activity_type": "self_study",
    "evidence_quality": "draft",
    "ksbs": [{"code": "K1", "db_code": "K1", "title": "..."}],
    "tags": [{"id": 1, "name": "systems thinking"}],
    "resources": [{"id": 1, "url": "...", "title": "...", "source_type": "...", "workflow_stage": "..."}],
    "created_at": "2024-03-15T10:30:00",
    "updated_at": "2024-03-15T10:30:00"
}
```

Paginated responses use:
```json
{
    "items": [...],
    "page": 1,
    "per_page": 20,
    "total": 45,
    "pages": 3
}
```

Validation: use the same rules as `_save_activity()` in `routes/activities.py` -- `math.isfinite()`, positive duration, valid activity type, valid ISO date. Return 422 with `{"errors": [...]}`.

### 6. Create a token management page

**New file:** `src/otj_helper/routes/settings.py`

Blueprint at `/settings` with:
- `GET /settings/tokens` -- show user's API tokens
- `POST /settings/tokens/create` -- generate new token (sha256 hash stored, raw shown once)
- `POST /settings/tokens/<id>/revoke` -- deactivate a token

Use `secrets.token_urlsafe(32)` for token generation. Store `hashlib.sha256(raw).hexdigest()`. Flash the raw token once.

### 7. Create the token management template

**New file:** `src/otj_helper/templates/settings/tokens.html`

Extends `base.html`. Contains:
- "Generate new token" button (POST form with CSRF)
- Table: token name, created date, last used date, status (Active/Revoked), Revoke button
- Note: "Copy your token immediately -- it will not be shown again"

### 8. Register blueprints and configure CORS

**File:** `src/otj_helper/app.py`

```python
from flask_cors import CORS
from otj_helper.routes.api_v1 import bp as api_v1_bp
from otj_helper.routes.settings import bp as settings_bp

csrf.exempt(api_v1_bp)
app.register_blueprint(api_v1_bp)
app.register_blueprint(settings_bp)
CORS(app, resources={r"/api/*": {"origins": "*"}})
```

### 9. Add "Settings" link to navigation

**File:** `src/otj_helper/templates/base.html`

Add a "Settings" link in the nav bar pointing to `url_for('settings.tokens')`.

### 10. Write tests

**New file:** `tests/test_api_v1.py`

Create a fixture that generates a test user with an API token:

```python
@pytest.fixture()
def api_headers(app):
    import hashlib, secrets
    from otj_helper.models import ApiToken, User, db
    with app.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        raw = secrets.token_urlsafe(32)
        h = hashlib.sha256(raw.encode()).hexdigest()
        db.session.add(ApiToken(user_id=user.id, token_hash=h))
        db.session.commit()
    return {"Authorization": f"Bearer {raw}"}
```

Test cases:
- Request without Bearer token returns 401
- Request with invalid token returns 401
- `GET /api/v1/activities` returns paginated JSON
- `POST /api/v1/activities` with valid JSON returns 201
- `POST /api/v1/activities` with missing fields returns 422
- `DELETE /api/v1/activities/<id>` returns 204
- `GET /api/v1/ksbs` returns KSBs for user's spec
- `GET /api/v1/stats` returns aggregate stats JSON

---

## Files Changed Summary

| File | Action | Description |
|------|--------|-------------|
| `pyproject.toml` | Edit | Add `flask-cors` dependency |
| `src/otj_helper/models.py` | Edit | Add `ApiToken` model |
| `src/otj_helper/app.py` | Edit | Register blueprints, CORS, CSRF exemption, migration |
| `src/otj_helper/api_auth.py` | Create | Bearer token auth decorator |
| `src/otj_helper/routes/api_v1.py` | Create | REST API v1 blueprint |
| `src/otj_helper/routes/settings.py` | Create | Token management routes |
| `src/otj_helper/templates/settings/tokens.html` | Create | Token management UI |
| `src/otj_helper/templates/base.html` | Edit | Add "Settings" nav link |
| `tests/test_api_v1.py` | Create | API endpoint tests |

---

## Security Considerations

- **Token storage:** Only SHA-256 hash stored in DB. Raw token shown once at creation.
- **CSRF:** API blueprint is CSRF-exempt (JSON-based). Uses Bearer token auth instead.
- **CORS:** Configured for `/api/*` routes with `origins: *`. Tighten for production.
- **Authorization scoping:** All queries filter by `g.user.id`.
- **Rate limiting:** Consider `flask-limiter` for production (e.g. 60 req/min/token).

---

## Testing Checklist

- [ ] `uv run pytest tests/test_api_v1.py` -- all pass
- [ ] `uv run pytest` -- existing tests still pass
- [ ] Manual: generate token via Settings page
- [ ] Manual: `curl -H "Authorization: Bearer <token>" http://localhost:5000/api/v1/activities`
- [ ] Manual: `curl -X POST ... http://localhost:5000/api/v1/activities` with JSON body
- [ ] Manual: revoke token, confirm 401 on subsequent requests
