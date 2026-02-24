"""Dashboard route - overview of OTJ hours and KSB coverage."""

from flask import Blueprint, g, redirect, render_template, url_for
from sqlalchemy import func

from otj_helper.auth import login_required
from otj_helper.models import Activity, KSB, activity_ksbs, db

bp = Blueprint("dashboard", __name__)


@bp.route("/dashboard")
@login_required
def index():
    # Redirect to landing if the user hasn't chosen a spec yet
    if not g.user.selected_spec:
        return redirect(url_for("landing.index"))

    uid = g.user.id
    spec = g.user.selected_spec

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

    return render_template(
        "dashboard.html",
        total_hours=total_hours,
        hours_by_type=hours_by_type,
        recent=recent,
        ksb_coverage=ksb_coverage,
        activity_count=activity_count,
    )
