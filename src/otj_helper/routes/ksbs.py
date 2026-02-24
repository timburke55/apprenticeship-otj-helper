"""KSB reference and detail routes."""

from flask import Blueprint, abort, g, render_template
from sqlalchemy import func

from otj_helper.auth import login_required
from otj_helper.models import Activity, KSB, activity_ksbs, db

bp = Blueprint("ksbs", __name__, url_prefix="/ksbs")


@bp.route("/")
@login_required
def list_ksbs():
    uid = g.user.id
    spec = g.user.selected_spec or "ST0787"

    ksbs = (
        db.session.query(
            KSB,
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
        .group_by(KSB.code)
        .order_by(KSB.code)
        .all()
    )

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
@login_required
def detail(code):
    spec = g.user.selected_spec or "ST0787"
    ksb = KSB.query.filter_by(code=code, spec_code=spec).first_or_404()
    activities = (
        Activity.query.filter(Activity.ksbs.any(KSB.code == code))
        .filter(Activity.user_id == g.user.id)
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
