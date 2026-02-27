# Extension 05: Background Task Queue

## Overview

Add a background task processing system using `rq` (Redis Queue) for deferred work: generating reports, sending email digests, running batch analytics. Introduces a separate worker process, a message broker (Redis), task retry/failure handling, progress tracking, and a task status UI.

**Complexity drivers:** Worker process management, message broker dependency, task serialisation, retry logic, failure handling, progress tracking, and deployment configuration for a second process.

---

## Prerequisites

- Redis server running locally (default: `localhost:6379`)
- New dependencies: `rq>=1.16`, `redis>=5.0`

---

## Step-by-step Implementation

### 1. Add dependencies

**File:** `pyproject.toml`

Add to `dependencies`:
```
"rq>=1.16",
"redis>=5.0",
```

Run `uv sync`.

### 2. Create the task queue configuration

**New file:** `src/otj_helper/tasks/__init__.py`

```python
"""Background task queue configuration."""

import os
import logging

from redis import Redis
from rq import Queue

logger = logging.getLogger(__name__)

_redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


def get_redis():
    """Return a Redis connection."""
    return Redis.from_url(_redis_url)


def get_queue(name="default") -> Queue:
    """Return an RQ Queue instance."""
    return Queue(name, connection=get_redis())


def enqueue(func, *args, **kwargs):
    """Enqueue a task. Falls back to synchronous execution if Redis is unavailable.

    This fallback ensures the app works in development without Redis.
    """
    try:
        q = get_queue()
        job = q.enqueue(func, *args, **kwargs)
        logger.info("Enqueued: %s (job_id=%s)", func.__name__, job.id)
        return job
    except Exception as exc:
        logger.warning("Redis unavailable, executing synchronously: %s", exc)
        func(*args, **kwargs)
        return None
```

### 3. Add the TaskResult model

**File:** `src/otj_helper/models.py`

```python
class TaskResult(db.Model):
    """Stores results from background tasks (reports, exports, etc.)."""

    __tablename__ = "task_result"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("app_user.id"), nullable=False)
    task_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    result_data = db.Column(db.Text, nullable=True)
    result_path = db.Column(db.String(500), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", backref="task_results")
```

### 4. Add migration

**File:** `src/otj_helper/app.py`

Add to `_migrate_db()` migrations list:

```python
(
    "CREATE TABLE IF NOT EXISTS task_result ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
    "user_id INTEGER NOT NULL REFERENCES app_user(id), "
    "task_type VARCHAR(50) NOT NULL, "
    "status VARCHAR(20) NOT NULL DEFAULT 'pending', "
    "result_data TEXT, "
    "result_path VARCHAR(500), "
    "error_message TEXT, "
    "created_at DATETIME, "
    "completed_at DATETIME)"
),
```

### 5. Create an example background task

**New file:** `src/otj_helper/tasks/reports.py`

```python
"""Background tasks for report generation."""

import csv
import io
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_full_report(user_id: int, spec_code: str):
    """Generate a comprehensive CSV report for the user.

    Runs inside an RQ worker process (or synchronously as fallback).
    Creates its own app context since it runs outside the request cycle.
    """
    from otj_helper.app import create_app
    from otj_helper.models import Activity, TaskResult, db

    app = create_app()
    with app.app_context():
        logger.info("Generating report for user %d", user_id)

        activities = (
            Activity.query.filter_by(user_id=user_id)
            .order_by(Activity.activity_date.desc())
            .all()
        )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "date", "title", "hours", "type", "evidence_quality",
            "tags", "ksbs", "links", "description", "notes",
        ])

        type_labels = dict(Activity.ACTIVITY_TYPES)
        quality_labels = dict(Activity.EVIDENCE_QUALITY_OPTIONS)

        for a in activities:
            writer.writerow([
                a.activity_date.isoformat(), a.title,
                round(a.duration_hours, 1),
                type_labels.get(a.activity_type, a.activity_type),
                quality_labels.get(a.evidence_quality or "draft", "draft"),
                "; ".join(t.name for t in a.tags),
                "; ".join(k.natural_code for k in a.ksbs),
                "; ".join(r.url for r in a.resources),
                a.description or "", a.notes or "",
            ])

        result = TaskResult(
            user_id=user_id, task_type="full_report",
            status="completed", result_data=output.getvalue(),
            completed_at=datetime.utcnow(),
        )
        db.session.add(result)
        db.session.commit()
        logger.info("Report done for user %d (id=%d)", user_id, result.id)
```

