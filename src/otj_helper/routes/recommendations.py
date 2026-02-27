"""Recommendations route -- portfolio readiness and gap analysis."""

from flask import Blueprint, g, redirect, render_template, url_for

from otj_helper.auth import login_required
from otj_helper.models import Activity, ResourceLink

bp = Blueprint("recommendations", __name__, url_prefix="/recommendations")


@bp.route("/")
@login_required
def index():
    """Show the recommendations dashboard."""
    if not g.user.selected_spec:
        return redirect(url_for("landing.index"))

    from otj_helper.recommendations import analyse_gaps

    spec = g.user.selected_spec or "ST0787"
    analysis = analyse_gaps(g.user.id, spec)
    return render_template(
        "recommendations/index.html",
        **analysis,
        activity_types=Activity.ACTIVITY_TYPES,
        workflow_stages=ResourceLink.WORKFLOW_STAGES,
    )
