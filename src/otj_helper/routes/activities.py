"""Activity CRUD routes."""

import csv
import io
import math
from datetime import date
from urllib.parse import urlparse

from flask import Blueprint, Response, flash, g, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from otj_helper.auth import login_required
from otj_helper.models import Activity, Attachment, KSB, ResourceLink, Tag, db
from otj_helper import storage

# Which source types are surfaced per CORE stage (first entry is the default)
_STAGE_SOURCE_TYPES = {
    "capture": ["google_keep", "website", "other"],
    "organise": ["google_tasks", "website", "other"],
    "review": ["google_docs", "diagram", "markdown", "google_drive", "other"],
    "engage": ["google_docs", "google_drive", "github", "diagram", "markdown", "website", "other"],
}

_VALID_ACTIVITY_TYPES = {t for t, _ in Activity.ACTIVITY_TYPES}
_VALID_WORKFLOW_STAGES = {s for s, _, _, _ in ResourceLink.WORKFLOW_STAGES}
_VALID_SOURCE_TYPES = {s for s, _ in ResourceLink.SOURCE_TYPES}
_VALID_EVIDENCE_QUALITIES = {v for v, _ in Activity.EVIDENCE_QUALITY_OPTIONS}

bp = Blueprint("activities", __name__, url_prefix="/activities")


def _validate_url(url: str) -> bool:
    """Return True if *url* is a well-formed http or https URL."""
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _form_context(activity):
    """Return the template-context dict needed to render the activity form."""
    spec = g.user.selected_spec or "ST0787"
    return dict(
        activity=activity,
        all_ksbs=KSB.query.filter_by(spec_code=spec).order_by(KSB.code).all(),
        activity_types=Activity.ACTIVITY_TYPES,
        evidence_quality_options=Activity.EVIDENCE_QUALITY_OPTIONS,
        source_types=ResourceLink.SOURCE_TYPES,
        workflow_stages=ResourceLink.WORKFLOW_STAGES,
        stage_source_types=_STAGE_SOURCE_TYPES,
        user_tags=Tag.query.filter_by(user_id=g.user.id).order_by(Tag.name).all(),
    )


