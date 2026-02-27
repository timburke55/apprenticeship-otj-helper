"""Tests for file upload, serving, and deletion."""

import io
import re

import pytest

import otj_helper.storage as storage_module


@pytest.fixture(autouse=True)
def _use_tmp_upload_dir(tmp_path, monkeypatch):
    """Redirect all file storage to a temporary directory for tests."""
    monkeypatch.setattr(storage_module, "UPLOAD_DIR", str(tmp_path))


def _create_activity(client):
    """Create a minimal activity and return (final_response, activity_id).

    The activity ID is parsed from the redirect Location header so no
    out-of-context DB queries are needed.
    """
    redirect_resp = client.post(
        "/activities/new",
        data={
            "title": "Upload test",
            "activity_date": "2024-03-15",
            "duration_hours": "1.0",
            "activity_type": "self_study",
            "evidence_quality": "draft",
        },
        follow_redirects=False,
    )
    location = redirect_resp.headers.get("Location", "")
    match = re.search(r"/activities/(\d+)", location)
    activity_id = int(match.group(1)) if match else None
    # Follow the redirect so callers can assert on the final rendered page
    resp = client.get(location, follow_redirects=True)
    return resp, activity_id


def test_upload_file(_with_spec, client):
    """Upload a plain-text file to an activity."""
    resp, activity_id = _create_activity(client)
    assert resp.status_code == 200

    data = {"files": (io.BytesIO(b"test content"), "test.txt", "text/plain")}
    resp = client.post(
        f"/uploads/activity/{activity_id}",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"1 file(s) uploaded" in resp.data


def test_upload_rejects_invalid_type(_with_spec, client):
    """Reject files with disallowed MIME types."""
    resp, activity_id = _create_activity(client)
    assert resp.status_code == 200

    data = {"files": (io.BytesIO(b"#!/bin/bash"), "script.sh", "application/x-sh")}
    resp = client.post(
        f"/uploads/activity/{activity_id}",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"file(s) uploaded" not in resp.data
    assert b"not allowed" in resp.data


def test_upload_no_files_selected(_with_spec, client):
    """Uploading with no file selected shows an error flash."""
    resp, activity_id = _create_activity(client)
    assert resp.status_code == 200

    resp = client.post(
        f"/uploads/activity/{activity_id}",
        data={},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"No files selected" in resp.data


def test_delete_attachment(_with_spec, client):
    """Deleting an attachment removes it and redirects to the activity."""
    resp, activity_id = _create_activity(client)
    assert resp.status_code == 200

    # Upload a file first, then grab the attachment ID from the redirect location
    upload_redirect = client.post(
        f"/uploads/activity/{activity_id}",
        data={"files": (io.BytesIO(b"hello"), "note.txt", "text/plain")},
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    # The detail page now contains the attachment; scrape its delete URL
    detail_resp = client.get(upload_redirect.headers["Location"])
    match = re.search(rb"/uploads/(\d+)/delete", detail_resp.data)
    assert match, "attachment delete URL not found in detail page"
    att_id = int(match.group(1))

    resp = client.post(f"/uploads/{att_id}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Attachment deleted" in resp.data


def test_upload_to_nonexistent_activity(_with_spec, client):
    """Uploading to a non-existent activity ID returns 404."""
    data = {"files": (io.BytesIO(b"data"), "file.txt", "text/plain")}
    resp = client.post(
        "/uploads/activity/9999",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 404
