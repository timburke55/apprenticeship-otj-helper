"""Dashboard route - overview of OTJ hours and KSB coverage."""

from flask import Blueprint, g, render_template
from sqlalchemy import func

from otj_helper.auth import login_required
from otj_helper.models import Activity, KSB, Tag, activity_ksbs, activity_tags, db

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@login_required
def index():
    uid = g.user.id

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

    # KSB coverage: count and hours per KSB for this user only.
    # Outer-join via Activity so KSBs with zero of this user's activities still appear.
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
    )