@bp.route("/")
@login_required
def list_activities():
    """List activities for the current user, with optional KSB/type/tag filters."""
    page = request.args.get("page", 1, type=int)
    ksb_filter = request.args.get("ksb", None)
    type_filter = request.args.get("type", None)
    tag_filter = request.args.get("tag", None, type=int)

    query = Activity.query.filter_by(user_id=g.user.id)

    if ksb_filter:
        query = query.filter(Activity.ksbs.any(KSB.code == ksb_filter))
    if type_filter:
        query = query.filter(Activity.activity_type == type_filter)
    if tag_filter is not None:
        query = query.filter(Activity.tags.any(Tag.id == tag_filter))

    activities = query.order_by(Activity.activity_date.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    spec = g.user.selected_spec or "ST0787"
    all_ksbs = KSB.query.filter_by(spec_code=spec).order_by(KSB.code).all()
    user_tags = Tag.query.filter_by(user_id=g.user.id).order_by(Tag.name).all()
    return render_template(
        "activities/list.html",
        activities=activities,
        all_ksbs=all_ksbs,
        activity_types=Activity.ACTIVITY_TYPES,
        ksb_filter=ksb_filter,
        type_filter=type_filter,
        tag_filter=tag_filter,
        user_tags=user_tags,
    )


@bp.route("/export.csv")
@login_required
def export_csv():
    """Export filtered activities as a CSV download.

    Accepts the same ``ksb``, ``type``, and ``tag`` query parameters as the
    activity list view so the export honours any active filters.
    """
    ksb_filter = request.args.get("ksb", None)
    type_filter = request.args.get("type", None)
    tag_filter = request.args.get("tag", None, type=int)

    query = Activity.query.filter_by(user_id=g.user.id)

    if ksb_filter:
        query = query.filter(Activity.ksbs.any(KSB.code == ksb_filter))
    if type_filter:
        query = query.filter(Activity.activity_type == type_filter)
    if tag_filter is not None:
        query = query.filter(Activity.tags.any(Tag.id == tag_filter))

    activities = query.order_by(Activity.activity_date.desc()).all()

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
            a.activity_date.isoformat(),
            a.title,
            round(a.duration_hours, 1),
            type_labels.get(a.activity_type, a.activity_type),
            quality_labels.get(a.evidence_quality or "draft", a.evidence_quality or "draft"),
            "; ".join(t.name for t in a.tags),
            "; ".join(k.natural_code for k in a.ksbs),
            "; ".join(r.url for r in a.resources),
            a.description or "",
            a.notes or "",
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=activities.csv"},
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    """Show the new-activity form (GET) or save a new activity (POST)."""
    if request.method == "POST":
        return _save_activity(Activity())

    return render_template("activities/form.html", **_form_context(None))


@bp.route("/<int:activity_id>")
@login_required
def detail(activity_id):
    """Show the detail view for a single activity."""
    activity = Activity.query.filter_by(id=activity_id, user_id=g.user.id).first_or_404()
    return render_template("activities/detail.html", activity=activity)


@bp.route("/<int:activity_id>/edit", methods=["GET", "POST"])
@login_required
def edit(activity_id):
    """Show the edit form for an activity (GET) or save changes (POST)."""
    activity = Activity.query.filter_by(id=activity_id, user_id=g.user.id).first_or_404()

    if request.method == "POST":
        return _save_activity(activity)

    return render_template("activities/form.html", **_form_context(activity))


@bp.route("/<int:activity_id>/delete", methods=["POST"])
@login_required
def delete(activity_id):
    """Delete an activity and redirect to the activity list."""
    activity = Activity.query.filter_by(id=activity_id, user_id=g.user.id).first_or_404()
    for att in activity.attachments:
        storage.delete_file(att.stored_name)
    db.session.delete(activity)
    db.session.commit()
    flash("Activity deleted.", "info")
    return redirect(url_for("activities.list_activities"))


def _save_uploaded_files(activity):
    """Process any files submitted with the activity form and attach them to *activity*.

    Silently skips empty file inputs.  Flashes per-file error messages for
    invalid types or oversized files.  On DB commit failure all stored files
    are cleaned up so no orphans are left on disk.
    """
    files = request.files.getlist("files")
    stored_names: list[str] = []
    saved = 0
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

        file.seek(0, 2)
        size = file.tell()
        file.seek(0)

        if size > Attachment.MAX_FILE_SIZE:
            flash(
                f"{secure_filename(file.filename)}: exceeds the 10 MB size limit.",
                "error",
            )
            continue

        stored_name, has_thumb = storage.save_file(file, content_type)
        stored_names.append(stored_name)
        db.session.add(Attachment(
            activity_id=activity.id,
            filename=secure_filename(file.filename),
            stored_name=stored_name,
            content_type=content_type,
            file_size=size,
            has_thumbnail=has_thumb,
        ))
        saved += 1

    if saved:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            for sn in stored_names:
                storage.delete_file(sn)
            flash("Files could not be saved — please try uploading them again.", "error")


def _save_activity(activity):
    """Validate form data then save or update *activity*.

    Returns a redirect on success.  On validation failure, flashes error
    messages and re-renders the form with HTTP 422 so no DB write occurs.
    """
    errors = []

    # --- Date ---
    try:
        activity_date = date.fromisoformat(request.form["activity_date"])
    except (ValueError, KeyError):
        errors.append("Date is invalid or missing — please use the date picker.")
        activity_date = None

    # --- Duration ---
    try:
        duration = float(request.form["duration_hours"])
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("Duration must be a positive finite number.")
    except (ValueError, KeyError):
        errors.append("Duration must be a positive number greater than zero (e.g. 2.5).")
        duration = None

    # --- Activity type ---
    activity_type = request.form.get("activity_type", "")
    if activity_type not in _VALID_ACTIVITY_TYPES:
        errors.append(f"Activity type '{activity_type}' is not recognised.")
        activity_type = None

    # --- Evidence quality (optional; default to draft) ---
    evidence_quality = request.form.get("evidence_quality", "draft")
    if evidence_quality not in _VALID_EVIDENCE_QUALITIES:
        evidence_quality = "draft"

    # --- Resource link URLs ---
    link_urls_raw = request.form.getlist("link_url")
    bad_urls = [u for u in link_urls_raw if u.strip() and not _validate_url(u.strip())]
    if bad_urls:
        sample = ", ".join(bad_urls[:3])
        errors.append(f"Resource link URL(s) must start with http:// or https://: {sample}")

    # --- Populate submitted values onto the activity so re-renders are pre-filled ---
    activity.title = request.form.get("title", "")
    activity.description = request.form.get("description", "")
    activity.notes = request.form.get("notes", "")
    activity.activity_type = activity_type or ""
    activity.evidence_quality = evidence_quality
    activity.activity_date = activity_date   # may be None if parse failed; template handles it
    activity.duration_hours = duration       # may be None if parse failed; template handles it

    # --- Early return on errors (no DB writes have occurred) ---
    if errors:
        for msg in errors:
            flash(msg, "error")
        return render_template("activities/form.html", **_form_context(activity)), 422

    # --- KSBs: constrain to the user's selected spec ---
    spec = g.user.selected_spec or "ST0787"
    selected_codes = request.form.getlist("ksbs")
    activity.ksbs = KSB.query.filter(
        KSB.code.in_(selected_codes), KSB.spec_code == spec
    ).all()

    # Assign owner on new activities
    if not activity.id:
        activity.user_id = g.user.id

    # --- Tags: deduplicate while preserving submission order ---
    raw_tags = request.form.get("tags", "")
    seen = dict.fromkeys(
        t.strip().lower() for t in raw_tags.split(",") if t.strip().lower()
    )
    resolved_tags = []
    for name in seen:
        tag = Tag.query.filter_by(name=name, user_id=g.user.id).first()
        if not tag:
            tag = Tag(name=name, user_id=g.user.id)
            db.session.add(tag)
        resolved_tags.append(tag)
    activity.tags = resolved_tags

    # --- Resource links ---
    if activity.id:
        ResourceLink.query.filter_by(activity_id=activity.id).delete()

    link_titles = request.form.getlist("link_title")
    link_types = request.form.getlist("link_source_type")
    link_descriptions = request.form.getlist("link_description")
    link_stages = request.form.getlist("link_stage")

    for i, raw_url in enumerate(link_urls_raw):
        url = raw_url.strip()
        if not url:
            continue
        source_type = link_types[i] if i < len(link_types) else "other"
        if source_type not in _VALID_SOURCE_TYPES:
            source_type = "other"
        workflow_stage = link_stages[i] if i < len(link_stages) else "engage"
        if workflow_stage not in _VALID_WORKFLOW_STAGES:
            workflow_stage = "engage"
        resource = ResourceLink(
            url=url,
            title=link_titles[i].strip() if i < len(link_titles) else url,
            source_type=source_type,
            description=link_descriptions[i].strip() if i < len(link_descriptions) else "",
            workflow_stage=workflow_stage,
        )
        activity.resources.append(resource)

    if not activity.id:
        db.session.add(activity)

    db.session.commit()
    flash("Activity saved.", "success")

    # --- File uploads (optional) ---
    _save_uploaded_files(activity)

    return redirect(url_for("activities.detail", activity_id=activity.id))
