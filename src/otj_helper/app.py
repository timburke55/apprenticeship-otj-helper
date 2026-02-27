"""Flask application factory."""

import logging
import os
from pathlib import Path

from flask import Flask, g, session
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from werkzeug.middleware.proxy_fix import ProxyFix

from otj_helper.ksb_data import KSBS
from otj_helper.models import KSB, db
from otj_helper.specs_data import SPECS_BY_CODE

logger = logging.getLogger(__name__)

csrf = CSRFProtect()


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
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        db_url = f"sqlite:///{db_path}"

    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-change-in-production")
    app.config["GOOGLE_CLIENT_ID"] = os.environ.get("GOOGLE_CLIENT_ID")
    app.config["GOOGLE_CLIENT_SECRET"] = os.environ.get("GOOGLE_CLIENT_SECRET")
    app.config["DEV_AUTO_LOGIN_EMAIL"] = os.environ.get("DEV_AUTO_LOGIN_EMAIL")
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB upload limit

    if test_config:
        app.config.update(test_config)

    # Trust Railway's HTTPS proxy so url_for(..., _external=True) produces https://
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    db.init_app(app)
    csrf.init_app(app)

    with app.app_context():
        try:
            db.create_all()
        except Exception as exc:
            if not _is_duplicate_ddl_error(exc):
                raise
            logger.debug("create_all: some tables already exist (concurrent worker startup), continuing: %s", exc)
        migration_results = _migrate_db()
        _seed_ksbs()

        # Startup diagnostics
        db_dialect = db.engine.dialect.name
        oauth_ok = bool(app.config.get("GOOGLE_CLIENT_ID") and app.config.get("GOOGLE_CLIENT_SECRET"))
        dev_login = bool(app.config.get("DEV_AUTO_LOGIN_EMAIL"))
        applied = sum(1 for ok in migration_results if ok)
        skipped = sum(1 for ok in migration_results if not ok)
        logger.info(
            "Startup: db=%s oauth=%s dev_login=%s migrations(applied=%d skipped=%d)",
            db_dialect, oauth_ok, dev_login, applied, skipped,
        )

    # Register blueprints
    from otj_helper.routes.auth import bp as auth_bp, init_oauth
    from otj_helper.routes.landing import bp as landing_bp
    from otj_helper.routes.dashboard import bp as dashboard_bp
    from otj_helper.routes.activities import bp as activities_bp
    from otj_helper.routes.ksbs import bp as ksbs_bp
    from otj_helper.routes.tags import bp as tags_bp
    from otj_helper.routes.health import bp as health_bp
    from otj_helper.routes.templates import bp as templates_bp
    from otj_helper.routes.uploads import bp as uploads_bp

    init_oauth(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(landing_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(activities_bp)
    app.register_blueprint(ksbs_bp)
    app.register_blueprint(tags_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(templates_bp)
    app.register_blueprint(uploads_bp)

    @app.before_request
    def load_user():
        from otj_helper.models import User
        user_id = session.get("user_id")

        dev_email = app.config.get("DEV_AUTO_LOGIN_EMAIL")
        if dev_email and user_id is None:
            user = User.query.filter_by(email=dev_email).first()
            if not user:
                user = User(email=dev_email, name="Dev User")
                db.session.add(user)
                db.session.commit()
            session["user_id"] = user.id
            user_id = user.id

        g.user = db.session.get(User, user_id) if user_id else None

    @app.before_request
    def maybe_generate_recurring():
        """Trigger recurring activity generation at most once per day per user session."""
        from datetime import date as _date
        if g.user is None:
            return
        today_str = _date.today().isoformat()
        if session.get("recurrence_checked") == today_str:
            return
        from otj_helper.tasks.recurrence import generate_recurring_activities
        generate_recurring_activities()
        session["recurrence_checked"] = today_str

    @app.context_processor
    def inject_user():
        user = g.get("user")
        spec = SPECS_BY_CODE.get(user.selected_spec) if user and user.selected_spec else None

        def natural_code(code: str) -> str:
            """Strip the single-character spec prefix from a DB KSB code.

            'AK1' → 'K1', 'AS28' → 'S28', 'K1' → 'K1' (unchanged).
            """
            if len(code) >= 3 and code[0].isalpha() and code[1].isalpha():
                return code[1:]
            return code

        return {"current_user": user, "current_spec": spec, "natural_code": natural_code}

    return app


def _is_duplicate_ddl_error(exc: Exception) -> bool:
    """Return True if *exc* indicates a DDL object (table/column) already exists.

    Covers both SQLite ('already exists') and PostgreSQL ('already exists',
    'duplicate column', 'duplicate table') error messages.
    """
    msg = str(exc).lower()
    return any(kw in msg for kw in ("already exists", "duplicate column", "duplicate table"))


def _migrate_db() -> list[bool]:
    """Apply incremental schema migrations for existing databases.

    Each statement is executed independently.  Errors caused by a column or
    table already existing are treated as expected and logged at DEBUG level.
    Unexpected errors are logged at WARNING level.

    Returns a list of booleans indicating whether each migration was applied
    (True) or skipped (False — already present).
    """
    # Build the attachment DDL using dialect-appropriate auto-increment syntax.
    # db.create_all() (called before this) always creates the table via ORM DDL,
    # so this migration is a safe no-op on fresh installs of either dialect.
    _pg = db.engine.dialect.name == "postgresql"
    _id_col = "id SERIAL PRIMARY KEY" if _pg else "id INTEGER PRIMARY KEY AUTOINCREMENT"
    migrations = [
        "ALTER TABLE resource_link ADD COLUMN workflow_stage VARCHAR(20) NOT NULL DEFAULT 'engage'",
        "ALTER TABLE activity ADD COLUMN user_id INTEGER REFERENCES app_user(id)",
        (
            "CREATE TABLE IF NOT EXISTS tag (id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " name VARCHAR(50) NOT NULL, user_id INTEGER NOT NULL REFERENCES app_user(id),"
            " UNIQUE(name, user_id))"
        ),
        (
            "CREATE TABLE IF NOT EXISTS activity_tags (activity_id INTEGER NOT NULL REFERENCES activity(id),"
            " tag_id INTEGER NOT NULL REFERENCES tag(id), PRIMARY KEY (activity_id, tag_id))"
        ),
        "ALTER TABLE ksb ADD COLUMN spec_code VARCHAR(20) NOT NULL DEFAULT 'ST0787'",
        "ALTER TABLE app_user ADD COLUMN selected_spec VARCHAR(20)",
        "ALTER TABLE app_user ADD COLUMN otj_target_hours REAL",
        "ALTER TABLE app_user ADD COLUMN seminar_target_hours REAL",
        "ALTER TABLE app_user ADD COLUMN weekly_target_hours REAL",
        "ALTER TABLE activity ADD COLUMN evidence_quality VARCHAR(20) NOT NULL DEFAULT 'draft'",
        (
            "CREATE TABLE IF NOT EXISTS activity_template ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "user_id INTEGER NOT NULL REFERENCES app_user(id), "
            "name VARCHAR(200) NOT NULL, "
            "title VARCHAR(200) NOT NULL, "
            "description TEXT DEFAULT '', "
            "activity_type VARCHAR(50) NOT NULL DEFAULT 'self_study', "
            "duration_hours REAL, "
            "evidence_quality VARCHAR(20) DEFAULT 'draft', "
            "tags_csv VARCHAR(500) DEFAULT '', "
            "ksb_codes_csv VARCHAR(500) DEFAULT '', "
            "is_recurring BOOLEAN DEFAULT 0, "
            "recurrence_day INTEGER, "
            "last_generated DATE, "
            "created_at DATETIME)"
        ),
        (
            f"CREATE TABLE IF NOT EXISTS attachment ("
            f"{_id_col}, "
            "activity_id INTEGER NOT NULL REFERENCES activity(id), "
            "filename VARCHAR(255) NOT NULL, "
            "stored_name VARCHAR(255) NOT NULL, "
            "content_type VARCHAR(100) NOT NULL, "
            "file_size INTEGER NOT NULL, "
            "has_thumbnail BOOLEAN DEFAULT 0, "
            "created_at DATETIME)"
        ),
    ]
    results: list[bool] = []
    for sql in migrations:
        try:
            with db.engine.connect() as conn:
                conn.execute(text(sql))
                conn.commit()
            logger.debug("Migration applied: %.80s", sql)
            results.append(True)
        except Exception as exc:
            if _is_duplicate_ddl_error(exc):
                logger.debug("Migration skipped (already applied): %.80s", sql)
            else:
                logger.warning("Migration failed unexpectedly — sql=%.80s error=%s", sql, exc)
            results.append(False)
    return results


def _is_unique_constraint_error(exc: Exception) -> bool:
    """Return True if *exc* is a unique-constraint violation.

    Detection strategy (most-to-least reliable):
    1. SQLAlchemy IntegrityError + SQLSTATE/PGCODE '23505' (PostgreSQL unique
       violation) via the underlying driver's ``orig`` attribute — resilient
       across psycopg2, psycopg3, and asyncpg.
    2. Message-based fallback covering SQLite ('unique constraint failed') and
       any driver that doesn't expose a structured error code.
    """
    if not isinstance(exc, IntegrityError):
        return False
    orig = getattr(exc, "orig", None)
    if orig is not None:
        code = getattr(orig, "pgcode", None) or getattr(orig, "sqlstate", None)
        if code is not None:
            return code == "23505"
    # Fallback: inspect the string representation for known phrases.
    msg = str(exc).lower()
    return any(kw in msg for kw in ("unique constraint failed", "unique violation", "duplicate key value"))


def _seed_ksbs():
    """Insert KSB reference data if not already present.

    Seeds are keyed by (spec_code, code) so that re-running on a database that
    already has ST0787 records will still insert the new ST0763 records.

    The commit is wrapped in a try/except so that a concurrent worker that
    already committed the same rows (raising a UNIQUE constraint error) is
    treated as a no-op rather than a fatal startup failure.
    """
    existing = {(k.spec_code, k.code) for k in KSB.query.all()}
    added = False
    for item in KSBS:
        key = (item["spec_code"], item["code"])
        if key not in existing:
            db.session.add(KSB(**item))
            added = True
    if added:
        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            if _is_unique_constraint_error(exc):
                logger.debug(
                    "KSB seed skipped (concurrent worker already seeded): %s", exc
                )
            else:
                raise
