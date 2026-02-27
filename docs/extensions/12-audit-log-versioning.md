# Extension 12: Audit Log and Activity Versioning

## Overview

Track every change to an activity (who changed what, when) with a full history table. Users can view the change history of any activity, diff between versions, and roll back to a previous version. Introduces event sourcing patterns, temporal data modelling, and a diff rendering UI.

**Complexity drivers:** Temporal data storage, before/after snapshots, JSON serialisation of model state, diff computation, rollback logic, history UI with expandable diffs, and audit trail integrity.

---

## Prerequisites

No new external dependencies. Uses SQLAlchemy events for automatic capture.

---

## Step-by-step Implementation

### 1. Create the AuditLog model

**File:** `src/otj_helper/models.py`

```python
class AuditLog(db.Model):
    """An immutable record of a change to an activity."""

    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey("activity.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("app_user.id"), nullable=False)
    action = db.Column(db.String(20), nullable=False)  # "created", "updated", "deleted"
    changes_json = db.Column(db.Text, nullable=False)   # JSON: {"field": {"old": ..., "new": ...}}
    snapshot_json = db.Column(db.Text, nullable=False)   # Full activity state at this point
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    activity = db.relationship("Activity", backref="audit_logs")
    user = db.relationship("User")
```

### 2. Add migration

**File:** `src/otj_helper/app.py`

```python
(
    "CREATE TABLE IF NOT EXISTS audit_log ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
    "activity_id INTEGER NOT NULL REFERENCES activity(id), "
    "user_id INTEGER NOT NULL REFERENCES app_user(id), "
    "action VARCHAR(20) NOT NULL, "
    "changes_json TEXT NOT NULL, "
    "snapshot_json TEXT NOT NULL, "
    "created_at DATETIME)"
),
```

### 3. Create the audit service

**New file:** `src/otj_helper/audit.py`

```python
"""Audit logging for activity changes."""

import json
import logging
from datetime import date, datetime

from flask import g

from otj_helper.models import AuditLog, db

logger = logging.getLogger(__name__)


def _serialize_value(val):
    """Convert a value to a JSON-safe representation."""
    if isinstance(val, date):
        return val.isoformat()
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, (list, tuple)):
        return [_serialize_value(v) for v in val]
    if hasattr(val, 'code'):  # KSB object
        return val.code
    if hasattr(val, 'name'):  # Tag object
        return val.name
    return val


def snapshot_activity(activity) -> dict:
    """Create a complete snapshot of an activity's current state."""
    return {
        "title": activity.title,
        "description": activity.description or "",
        "notes": activity.notes or "",
        "activity_date": activity.activity_date.isoformat() if activity.activity_date else None,
        "duration_hours": activity.duration_hours,
        "activity_type": activity.activity_type,
        "evidence_quality": activity.evidence_quality or "draft",
        "ksbs": sorted([k.code for k in activity.ksbs]),
        "tags": sorted([t.name for t in activity.tags]),
        "resources": [
            {
                "url": r.url, "title": r.title,
                "source_type": r.source_type,
                "workflow_stage": r.workflow_stage,
            }
            for r in activity.resources
        ],
    }


def compute_changes(old_snapshot: dict, new_snapshot: dict) -> dict:
    """Compare two snapshots and return a dict of changed fields.

    Returns:
        Dict of {field_name: {"old": old_value, "new": new_value}} for fields that differ.
    """
    changes = {}
    all_keys = set(old_snapshot.keys()) | set(new_snapshot.keys())
    for key in all_keys:
        old_val = old_snapshot.get(key)
        new_val = new_snapshot.get(key)
        if old_val != new_val:
            changes[key] = {"old": old_val, "new": new_val}
    return changes


def log_activity_created(activity):
    """Record the creation of a new activity."""
    snap = snapshot_activity(activity)
    entry = AuditLog(
        activity_id=activity.id,
        user_id=g.user.id,
        action="created",
        changes_json=json.dumps({}),
        snapshot_json=json.dumps(snap),
    )
    db.session.add(entry)
    db.session.commit()


def log_activity_updated(activity, old_snapshot: dict):
    """Record an update to an activity by comparing old and new state."""
    new_snap = snapshot_activity(activity)
    changes = compute_changes(old_snapshot, new_snap)

    if not changes:
        return  # No actual changes

    entry = AuditLog(
        activity_id=activity.id,
        user_id=g.user.id,
        action="updated",
        changes_json=json.dumps(changes),
        snapshot_json=json.dumps(new_snap),
    )
    db.session.add(entry)
    db.session.commit()


def log_activity_deleted(activity):
    """Record the deletion of an activity."""
    snap = snapshot_activity(activity)
    entry = AuditLog(
        activity_id=activity.id,
        user_id=g.user.id,
        action="deleted",
        changes_json=json.dumps({}),
        snapshot_json=json.dumps(snap),
    )
    db.session.add(entry)
    db.session.commit()
```

### 4. Integrate audit logging into activity routes

**File:** `src/otj_helper/routes/activities.py`

In `_save_activity()`:

