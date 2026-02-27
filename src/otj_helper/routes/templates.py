"""Activity template CRUD routes."""

import math

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from otj_helper.auth import login_required
from otj_helper.models import Activity, ActivityTemplate, KSB, db

_VALID_ACTIVITY_TYPES = {t for t, _ in Activity.ACTIVITY_TYPES}
_VALID_EVIDENCE_QUALITIES = {v for v, _ in Activity.EVIDENCE_QUALITY_OPTIONS}

bp = Blueprint("templates", __name__, url_prefix="/templates")


def _form_context(template=None):
    """Return context dict for the template create/edit form."""
    spec = g.user.selected_spec or "ST0787"
    selected_ksb_codes = set()
    if template and template.ksb_codes_csv:
        selected_ksb_codes = {c.strip() for c in template.ksb_codes_csv.split(",") if c.strip()}
    return dict(
        template=template,
        selected_ksb_codes=selected_ksb_codes,
        all_ksbs=KSB.query.filter_by(spec_code=spec).order_by(KSB.code).all(),
        activity_types=Activity.ACTIVITY_TYPES,
        evidence_quality_options=Activity.EVIDENCE_QUALITY_OPTIONS,
        recurrence_days=ActivityTemplate.RECURRENCE_DAYS,
    )


@bp.route("/")
@login_required
def list_templates():
    """List all templates for the current user."""
    templates = (
        ActivityTemplate.query.filter_by(user_id=g.user.id)
        .order_by(ActivityTemplate.name)
        .all()
    )
    activity_type_labels = dict(Activity.ACTIVITY_TYPES)
    recurrence_day_labels = dict(ActivityTemplate.RECURRENCE_DAYS)
    return render_template(
        "templates/list.html",
        templates=templates,
        activity_type_labels=activity_type_labels,
        recurrence_day_labels=recurrence_day_labels,
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    """Show the new-template form (GET) or save a new template (POST)."""
    if request.method == "POST":
        return _save_template(ActivityTemplate(user_id=g.user.id))
    return render_template("templates/form.html", **_form_context())


@bp.route("/<int:template_id>/edit", methods=["GET", "POST"])
@login_required
def edit(template_id):
    """Show the edit form for a template (GET) or save changes (POST)."""
    tmpl = ActivityTemplate.query.filter_by(
        id=template_id, user_id=g.user.id
    ).first_or_404()
    if request.method == "POST":
        return _save_template(tmpl)
    return render_template("templates/form.html", **_form_context(tmpl))


@bp.route("/<int:template_id>/delete", methods=["POST"])
@login_required
def delete(template_id):
    """Delete a template and redirect to the template list."""
    tmpl = ActivityTemplate.query.filter_by(
        id=template_id, user_id=g.user.id
    ).first_or_404()
    db.session.delete(tmpl)
    db.session.commit()
    flash("Template deleted.", "info")
    return redirect(url_for("templates.list_templates"))


@bp.route("/<int:template_id>/use")
@login_required
def use_template(template_id):
    """Redirect to the activity form pre-filled from a template."""
    tmpl = ActivityTemplate.query.filter_by(
        id=template_id, user_id=g.user.id
    ).first_or_404()
    return redirect(url_for(
        "activities.create",
        tmpl_title=tmpl.title,
        tmpl_type=tmpl.activity_type,
        tmpl_duration=tmpl.duration_hours if tmpl.duration_hours is not None else "",
        tmpl_description=tmpl.description or "",
        tmpl_tags=tmpl.tags_csv or "",
        tmpl_ksbs=tmpl.ksb_codes_csv or "",
        tmpl_quality=tmpl.evidence_quality or "draft",
    ))


@bp.route("/from-activity/<int:activity_id>")
@login_required
def create_from_activity(activity_id):
    """Pre-fill the template form from an existing activity."""
    activity = Activity.query.filter_by(
        id=activity_id, user_id=g.user.id
    ).first_or_404()
    tmpl = ActivityTemplate(
        user_id=g.user.id,
        name="",
        title=activity.title,
        description=activity.description or "",
        activity_type=activity.activity_type,
        duration_hours=activity.duration_hours,
        evidence_quality=activity.evidence_quality or "draft",
        tags_csv=",".join(t.name for t in activity.tags),
        ksb_codes_csv=",".join(k.code for k in activity.ksbs),
    )
    return render_template("templates/form.html", **_form_context(tmpl))


def _save_template(tmpl):
    """Validate form data then save or update *tmpl*.

    Returns a redirect on success.  On validation failure, flashes error
    messages and re-renders the form with HTTP 422.
    """
    errors = []

    name = request.form.get("name", "").strip()
    if not name:
        errors.append("Template name is required.")

    title = request.form.get("title", "").strip()
    if not title:
        errors.append("Pre-fill title is required.")

    activity_type = request.form.get("activity_type", "")
    if activity_type not in _VALID_ACTIVITY_TYPES:
        errors.append(f"Activity type '{activity_type}' is not recognised.")

    duration_str = request.form.get("duration_hours", "").strip()
    duration_hours = None
    if duration_str:
        try:
            duration_hours = float(duration_str)
            if not math.isfinite(duration_hours) or duration_hours <= 0:
                raise ValueError("Duration must be a positive finite number.")
        except ValueError:
            errors.append("Duration must be a positive number (e.g. 2.5).")
            duration_hours = None

    evidence_quality = request.form.get("evidence_quality", "draft")
    if evidence_quality not in _VALID_EVIDENCE_QUALITIES:
        evidence_quality = "draft"

    is_recurring = request.form.get("is_recurring") == "on"
    recurrence_day = None
    if is_recurring:
        recurrence_day_str = request.form.get("recurrence_day", "")
        try:
            recurrence_day = int(recurrence_day_str)
            if recurrence_day < 0 or recurrence_day > 6:
                raise ValueError("Day must be 0–6.")
        except (ValueError, TypeError):
            errors.append("A valid day of the week is required for recurring templates.")

    # Populate fields for re-render on error
    tmpl.name = name
    tmpl.title = title
    tmpl.activity_type = activity_type
    tmpl.duration_hours = duration_hours
    tmpl.evidence_quality = evidence_quality
    tmpl.description = request.form.get("description", "")
    tmpl.tags_csv = ",".join(
        t.strip().lower()
        for t in request.form.get("tags_csv", "").split(",")
        if t.strip()
    )
    tmpl.ksb_codes_csv = ",".join(request.form.getlist("ksb_codes"))
    tmpl.is_recurring = is_recurring
    tmpl.recurrence_day = recurrence_day

    if errors:
        for msg in errors:
            flash(msg, "error")
        return render_template("templates/form.html", **_form_context(tmpl)), 422

    if not tmpl.id:
        db.session.add(tmpl)
    db.session.commit()
    flash("Template saved.", "success")
    return redirect(url_for("templates.list_templates"))
