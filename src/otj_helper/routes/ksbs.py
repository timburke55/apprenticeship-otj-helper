"""KSB reference and detail routes."""

from flask import Blueprint, render_template
from sqlalchemy import func

from otj_helper.models import Activity, KSB, activity_ksbs, db

bp = Blueprint("ksbs", __name__, url_prefix="/ksbs")


@bp.route("/")
def list_ksbs():
    ksbs = (
        db.session.query(
            KSB,
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
        .group_by(KSB.code)
        .order_by(KSB.code)
        .all()
    )

    # Group by category
    knowledge = [(k, c, h) for k, c, h in ksbs if k.category == "knowledge"]
    skills = [(k, c, h) for k, c, h in ksbs if k.category == "skill"]
    behaviours = [(k, c, h) for k, c, h in ksbs if k.category == "behaviour"]

    return render_template(
        "ksbs/list.html",
        knowledge=knowledge,
        skills=skills,
        behaviours=behaviours,
    )


@bp.route("/<code>")
def detail(code):
    ksb = KSB.query.get_or_404(code)
    activities = (
        Activity.query.filter(Activity.ksbs.any(KSB.code == code))
        .order_by(Activity.activity_date.desc())
        .all()
    )
    total_hours = sum(a.duration_hours for a in activities)
    return render_template(
        "ksbs/detail.html",
        ksb=ksb,
        activities=activities,
        total_hours=total_hours,
    )
