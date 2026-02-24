"""Activity CRUD routes."""

from datetime import date

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from otj_helper.auth import login_required
from otj_helper.models import Activity, KSB, ResourceLink, Tag, db

# Which source types are surfaced per CORE stage (first entry is the default)
_STAGE_SOURCE_TYPES = {
    "capture": ["google_keep", "website", "other"],
    "organise": ["google_tasks", "website", "other"],
    "review": ["google_docs", "diagram", "markdown", "google_drive", "other"],
    "engage": ["google_docs", "google_drive", "github", "diagram", "markdown", "website", "other"],
}

bp = Blueprint("activities", __name__, url_prefix="/activities")


@bp.route("/")
@login_required
def list_activities():
    page = request.args.get("page", 1, type=int)
    ksb_filter = request.args.get("ksb", None)
    type_filter = request.args.get("type", None)
    tag_filter = request.args.get("tag", None)

    query = Activity.query.filter_by(user_id=g.user.id)

    if ksb_filter:
        query = query.filter(Activity.ksbs.any(KSB.code == ksb_filter))
    if type_filter:
        query = query.filter(Activity.activity_type == type_filter)
    if tag_filter:
        query = query.filter(Activity.tags.any(Tag.id == tag_filter))

    activities = query.order_by(Activity.activity_date.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    all_ksbs = KSB.query.order_by(KSB.code).all()
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


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        return _save_activity(Activity())

    all_ksbs = KSB.query.order_by(KSB.code).all()
    user_tags = Tag.query.filter_by(user_id=g.user.id).order_by(Tag.name).all()
    return render_template(
        "activities/form.html",
        activity=None,
        all_ksbs=all_ksbs,
        activity_types=Activity.ACTIVITY_TYPES,
        source_types=ResourceLink.SOURCE_TYPES,
        workflow_stages=ResourceLink.WORKFLOW_STAGES,
        stage_source_types=_STAGE_SOURCE_TYPES,
        user_tags=user_tags,
    )


@bp.route("/<int:activity_id>")
@login_required
def detail(activity_id):
    activity = Activity.query.filter_by(id=activity_id, user_id=g.user.id).first_or_404()
    return render_template("activities/detail.html", activity=activity)


@bp.route("/<int:activity_id>/edit", methods=["GET", "POST"])
@login_required
def edit(activity_id):
    activity = Activity.query.filter_by(id=activity_id, user_id=g.user.id).first_or_404()

    if request.method == "POST":
        return _save_activity(activity)

    all_ksbs = KSB.query.order_by(KSB.code).all()
    user_tags = Tag.query.filter_by(user_id=g.user.id).order_by(Tag.name).all()
    return render_template(
        "activities/form.html",
        activity=activity,
        all_ksbs=all_ksbs,
        activity_types=Activity.ACTIVITY_TYPES,
        source_types=ResourceLink.SOURCE_TYPES,
        workflow_stages=ResourceLink.WORKFLOW_STAGES,
        stage_source_types=_STAGE_SOURCE_TYPES,
        user_tags=user_tags,
    )


@bp.route("/<int:activity_id>/delete", methods=["POST"])
@login_required
def delete(activity_id):
    activity = Activity.query.filter_by(id=activity_id, user_id=g.user.id).first_or_404()
    db.session.delete(activity)
    db.session.commit()
    flash("Activity deleted.", "info")
    return redirect(url_for("activities.list_activities"))


def _save_activity(activity):
    """Save or update an activity from form data."""
    activity.title = request.form["title"]
    activity.description = request.form.get("description", "")
    activity.activity_date = date.fromisoformat(request.form["activity_date"])
    activity.duration_hours = float(request.form["duration_hours"])
    activity.activity_type = request.form["activity_type"]
    activity.notes = request.form.get("notes", "")

    # Assign owner on new activities
    if not activity.id:
        activity.user_id = g.user.id

    # Update KSBs
    selected_ksbs = request.form.getlist("ksbs")
    activity.ksbs = KSB.query.filter(KSB.code.in_(selected_ksbs)).all()

    # Update tags — parse comma-separated input, create new tags as needed
    raw_tags = request.form.get("tags", "")
    tag_names = [t.strip().lower() for t in raw_tags.split(",") if t.strip()]
    resolved_tags = []
    for name in tag_names:
        tag = Tag.query.filter_by(name=name, user_id=g.user.id).first()
        if not tag:
            tag = Tag(name=name, user_id=g.user.id)
            db.session.add(tag)
        resolved_tags.append(tag)
    activity.tags = resolved_tags

    # Handle resource links — remove existing if editing
    if activity.id:
        ResourceLink.query.filter_by(activity_id=activity.id).delete()

    link_titles = request.form.getlist("link_title")
    link_urls = request.form.getlist("link_url")
    link_types = request.form.getlist("link_source_type")
    link_descriptions = request.form.getlist("link_description")
    link_stages = request.form.getlist("link_stage")

    for i in range(len(link_urls)):
        url = link_urls[i].strip()
        if not url:
            continue
        resource = ResourceLink(
            url=url,
            title=link_titles[i].strip() if i < len(link_titles) else url,
            source_type=link_types[i] if i < len(link_types) else "other",
            description=link_descriptions[i].strip() if i < len(link_descriptions) else "",
            workflow_stage=link_stages[i] if i < len(link_stages) else "engage",
        )
        activity.resources.append(resource)

    if not activity.id:
        db.session.add(activity)

    db.session.commit()
    flash("Activity saved.", "success")
    return redirect(url_for("activities.detail", activity_id=activity.id))
