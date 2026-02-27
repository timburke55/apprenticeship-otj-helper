# Extension 08: File Uploads and Evidence Attachments

## Overview

Allow users to attach files (screenshots, certificates, documents) directly to activities, rather than only linking external URLs. Files are stored on the local filesystem (or S3 for production) with metadata in the database. Includes file type validation, size limits, thumbnail generation for images, and a gallery view on activity detail.

**Complexity drivers:** Multipart upload handling, file type validation, storage abstraction (local vs S3), secure file serving, image thumbnailing, size limits, and cleanup of orphaned files.

---

## Prerequisites

- New dependency: `Pillow>=10.0` (for image thumbnailing)
- Storage directory: `data/uploads/` (created automatically)
- Optional for production: `boto3>=1.34` (for S3 storage)

---

## Step-by-step Implementation

### 1. Add dependencies

**File:** `pyproject.toml`

Add `"Pillow>=10.0"` to `dependencies`. Run `uv sync`.

### 2. Create the Attachment model

**File:** `src/otj_helper/models.py`

```python
class Attachment(db.Model):
    """A file attached to an activity."""

    __tablename__ = "attachment"

    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey("activity.id"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)       # Original filename
    stored_name = db.Column(db.String(255), nullable=False)    # UUID-based stored name
    content_type = db.Column(db.String(100), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)          # Bytes
    has_thumbnail = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    activity = db.relationship("Activity", backref="attachments")

    ALLOWED_TYPES: ClassVar[set[str]] = {
        "image/jpeg", "image/png", "image/gif", "image/webp",
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain", "text/markdown",
    }
    MAX_FILE_SIZE: ClassVar[int] = 10 * 1024 * 1024  # 10 MB
```

### 3. Add migration

**File:** `src/otj_helper/app.py`

```python
(
    "CREATE TABLE IF NOT EXISTS attachment ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
    "activity_id INTEGER NOT NULL REFERENCES activity(id), "
    "filename VARCHAR(255) NOT NULL, "
    "stored_name VARCHAR(255) NOT NULL, "
    "content_type VARCHAR(100) NOT NULL, "
    "file_size INTEGER NOT NULL, "
    "has_thumbnail BOOLEAN DEFAULT 0, "
    "created_at DATETIME)"
),
```

### 4. Create the storage service

**New file:** `src/otj_helper/storage.py`

```python
"""File storage abstraction -- local filesystem or S3."""

import os
import uuid
import logging
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

UPLOAD_DIR = os.environ.get(
    "UPLOAD_DIR",
    str(Path(__file__).resolve().parent.parent.parent / "data" / "uploads"),
)
THUMB_SIZE = (200, 200)


def _ensure_dirs():
    """Create upload and thumbnail directories."""
    Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(UPLOAD_DIR, "thumbs").mkdir(parents=True, exist_ok=True)


def save_file(file_obj, content_type: str) -> tuple[str, bool]:
    """Save an uploaded file and optionally generate a thumbnail.

    Args:
        file_obj: Werkzeug FileStorage object.
        content_type: The MIME type.

    Returns:
        Tuple of (stored_name, has_thumbnail).
    """
    _ensure_dirs()

    ext = Path(file_obj.filename or "file").suffix.lower()
    stored_name = f"{uuid.uuid4().hex}{ext}"
    dest = Path(UPLOAD_DIR) / stored_name
    file_obj.save(str(dest))

    has_thumb = False
    if content_type.startswith("image/"):
        try:
            img = Image.open(str(dest))
            img.thumbnail(THUMB_SIZE)
            thumb_path = Path(UPLOAD_DIR) / "thumbs" / stored_name
            img.save(str(thumb_path))
            has_thumb = True
        except Exception as exc:
            logger.warning("Thumbnail generation failed: %s", exc)

    return stored_name, has_thumb


def get_file_path(stored_name: str) -> str:
    """Return the full path to a stored file."""
    return str(Path(UPLOAD_DIR) / stored_name)


def get_thumb_path(stored_name: str) -> str:
    """Return the full path to a thumbnail."""
    return str(Path(UPLOAD_DIR) / "thumbs" / stored_name)


def delete_file(stored_name: str):
    """Delete a stored file and its thumbnail."""
    for path in [get_file_path(stored_name), get_thumb_path(stored_name)]:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
```

### 5. Create upload routes

**New file:** `src/otj_helper/routes/uploads.py`

```python
bp = Blueprint("uploads", __name__, url_prefix="/uploads")
```

| Method | Path | Description |
|--------|------|-------------|
| POST | `/uploads/activity/<id>` | Upload file(s) to an activity |
| GET | `/uploads/<id>/file` | Serve the original file |
| GET | `/uploads/<id>/thumb` | Serve the thumbnail |
| POST | `/uploads/<id>/delete` | Delete an attachment |

Upload validation:
- Check `file.content_type in Attachment.ALLOWED_TYPES`
- Check file size <= `Attachment.MAX_FILE_SIZE`
- Check activity belongs to `g.user.id`
- Use `secure_filename()` from Werkzeug for the original name
- Store via `storage.save_file()`

File serving: use `flask.send_file()` with the correct mimetype. Set `Cache-Control: private, max-age=3600`.

### 6. Add upload UI to activity detail

**File:** `src/otj_helper/templates/activities/detail.html`

Add an "Attachments" section after the CORE Workflow section:

