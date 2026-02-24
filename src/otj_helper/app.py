"""Flask application factory."""

import os
from pathlib import Path

from flask import Flask, g, session
from sqlalchemy import text
from werkzeug.middleware.proxy_fix import ProxyFix

from otj_helper.models import KSB, db
from otj_helper.ksb_data import KSBS


def create_app(test_config=None):
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Database: prefer DATABASE_URL (Railway PostgreSQL), fall back to SQLite
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        # Railway historically issued postgres:// which SQLAlchemy rejects
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
    else:
        db_path = os.environ.get(
            "OTJ_DB_PATH",
            str(Path(__file__).resolve().parent.parent.parent / "data" / "otj.db"),
        )
        db_url = f"sqlite:///{db_path}"

    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-change-in-production")
    app.config["GOOGLE_CLIENT_ID"] = os.environ.get("GOOGLE_CLIENT_ID")
    app.config["GOOGLE_CLIENT_SECRET"] = os.environ.get("GOOGLE_CLIENT_SECRET")

    if test_config:
        app.config.update(test_config)

    # Trust Railway's HTTPS proxy so url_for(..., _external=True) produces https://
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    db.init_app(app)

    with app.app_context():
        db.create_all()
        _migrate_db()
        _seed_ksbs()

    # Register blueprints
    from otj_helper.routes.auth import bp as auth_bp, init_oauth
    from otj_helper.routes.dashboard import bp as dashboard_bp
    from otj_helper.routes.activities import bp as activities_bp
    from otj_helper.routes.ksbs import bp as ksbs_bp

    init_oauth(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(activities_bp)
    app.register_blueprint(ksbs_bp)

    @app.before_request
    def load_user():
        from otj_helper.models import User
        user_id = session.get("user_id")
        g.user = db.session.get(User, user_id) if user_id else None

    @app.context_processor
    def inject_user():
        return {"current_user": g.get("user")}

    return app


def _migrate_db():
    """Apply incremental schema migrations for existing databases."""
    migrations = [
        "ALTER TABLE resource_link ADD COLUMN workflow_stage VARCHAR(20) NOT NULL DEFAULT 'engage'",
        "ALTER TABLE activity ADD COLUMN user_id INTEGER REFERENCES app_user(id)",
    ]
    for sql in migrations:
        try:
            with db.engine.connect() as conn:
                conn.execute(text(sql))
                conn.commit()
        except Exception:
            pass  # Column/constraint already exists


def _seed_ksbs():
    """Insert KSB reference data if not already present."""
    if KSB.query.count() == 0:
        for item in KSBS:
            db.session.add(KSB(**item))
        db.session.commit()
