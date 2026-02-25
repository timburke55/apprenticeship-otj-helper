"""Dashboard route - overview of OTJ hours and KSB coverage."""

import json
from collections import defaultdict
from datetime import date, timedelta

from flask import Blueprint, g, redirect, render_template, request, url_for
from sqlalchemy import func

from otj_helper.auth import login_required
from otj_helper.models import Activity, KSB, Tag, activity_ksbs, activity_tags, db

bp = Blueprint("dashboard", __name__)


def _weekly_hours(uid: int, weeks: int = 12) -> tuple[list[str], list[float]]:
    """Return (labels, values) for the last *weeks* ISO calendar weeks.

    Queries all activities for *uid*, groups them by ISO year+week, then
    builds an ordered list of the most-recent *weeks* weeks.  Weeks with
    no logged activities are filled with ``0.0``.

    Args:
        uid: Primary key of the user whose activities are queried.
        weeks: Number of most-recent weeks to include (default 12).

    Returns:
        A 2-tuple of equal-length lists: human-readable week-start labels
        (e.g. ``"3 Feb"``) and the corresponding total hours as floats.
    """
    activities = (
        db.session.query(Activity.activity_date, Activity.duration_hours)
        .filter(Activity.user_id == uid)
        .all()
    )

    # Group by (ISO year, ISO week)
    totals: dict[tuple[int, int], float] = defaultdict(float)
    for act_date, hours in activities:
        iso = act_date.isocalendar()
        totals[(iso[0], iso[1])] += hours

    # Build ordered list of the last `weeks` ISO weeks
    today = date.today()
    labels: list[str] = []
    values: list[float] = []
    for i in range(weeks - 1, -1, -1):
        day = today - timedelta(weeks=i)
        monday = day - timedelta(days=day.weekday())
        iso = monday.isocalendar()
        key = (iso[0], iso[1])
        labels.append(monday.strftime("%-d %b"))
        values.append(round(totals.get(key, 0.0), 2))

    return labels, values


@bp.route("/dashboard", methods=["GET", "POST"])
@login_required
def index():
    """Render the main dashboard with charts and aggregate stats.

    GET  – displays total hours, weekly bar chart, seminar doughnut, KSB
           progress charts, coverage map, tag cloud, and recent activities.
    POST – updates the user's ``otj_target_hours`` and
           ``seminar_target_hours`` settings, then redirects back to GET.
           Submitted values are validated to be non-negative floats; invalid
           or empty values leave the corresponding field unchanged/cleared.
    """
    # Redirect to landing if the user hasn't chosen a spec yet
    if not g.user.selected_spec:
        return redirect(url_for("landing.index"))

    uid = g.user.id
    spec = g.user.selected_spec

    # Handle settings update
    if request.method == "POST":
        try:
            otj_val = request.form.get("otj_target_hours", "").strip()
            sem_val = request.form.get("seminar_target_hours", "").strip()
            otj_parsed = float(otj_val) if otj_val else None
            sem_parsed = float(sem_val) if sem_val else None
            if (otj_parsed is not None and otj_parsed < 0) or (
                sem_parsed is not None and sem_parsed < 0
            ):
                raise ValueError("Targets must be non-negative")
            g.user.otj_target_hours = otj_parsed
            g.user.seminar_target_hours = sem_parsed
            db.session.commit()
        except ValueError:
            pass
        return redirect(url_for("dashboard.index"))

    # Total hours
    total_hours = (
        db.session.query(func.sum(Activity.duration_hours))
        .filter(Activity.user_id == uid)
        .scalar() or 0.0
    )

    # Hours by activity type
    hours_by_type = (
        db.session.query(Activity.activity_type, func.sum(Activity.duration_hours))
        .filter(Activity.user_id == uid)
        .group_by(Activity.activity_type)
        .all()
    )
    type_labels = dict(Activity.ACTIVITY_TYPES)
    hours_by_type = [(type_labels.get(t, t), h) for t, h in hours_by_type]

    # Seminar/training hours: training_course + workshop activity types
    seminar_hours = (
        db.session.query(func.sum(Activity.duration_hours))
        .filter(
            Activity.user_id == uid,
            Activity.activity_type.in_(["training_course", "workshop"]),
        )
        .scalar() or 0.0
    )

    # Weekly hours for the last 12 weeks (for the bar chart)
    week_labels, week_values = _weekly_hours(uid, weeks=12)
    weekly_chart_data = json.dumps({"labels": week_labels, "values": week_values})

    # Recent activities
    recent = (
        Activity.query.filter_by(user_id=uid)
        .order_by(Activity.activity_date.desc())
        .limit(5)
        .all()
    )

    # KSB coverage for the user's selected spec only
    ksb_coverage = (
        db.session.query(
            KSB.code,
            KSB.category,
            KSB.title,
            func.count(Activity.id).label("activity_count"),
            func.coalesce(
                db.session.query(func.sum(Activity.duration_hours))
                .join(activity_ksbs, Activity.id == activity_ksbs.c.activity_id)
                .filter(activity_ksbs.c.ksb_code == KSB.code)
                .filter(Activity.user_id == uid)
                .correlate(KSB)
                .scalar_subquery(),
                0,
            ).label("total_hours"),
        )
        .filter(KSB.spec_code == spec)
        .outerjoin(activity_ksbs, KSB.code == activity_ksbs.c.ksb_code)
        .outerjoin(
            Activity,
            (Activity.id == activity_ksbs.c.activity_id) & (Activity.user_id == uid),
        )
        .group_by(KSB.code, KSB.category, KSB.title)
        .order_by(KSB.code)
        .all()
    )

    activity_count = Activity.query.filter_by(user_id=uid).count()

    # Top tags by activity count for this user
    top_tags = (
        db.session.query(Tag, func.count(activity_tags.c.activity_id).label("count"))
        .join(activity_tags, Tag.id == activity_tags.c.tag_id)
        .join(Activity, Activity.id == activity_tags.c.activity_id)
        .filter(Activity.user_id == uid)
        .group_by(Tag.id)
        .order_by(func.count(activity_tags.c.activity_id).desc())
        .limit(15)
        .all()
    )

    return render_template(
        "dashboard.html",
        total_hours=total_hours,
        hours_by_type=hours_by_type,
        recent=recent,
        ksb_coverage=ksb_coverage,
        activity_count=activity_count,
        top_tags=top_tags,
        seminar_hours=seminar_hours,
        weekly_chart_data=weekly_chart_data,
        otj_target_hours=g.user.otj_target_hours,
        seminar_target_hours=g.user.seminar_target_hours,
    )