```html
<div class="bg-white shadow rounded-lg p-6 mb-6">
    <h2 class="text-sm font-medium text-gray-500 mb-3">Attachments</h2>

    <!-- Existing attachments -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        {% for att in activity.attachments %}
        <div class="border rounded-lg p-2 text-center">
            {% if att.has_thumbnail %}
            <a href="{{ url_for('uploads.serve_file', attachment_id=att.id) }}" target="_blank">
                <img src="{{ url_for('uploads.serve_thumb', attachment_id=att.id) }}"
                    class="w-full h-24 object-cover rounded" alt="{{ att.filename }}">
            </a>
            {% else %}
            <a href="{{ url_for('uploads.serve_file', attachment_id=att.id) }}" target="_blank"
                class="block p-4 text-indigo-600 hover:text-indigo-500">
                <span class="text-2xl">&#128196;</span>
            </a>
            {% endif %}
            <p class="text-xs text-gray-500 truncate mt-1">{{ att.filename }}</p>
            <p class="text-xs text-gray-400">{{ (att.file_size / 1024)|round(0)|int }} KB</p>
            <form method="post" action="{{ url_for('uploads.delete_attachment', attachment_id=att.id) }}"
                class="mt-1" onsubmit="return confirm('Delete this file?')">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                <button class="text-xs text-red-500 hover:text-red-700">Delete</button>
            </form>
        </div>
        {% endfor %}
    </div>

    <!-- Upload form -->
    <form method="post" action="{{ url_for('uploads.upload', activity_id=activity.id) }}"
        enctype="multipart/form-data" class="flex items-center gap-3">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <input type="file" name="files" multiple accept=".jpg,.jpeg,.png,.gif,.webp,.pdf,.doc,.docx,.txt,.md"
            class="text-sm text-gray-500">
        <button type="submit"
            class="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500">
            Upload
        </button>
    </form>
</div>
```

### 7. Register blueprint

**File:** `src/otj_helper/app.py`

```python
from otj_helper.routes.uploads import bp as uploads_bp
app.register_blueprint(uploads_bp)
```

### 8. Add cascade delete for attachments

When an activity is deleted, its attachments should also be deleted from storage. Add to the `delete()` route in `routes/activities.py`:

```python
from otj_helper.storage import delete_file
for att in activity.attachments:
    delete_file(att.stored_name)
```

The DB records are cleaned up by the existing `cascade="all, delete-orphan"` -- but you need to add `attachments` to Activity's relationships with cascade.

### 9. Write tests

**New file:** `tests/test_uploads.py`

```python
import io

def test_upload_file(_with_spec, client):
    """Upload a file to an activity."""
    # Create activity first
    resp = client.post("/activities/new", data={
        "title": "Upload test", "activity_date": "2024-03-15",
        "duration_hours": "1.0", "activity_type": "self_study",
        "evidence_quality": "draft",
    }, follow_redirects=True)
    assert resp.status_code == 200

    # Upload file
    data = {"files": (io.BytesIO(b"test content"), "test.txt")}
    resp = client.post("/uploads/activity/1", data=data,
                       content_type="multipart/form-data", follow_redirects=True)
    assert resp.status_code == 200

def test_upload_rejects_invalid_type(_with_spec, client):
    """Reject files with disallowed MIME types."""
    client.post("/activities/new", data={
        "title": "Upload test", "activity_date": "2024-03-15",
        "duration_hours": "1.0", "activity_type": "self_study",
    }, follow_redirects=True)

    data = {"files": (io.BytesIO(b"#!/bin/bash"), "script.sh")}
    resp = client.post("/uploads/activity/1", data=data,
                       content_type="multipart/form-data", follow_redirects=True)
    assert resp.status_code == 200  # Redirects with flash error
```

---

## Files Changed Summary

| File | Action | Description |
|------|--------|-------------|
| `pyproject.toml` | Edit | Add `Pillow` dependency |
| `src/otj_helper/models.py` | Edit | Add `Attachment` model |
| `src/otj_helper/app.py` | Edit | Migration, register blueprint |
| `src/otj_helper/storage.py` | Create | File storage service (local + thumbnail) |
| `src/otj_helper/routes/uploads.py` | Create | Upload, serve, delete routes |
| `src/otj_helper/routes/activities.py` | Edit | Cascade delete files on activity delete |
| `src/otj_helper/templates/activities/detail.html` | Edit | Attachments gallery + upload form |
| `tests/test_uploads.py` | Create | Upload and validation tests |

---

## Security Considerations

- **File type validation:** Check `content_type` against allowlist AND validate magic bytes (not just extension).
- **Filename sanitisation:** Use `werkzeug.utils.secure_filename()`.
- **Storage isolation:** Files stored with UUID names, not original names.
- **Size limits:** 10 MB per file. Set `app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024`.
- **Serve securely:** Use `send_file()` with explicit mimetype, not `send_from_directory()`.
- **Authorization:** All routes check `activity.user_id == g.user.id`.

---

## Testing Checklist

- [ ] `uv run pytest tests/test_uploads.py` -- all pass
- [ ] `uv run pytest` -- existing tests still pass
- [ ] Manual: upload an image, verify thumbnail appears
- [ ] Manual: upload a PDF, verify file icon and download link
- [ ] Manual: delete an attachment, verify file removed from disk
- [ ] Manual: delete an activity with attachments, verify files cleaned up
- [ ] Manual: try uploading a .exe -- should be rejected