### 6. Create task management routes

**New file:** `src/otj_helper/routes/tasks.py`

```python
bp = Blueprint("tasks", __name__, url_prefix="/tasks")
```

| Method | Path | Description |
|--------|------|-------------|
| GET | `/tasks/` | List user's recent tasks with status badges |
| POST | `/tasks/generate-report` | Enqueue a full report generation task |
| GET | `/tasks/<id>/download` | Download completed task result as CSV |

The list page should auto-refresh (meta tag) when any tasks are pending/running.

### 7. Create the tasks template

**New file:** `src/otj_helper/templates/tasks/list.html`

Extends `base.html`. Contains:
- "Generate Full Report" button (POST form with CSRF)
- Table: task type, status badge (pending=gray, running=blue, completed=green, failed=red), created time, completed time, download link
- Conditional `<meta http-equiv="refresh" content="5">` when pending/running tasks exist

### 8. Register blueprint

**File:** `src/otj_helper/app.py`

```python
from otj_helper.routes.tasks import bp as tasks_bp
app.register_blueprint(tasks_bp)
```

### 9. Add CLI command for the worker

**File:** `src/otj_helper/cli.py`

Add a function to start the RQ worker:

```python
def worker():
    """Start the RQ background worker."""
    from rq import Worker
    from otj_helper.tasks import get_redis, get_queue
    w = Worker([get_queue()], connection=get_redis())
    w.work()
```

### 10. Write tests

**New file:** `tests/test_tasks.py`

```python
def test_task_list_accessible(_with_spec, client):
    """Tasks list returns 200."""
    resp = client.get("/tasks/")
    assert resp.status_code == 200

def test_generate_report_enqueues(_with_spec, client, monkeypatch):
    """POST /tasks/generate-report calls enqueue."""
    enqueued = []
    monkeypatch.setattr(
        "otj_helper.tasks.enqueue",
        lambda func, *a, **kw: enqueued.append(func.__name__),
    )
    resp = client.post("/tasks/generate-report", follow_redirects=True)
    assert resp.status_code == 200
    assert "generate_full_report" in enqueued

def test_synchronous_fallback():
    """Tasks run synchronously when Redis is unavailable."""
    from otj_helper.tasks import enqueue
    results = []
    def fake(x):
        results.append(x)
    enqueue(fake, 42)
    assert 42 in results
```

---

## Files Changed Summary

| File | Action | Description |
|------|--------|-------------|
| `pyproject.toml` | Edit | Add `rq`, `redis` dependencies |
| `src/otj_helper/tasks/__init__.py` | Create | Queue config, enqueue with sync fallback |
| `src/otj_helper/tasks/reports.py` | Create | Report generation task |
| `src/otj_helper/models.py` | Edit | Add `TaskResult` model |
| `src/otj_helper/app.py` | Edit | Migration, register blueprint |
| `src/otj_helper/routes/tasks.py` | Create | Task management routes |
| `src/otj_helper/templates/tasks/list.html` | Create | Task status UI |
| `src/otj_helper/cli.py` | Edit | Add `worker` subcommand |
| `tests/test_tasks.py` | Create | Tests with mocked queue |

---

## Deployment Notes

- **Redis:** Set `REDIS_URL` env var. Railway has a Redis add-on.
- **Worker process:** Run as separate service alongside web server.
- **Graceful fallback:** Without Redis, tasks execute synchronously in the request.

---

## Testing Checklist

- [ ] `uv run pytest tests/test_tasks.py` -- all pass
- [ ] `uv run pytest` -- existing tests still pass
- [ ] Manual: click "Generate Full Report", see it appear in task list
- [ ] Manual (with Redis): start worker, verify task completes, download works
- [ ] Manual (without Redis): verify synchronous fallback works