**Before any modifications** (at the top of the function), capture the old state:
```python
from otj_helper.audit import snapshot_activity, log_activity_created, log_activity_updated

is_new = activity.id is None
old_snapshot = snapshot_activity(activity) if not is_new else None
```

**After `db.session.commit()`:**
```python
if is_new:
    log_activity_created(activity)
else:
    log_activity_updated(activity, old_snapshot)
```

In `delete()`, before `db.session.delete(activity)`:
```python
from otj_helper.audit import log_activity_deleted
log_activity_deleted(activity)
```

### 5. Create the history route

**File:** `src/otj_helper/routes/activities.py`

Add a new route:

```python
@bp.route("/<int:activity_id>/history")
@login_required
def history(activity_id):
    """Show the change history for an activity."""
    activity = Activity.query.filter_by(
        id=activity_id, user_id=g.user.id
    ).first_or_404()

    from otj_helper.models import AuditLog
    logs = (
        AuditLog.query
        .filter_by(activity_id=activity_id)
        .order_by(AuditLog.created_at.desc())
        .all()
    )

    import json
    for log_entry in logs:
        log_entry.changes = json.loads(log_entry.changes_json)
        log_entry.snapshot = json.loads(log_entry.snapshot_json)

    return render_template("activities/history.html", activity=activity, logs=logs)
```

### 6. Create the rollback route

```python
@bp.route("/<int:activity_id>/rollback/<int:log_id>", methods=["POST"])
@login_required
def rollback(activity_id, log_id):
    """Restore an activity to a previous version."""
    activity = Activity.query.filter_by(
        id=activity_id, user_id=g.user.id
    ).first_or_404()

    from otj_helper.models import AuditLog
    from otj_helper.audit import snapshot_activity, log_activity_updated

    target_log = AuditLog.query.filter_by(
        id=log_id, activity_id=activity_id
    ).first_or_404()

    import json
    old_snapshot = snapshot_activity(activity)
    target_state = json.loads(target_log.snapshot_json)

    # Apply the snapshot
    activity.title = target_state["title"]
    activity.description = target_state.get("description", "")
    activity.notes = target_state.get("notes", "")
    activity.activity_date = date.fromisoformat(target_state["activity_date"])
    activity.duration_hours = target_state["duration_hours"]
    activity.activity_type = target_state["activity_type"]
    activity.evidence_quality = target_state.get("evidence_quality", "draft")

    # Restore KSBs
    ksb_codes = target_state.get("ksbs", [])
    activity.ksbs = KSB.query.filter(KSB.code.in_(ksb_codes)).all() if ksb_codes else []

    # Restore tags
    from otj_helper.models import Tag
    tag_names = target_state.get("tags", [])
    resolved = []
    for name in tag_names:
        tag = Tag.query.filter_by(name=name, user_id=g.user.id).first()
        if not tag:
            tag = Tag(name=name, user_id=g.user.id)
            db.session.add(tag)
        resolved.append(tag)
    activity.tags = resolved

    db.session.commit()
    log_activity_updated(activity, old_snapshot)

    flash("Activity rolled back to previous version.", "success")
    return redirect(url_for("activities.detail", activity_id=activity_id))
```

### 7. Create the history template

**New file:** `src/otj_helper/templates/activities/history.html`

Extends `base.html`. Shows:

```html
{% extends "base.html" %}
{% block title %}History: {{ activity.title }}{% endblock %}

{% block content %}
<h1 class="text-2xl font-bold text-gray-900 mb-2">Change History</h1>
<p class="text-sm text-gray-500 mb-6">{{ activity.title }}</p>

<div class="space-y-4">
    {% for log_entry in logs %}
    <div class="bg-white shadow rounded-lg p-4">
        <div class="flex justify-between items-start">
            <div>
                <span class="inline-flex items-center rounded px-2 py-0.5 text-xs font-medium
                    {% if log_entry.action == 'created' %}bg-green-100 text-green-800
                    {% elif log_entry.action == 'updated' %}bg-blue-100 text-blue-800
                    {% else %}bg-red-100 text-red-800{% endif %}">
                    {{ log_entry.action }}
                </span>
                <span class="text-sm text-gray-500 ml-2">
                    {{ log_entry.created_at.strftime('%d %b %Y %H:%M') }}
                </span>
            </div>
            {% if log_entry.action != 'deleted' and not loop.first %}
            <form method="post"
                action="{{ url_for('activities.rollback', activity_id=activity.id, log_id=log_entry.id) }}"
                onsubmit="return confirm('Restore this version?')">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                <button class="text-xs text-indigo-600 hover:text-indigo-800">Restore this version</button>
            </form>
            {% endif %}
        </div>

        {% if log_entry.changes %}
        <div class="mt-3 space-y-1">
            {% for field, change in log_entry.changes.items() %}
            <div class="text-sm">
                <span class="font-medium text-gray-700">{{ field }}:</span>
                <span class="text-red-600 line-through">{{ change.old }}</span>
                <span class="text-green-600">{{ change.new }}</span>
            </div>
            {% endfor %}
        </div>
        {% elif log_entry.action == 'created' %}
        <p class="text-sm text-gray-500 mt-2">Activity created</p>
        {% endif %}
    </div>
    {% endfor %}
</div>

<a href="{{ url_for('activities.detail', activity_id=activity.id) }}"
    class="mt-6 inline-block text-sm text-indigo-600 hover:text-indigo-500">Back to activity</a>
{% endblock %}
```

