"""Health-check endpoint for Railway and uptime monitors."""

from flask import Blueprint, jsonify
from sqlalchemy import text

from otj_helper.models import db

bp = Blueprint("health", __name__)


@bp.route("/healthz")
def healthz():
    """Return application health including DB connectivity.

    Returns HTTP 200 with ``{"status": "ok"}`` when the database is reachable,
    or HTTP 503 with ``{"status": "degraded"}`` when it is not.
    """
    try:
        db.session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "error"

    status = "ok" if db_status == "connected" else "degraded"
    code = 200 if status == "ok" else 503
    return jsonify({"status": status, "db": db_status, "version": "0.1.0"}), code
