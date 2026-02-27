"""Upload, serve, and delete routes for activity file attachments."""

import os

from flask import Blueprint, abort, flash, redirect, send_file, url_for
from flask import request, g
from werkzeug.utils import secure_filename

from otj_helper.auth import login_required
from otj_helper.models import Activity, Attachment, db
from otj_helper import storage

bp = Blueprint("uploads", __name__, url_prefix="/uploads")


@bp.route("/activity/<int:activity_id>", methods=["POST"])
@login_required
def upload(activity_id):
    """Upload one or more files and attach them to an activity."""
    activity = Activity.query.filter_by(id=activity_id, user_id=g.user.id).first_or_404()

    files = request.files.getlist("files")
    if not files or all(f.filename == "" for f in files):
        flash("No files selected.", "error")
        return redirect(url_for("activities.detail", activity_id=activity_id))

    saved = 0
    stored_names: list[str] = []
    for file in files:
        if not file.filename:
            continue

        content_type = file.content_type or ""
        if content_type not in Attachment.ALLOWED_TYPES:
            flash(
                f"{secure_filename(file.filename)}: file type '{content_type}' is not allowed.",
                "error",
            )
            continue

        # Determine file size without fully loading into memory
        file.seek(0, 2)
        size = file.tell()
        file.seek(0)

        if size > Attachment.MAX_FILE_SIZE:
            flash(
                f"{secure_filename(file.filename)}: exceeds the 10 MB size limit.",
                "error",
            )
            continue

        safe_name = secure_filename(file.filename)
        stored_name, has_thumb = storage.save_file(file, content_type)
        stored_names.append(stored_name)

        att = Attachment(
            activity_id=activity.id,
            filename=safe_name,
            stored_name=stored_name,
            content_type=content_type,
            file_size=size,
            has_thumbnail=has_thumb,
        )
        db.session.add(att)
        saved += 1

    if saved:
        try:
            db.session.commit()
            flash(f"{saved} file(s) uploaded.", "success")
        except Exception:
            db.session.rollback()
            for sn in stored_names:
                storage.delete_file(sn)
            flash("Upload failed — please try again.", "error")

    return redirect(url_for("activities.detail", activity_id=activity_id))


@bp.route("/<int:attachment_id>/file")
@login_required
def serve_file(attachment_id):
    """Serve the original uploaded file."""
    att = _get_attachment_or_404(attachment_id)
    path = storage.get_file_path(att.stored_name)
    if not os.path.exists(path):
        abort(404)
    response = send_file(path, mimetype=att.content_type, download_name=att.filename)
    response.headers["Cache-Control"] = "private, max-age=3600"
    return response


@bp.route("/<int:attachment_id>/thumb")
@login_required
def serve_thumb(attachment_id):
    """Serve the thumbnail for an image attachment."""
    att = _get_attachment_or_404(attachment_id)
    if not att.has_thumbnail:
        abort(404)
    path = storage.get_thumb_path(att.stored_name)
    if not os.path.exists(path):
        abort(404)
    response = send_file(path, mimetype=att.content_type)
    response.headers["Cache-Control"] = "private, max-age=3600"
    return response


@bp.route("/<int:attachment_id>/delete", methods=["POST"])
@login_required
def delete_attachment(attachment_id):
    """Delete an attachment and its file from storage."""
    att = _get_attachment_or_404(attachment_id)
    activity_id = att.activity_id
    stored_name = att.stored_name
    db.session.delete(att)
    db.session.commit()
    storage.delete_file(stored_name)
    flash("Attachment deleted.", "info")
    return redirect(url_for("activities.detail", activity_id=activity_id))


def _get_attachment_or_404(attachment_id: int) -> Attachment:
    """Return an attachment belonging to the current user, or raise 404."""
    att = (
        Attachment.query
        .join(Activity)
        .filter(Attachment.id == attachment_id, Activity.user_id == g.user.id)
        .first_or_404()
    )
    return att
