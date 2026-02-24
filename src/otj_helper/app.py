"""Flask application factory."""

import os
from pathlib import Path

from flask import Flask
from sqlalchemy import text

from otj_helper.models import KSB, db
from otj_helper.ksb_data import KSBS


def create_app(test_config=None):
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Default config
    db_path = os.environ.get(
        "OTJ_DB_PATH",
        str(Path(__file__).resolve().parent.parent.parent / "data" / "otj.db"),
    )
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-change-in-production")

    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    with app.app_context():
        db.create_all()
        _migrate_db()
        _seed_ksbs()

    # Register blueprints
    from otj_helper.routes.dashboard import bp as dashboard_bp
    from otj_helper.routes.activities import bp as activities_bp
    from otj_helper.routes.ksbs import bp as ksbs_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(activities_bp)
    app.register_blueprint(ksbs_bp)

    return app


def _migrate_db():
    """Apply incremental schema migrations for existing databases."""
    try:
        with db.engine.connect() as conn:
            conn.execute(
                text("ALTER TABLE resource_link ADD COLUMN workflow_stage VARCHAR(20) NOT NULL DEFAULT 'engage'")
            )
            conn.commit()
    except Exception:
        pass  # Column already exists


def _seed_ksbs():
    """Insert KSB reference data if not already present."""
    if KSB.query.count() == 0:
        for item in KSBS:
            db.session.add(KSB(**item))
        db.session.commit()
