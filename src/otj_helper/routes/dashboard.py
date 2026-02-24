"""Dashboard route - overview of OTJ hours and KSB coverage."""

from flask import Blueprint, render_template
from sqlalchemy import func

from otj_helper.models import Activity, KSB, activity_ksbs, db

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    # Total hours
    total_hours = db.session.query(func.sum(Activity.duration_hours)).scalar() or 0.0

    # Hours by activity type
    hours_by_type = (
        db.session.query(Activity.activity_type, func.sum(Activity.duration_hours))
        .group_by(Activity.activity_type)
        .all()
    )
    type_labels = dict(Activity.ACTIVITY_TYPES)
    hours_by_type = [(type_labels.get(t, t), h) for t, h in hours_by_type]

    # Recent activities
    recent = Activity.query.order_by(Activity.activity_date.desc()).limit(5).all()

    # KSB coverage: count of activities per KSB
    ksb_coverage = (
        db.session.query(
            KSB.code,
            KSB.category,
            KSB.title,
            func.count(activity_ksbs.c.activity_id).label("activity_count"),
            func.coalesce(
                db.session.query(func.sum(Activity.duration_hours))
                .join(activity_ksbs, Activity.id == activity_ksbs.c.activity_id)
                .filter(activity_ksbs.c.ksb_code == KSB.code)
                .correlate(KSB)
                .scalar_subquery(),
                0,
            ).label("total_hours"),
        )
        .outerjoin(activity_ksbs, KSB.code == activity_ksbs.c.ksb_code)
        .group_by(KSB.code, KSB.category, KSB.title)
        .order_by(KSB.code)
        .all()
    )

    # Activity count
    activity_count = Activity.query.count()

    return render_template(
        "dashboard.html",
        total_hours=total_hours,
        hours_by_type=hours_by_type,
        recent=recent,
        ksb_coverage=ksb_coverage,
        activity_count=activity_count,
    )
