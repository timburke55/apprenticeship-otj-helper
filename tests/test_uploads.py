"""Tests for file upload, serving, and deletion."""

import io

import pytest

import otj_helper.storage as storage_module


@pytest.fixture(autouse=True)
def _use_tmp_upload_dir(tmp_path, monkeypatch):
    """Redirect all file storage to a temporary directory for tests."""
    monkeypatch.setattr(storage_module, "UPLOAD_DIR", str(tmp_path))


def _create_activity(client):
    """Helper to create a minimal activity and return the response."""
    return client.post(
        "/activities/new",
        data={
            "title": "Upload test",
            "activity_date": "2024-03-15",
            "duration_hours": "1.0",
            "activity_type": "self_study",
            "evidence_quality": "draft",
        },
        follow_redirects=True,
    )


def test_upload_file(_with_spec, client):
    """Upload a plain-text file to an activity."""
    resp = _create_activity(client)
    assert resp.status_code == 200

    data = {"files": (io.BytesIO(b"test content"), "test.txt", "text/plain")}
    resp = client.post(
        "/uploads/activity/1",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"1 file(s) uploaded" in resp.data


def test_upload_rejects_invalid_type(_with_spec, client):
    """Reject files with disallowed MIME types."""
    resp = _create_activity(client)
    assert resp.status_code == 200

    data = {"files": (io.BytesIO(b"#!/bin/bash"), "script.sh", "application/x-sh")}
    resp = client.post(
        "/uploads/activity/1",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"file(s) uploaded" not in resp.data
    assert b"not allowed" in resp.data


def test_upload_no_files_selected(_with_spec, client):
    """Uploading with no file selected shows an error flash."""
    resp = _create_activity(client)
    assert resp.status_code == 200

    resp = client.post(
        "/uploads/activity/1",
        data={},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"No files selected" in resp.data


def test_delete_attachment(_with_spec, client):
    """Deleting an attachment removes it and redirects to the activity."""
    resp = _create_activity(client)
    assert resp.status_code == 200

    data = {"files": (io.BytesIO(b"hello"), "note.txt", "text/plain")}
    client.post(
        "/uploads/activity/1",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    resp = client.post(
        "/uploads/1/delete",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Attachment deleted" in resp.data


def test_upload_requires_activity_ownership(_with_spec, client):
    """Uploading to a nonexistent activity returns 404."""
    data = {"files": (io.BytesIO(b"data"), "file.txt", "text/plain")}
    resp = client.post(
        "/uploads/activity/9999",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 404
