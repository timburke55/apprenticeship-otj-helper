"""Landing page and spec-selection routes."""

from flask import Blueprint, g, redirect, render_template, request, url_for

from otj_helper.auth import login_required
from otj_helper.models import db
from otj_helper.specs_data import SPECS, SPECS_BY_CODE

bp = Blueprint("landing", __name__)


@bp.route("/")
def index():
    """Public landing page.  Logged-in users with a spec go straight to their dashboard."""
    if g.user and g.user.selected_spec:
        return redirect(url_for("dashboard.index"))
    return render_template("landing.html", specs=SPECS)


@bp.route("/select-spec")
@login_required
def select_spec():
    """Store the chosen spec on the user record then redirect to their dashboard.

    The spec code is passed as ?spec=ST0763.  Invalid codes bounce back to the
    landing page.
    """
    spec_code = request.args.get("spec", "").strip()
    if spec_code not in SPECS_BY_CODE:
        return redirect(url_for("landing.index"))

    g.user.selected_spec = spec_code
    db.session.commit()
    return redirect(url_for("dashboard.index"))
