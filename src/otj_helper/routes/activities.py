"""Activity CRUD routes."""

from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from otj_helper.models import Activity, KSB, ResourceLink, db

# Which source types are surfaced per CORE stage (first entry is the default)
_STAGE_SOURCE_TYPES = {
    "capture": ["google_keep", "website", "other"],
    "organise": ["google_tasks", "website", "other"],
    "review": ["google_docs", "diagram", "markdown", "google_drive", "other"],
    "engage": ["google_docs", "google_drive", "github", "diagram", "markdown", "website", "other"],
}

bp = Blueprint("activities", __name__, url_prefix="/activities")


@bp.route("/")
def list_activities():
    page = request.args.get("page", 1, type=int)
    ksb_filter = request.args.get("ksb", None)
    type_filter = request.args.get("type", None)

    query = Activity.query

    if ksb_filter:
        query = query.filter(Activity.ksbs.any(KSB.code == ksb_filter))
    if type_filter:
        query = query.filter(Activity.activity_type == type_filter)

    activities = query.order_by(Activity.activity_date.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    all_ksbs = KSB.query.order_by(KSB.code).all()
    return render_template(
        "activities/list.html",
        activities=activities,
        all_ksbs=all_ksbs,
        activity_types=Activity.ACTIVITY_TYPES,
        ksb_filter=ksb_filter,
        type_filter=type_filter,
    )


@bp.route("/new", methods=["GET", "POST"])
def create():
    if request.method == "POST":
        return _save_activity(Activity())

    all_ksbs = KSB.query.order_by(KSB.code).all()
    return render_template(
        "activities/form.html",
        activity=None,
        all_ksbs=all_ksbs,
        activity_types=Activity.ACTIVITY_TYPES,
        source_types=ResourceLink.SOURCE_TYPES,
        workflow_stages=ResourceLink.WORKFLOW_STAGES,
        stage_source_types=_STAGE_SOURCE_TYPES,
    )


@bp.route("/<int:activity_id>")
def detail(activity_id):
    activity = Activity.query.get_or_404(activity_id)
    return render_template("activities/detail.html", activity=activity)


@bp.route("/<int:activity_id>/edit", methods=["GET", "POST"])
def edit(activity_id):
    activity = Activity.query.get_or_404(activity_id)

    if request.method == "POST":
        return _save_activity(activity)

    all_ksbs = KSB.query.order_by(KSB.code).all()
    return render_template(
        "activities/form.html",
        activity=activity,
        all_ksbs=all_ksbs,
        activity_types=Activity.ACTIVITY_TYPES,
        source_types=ResourceLink.SOURCE_TYPES,
        workflow_stages=ResourceLink.WORKFLOW_STAGES,
        stage_source_types=_STAGE_SOURCE_TYPES,
    )


@bp.route("/<int:activity_id>/delete", methods=["POST"])
def delete(activity_id):
    activity = Activity.query.get_or_404(activity_id)
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

    # Update KSBs
    selected_ksbs = request.form.getlist("ksbs")
    activity.ksbs = KSB.query.filter(KSB.code.in_(selected_ksbs)).all()

    # Handle resource links
    # Remove existing links if editing
    if activity.id:
        ResourceLink.query.filter_by(activity_id=activity.id).delete()

    # Add new resource links from form
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