### 8. Add "History" link to activity detail

**File:** `src/otj_helper/templates/activities/detail.html`

Add alongside the Edit/Delete buttons:

```html
<a href="{{ url_for('activities.history', activity_id=activity.id) }}"
    class="rounded-md bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50">
    History
</a>
```

### 9. Register (no new blueprint needed -- routes added to existing activities blueprint)

The history and rollback routes are added to the existing `activities` blueprint, so no new registration is needed.

### 10. Write tests

**New file:** `tests/test_audit.py`

```python
import json

def test_create_activity_creates_audit_log(_with_spec, client, app):
    """Creating an activity creates an audit log entry."""
    client.post("/activities/new", data={
        "title": "Audit test", "activity_date": "2024-03-15",
        "duration_hours": "2.0", "activity_type": "self_study",
        "evidence_quality": "good",
    }, follow_redirects=True)

    from otj_helper.models import AuditLog
    with app.app_context():
        logs = AuditLog.query.all()
        assert len(logs) == 1
        assert logs[0].action == "created"
        snap = json.loads(logs[0].snapshot_json)
        assert snap["title"] == "Audit test"

def test_edit_activity_records_changes(_with_spec, client, app):
    """Editing an activity records the changed fields."""
    # Create
    client.post("/activities/new", data={
        "title": "Original", "activity_date": "2024-03-15",
        "duration_hours": "2.0", "activity_type": "self_study",
    }, follow_redirects=True)

    # Edit
    client.post("/activities/1/edit", data={
        "title": "Updated", "activity_date": "2024-03-15",
        "duration_hours": "3.0", "activity_type": "self_study",
    }, follow_redirects=True)

    from otj_helper.models import AuditLog
    with app.app_context():
        logs = AuditLog.query.filter_by(action="updated").all()
        assert len(logs) == 1
        changes = json.loads(logs[0].changes_json)
        assert "title" in changes
        assert changes["title"]["old"] == "Original"
        assert changes["title"]["new"] == "Updated"

def test_history_page_accessible(_with_spec, client):
    """History page returns 200 for an existing activity."""
    client.post("/activities/new", data={
        "title": "History test", "activity_date": "2024-03-15",
        "duration_hours": "1.0", "activity_type": "self_study",
    }, follow_redirects=True)
    resp = client.get("/activities/1/history")
    assert resp.status_code == 200

def test_rollback_restores_previous_state(_with_spec, client, app):
    """Rolling back restores the activity to a previous snapshot."""
    # Create
    client.post("/activities/new", data={
        "title": "Version 1", "activity_date": "2024-03-15",
        "duration_hours": "2.0", "activity_type": "self_study",
    }, follow_redirects=True)

    # Edit
    client.post("/activities/1/edit", data={
        "title": "Version 2", "activity_date": "2024-03-15",
        "duration_hours": "3.0", "activity_type": "self_study",
    }, follow_redirects=True)

    from otj_helper.models import AuditLog
    with app.app_context():
        first_log = AuditLog.query.filter_by(action="created").first()

    # Rollback to version 1
    resp = client.post(f"/activities/1/rollback/{first_log.id}", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Version 1" in resp.data
```

---

## Files Changed Summary

| File | Action | Description |
|------|--------|-------------|
| `src/otj_helper/models.py` | Edit | Add `AuditLog` model |
| `src/otj_helper/app.py` | Edit | Add migration |
| `src/otj_helper/audit.py` | Create | Snapshot, diff, and logging functions |
| `src/otj_helper/routes/activities.py` | Edit | Add audit calls in save/delete, history + rollback routes |
| `src/otj_helper/templates/activities/history.html` | Create | Change history UI with diffs and rollback |
| `src/otj_helper/templates/activities/detail.html` | Edit | Add "History" link |
| `tests/test_audit.py` | Create | Audit log and rollback tests |

---

## Security Considerations

- **Immutability:** Audit log entries are append-only. No update or delete routes for audit records.
- **Authorization:** History and rollback routes check `activity.user_id == g.user.id`.
- **Rollback creates new entry:** Rolling back creates a new "updated" audit log entry, preserving full history.
- **JSON storage:** Snapshots stored as JSON text. No user-controlled keys in the JSON structure.

---

## Testing Checklist

- [ ] `uv run pytest tests/test_audit.py` -- all pass
- [ ] `uv run pytest` -- existing tests still pass
- [ ] Manual: create activity, verify "created" entry in history
- [ ] Manual: edit activity, verify changes shown as old/new diff
- [ ] Manual: click "Restore this version", verify rollback works
- [ ] Manual: verify rollback creates its own audit entry
- [ ] Manual: delete activity, verify "deleted" entry exists
