"""Flask application factory."""

import logging
import os
import time
import urllib.parse
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


def _normalize_db_url_password(db_url: str) -> str:
    """Re-encode the password component of a database URL.

    Railway (and some other platforms) may generate passwords that contain
    special characters such as ``@``, ``#``, ``?``, or ``%``.  If those
    characters are not percent-encoded in the ``DATABASE_URL``, SQLAlchemy
    and psycopg2 can parse the URL incorrectly and send the wrong password
    to PostgreSQL, producing a ``password authentication failed`` error at
    startup.

    This function uses manual URL splitting (``rpartition``/``partition``)
    instead of ``urllib.parse.urlparse`` so that characters like ``#`` and
    ``?`` inside the password are not misinterpreted as URL fragment or
    query delimiters.  The password is unquoted then re-quoted so the
    round-trip is idempotent regardless of whether the source URL was
    already percent-encoded.
    """
    try:
        scheme_sep = db_url.find("://")
        if scheme_sep < 0:
            return db_url

        scheme = db_url[:scheme_sep]
        rest = db_url[scheme_sep + 3:]  # everything after ://

        # Split userinfo from hostinfo at the LAST '@' so that '@'
        # characters inside the password are preserved.
        userinfo, at_sign, hostinfo = rest.rpartition("@")
        if not at_sign:
            return db_url  # no credentials in the URL

        # Split username from password at the FIRST ':'
        username, colon, password = userinfo.partition(":")
        if not colon:
            return db_url  # username only, no password

        # unquote first so that an already-encoded password (e.g. %40 for @)
        # is not double-encoded to %2540; the round-trip is idempotent.
        safe_pw = urllib.parse.quote(urllib.parse.unquote(password), safe="")
        safe_user = urllib.parse.quote(urllib.parse.unquote(username), safe="")

        normalized = f"{scheme}://{safe_user}:{safe_pw}@{hostinfo}"
        if normalized != db_url:
            logger.info(
                "DATABASE_URL password re-encoded (special characters were percent-escaped)"
            )
        return normalized
    except Exception:
        # If anything goes wrong during re-encoding, return the original URL
        # unchanged so the caller can attempt the connection and surface a
        # more specific error.
        return db_url


_INSECURE_DEFAULT_KEY = "dev-key-change-in-production"

_REQUIRED_RAILWAY_VARS_DOC = (
    "Required Railway service variables:\n"
    "  DATABASE_URL  — linked from the Railway PostgreSQL addon (not manually typed)\n"
    "  SECRET_KEY    — random hex string: "
    "python -c \"import secrets; print(secrets.token_hex(32))\"\n"
    "  GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET — Google OAuth credentials\n"
    "  (or DEV_AUTO_LOGIN_EMAIL for development-only auto-login instead of OAuth)"
)


def _validate_railway_env(db_url: str) -> None:
    """Validate required environment variables before the app starts on Railway.

    Railway automatically sets ``RAILWAY_ENVIRONMENT``.  When present this
    function checks that every variable required for a working production
    deployment is set to a valid value, and raises ``RuntimeError`` with a
    clear, actionable message listing every problem at once rather than
    failing one-at-a-time at the first bad value encountered.

    Variables checked:

    * ``DATABASE_URL`` — must contain a host, password, and database name.
      A missing password is the most common cause of ``password authentication
      failed`` errors; it usually means the PostgreSQL addon reference was not
      linked to the service.
    * ``SECRET_KEY`` — must not be the insecure development default.  Flask
      uses this to sign session cookies; leaving it at the default means
      sessions are predictable and every redeploy logs all users out.
    * Authentication — either ``GOOGLE_CLIENT_ID``/``GOOGLE_CLIENT_SECRET``
      (for OAuth) or ``DEV_AUTO_LOGIN_EMAIL`` (development bypass) must be
      set, otherwise no one can log in.
    """
    if not os.environ.get("RAILWAY_ENVIRONMENT"):
        return

    errors: list[str] = []

    # --- DATABASE_URL component check ---
    # Use manual splitting (matching _normalize_db_url_password) so that
    # special characters like '#' inside the password don't fool urlparse
    # into reporting a missing host or password.
    if db_url.startswith("postgresql"):
        try:
            scheme_sep = db_url.find("://")
            rest = db_url[scheme_sep + 3:] if scheme_sep >= 0 else ""
            userinfo, at_sign, hostinfo = rest.rpartition("@")
            missing_parts = []
            if not at_sign or not hostinfo or hostinfo.startswith("/"):
                missing_parts.append("host")
            _user, colon, _pw = userinfo.partition(":") if at_sign else ("", "", "")
            if not colon or not _pw:
                missing_parts.append("password")
            # database name is after the first '/' in hostinfo
            db_name = hostinfo.partition("/")[2].partition("?")[0] if hostinfo else ""
            if not db_name:
                missing_parts.append("database name")
            if missing_parts:
                errors.append(
                    f"DATABASE_URL is incomplete — missing: {', '.join(missing_parts)}. "
                    "Ensure the Railway PostgreSQL addon is added and its DATABASE_URL "
                    "reference variable is linked to this service (not manually typed)."
                )
        except Exception:
            logger.debug("Unparseable DATABASE_URL", exc_info=True)

    # --- SECRET_KEY check ---
    if os.environ.get("SECRET_KEY", _INSECURE_DEFAULT_KEY) == _INSECURE_DEFAULT_KEY:
        errors.append(
            "SECRET_KEY is not set (or uses the insecure development default). "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\" "
            "and add it as a Railway service variable."
        )

    # --- Authentication method check ---
    has_oauth = bool(
        os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET")
    )
    has_dev_login = bool(os.environ.get("DEV_AUTO_LOGIN_EMAIL"))
    if not has_oauth and not has_dev_login:
        errors.append(
            "No login method is configured. "
            "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET for Google OAuth, "
            "or set DEV_AUTO_LOGIN_EMAIL for development auto-login."
        )

    if errors:
        bullet_list = "\n  • ".join(errors)
        raise RuntimeError(
            f"Railway startup validation failed — fix the following issues before redeploying:\n"
            f"  • {bullet_list}\n\n"
            f"{_REQUIRED_RAILWAY_VARS_DOC}"
        )



def create_app(test_config=None):
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Database: prefer DATABASE_URL (Railway PostgreSQL), fall back to SQLite
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        # Railway historically issued postgres:// which SQLAlchemy rejects
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        db_url = _normalize_db_url_password(db_url)
    else:
        db_path = os.environ.get(
            "OTJ_DB_PATH",
            str(Path(__file__).resolve().parent.parent.parent / "data" / "otj.db"),
        )
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        db_url = f"sqlite:///{db_path}"

    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    # Validate connections before handing them out from the pool.  This
    # prevents stale-connection errors when PostgreSQL restarts or when a
    # gunicorn worker inherits a connection forked from the master process.
    if db_url.startswith("postgresql"):
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", _INSECURE_DEFAULT_KEY)
    app.config["GOOGLE_CLIENT_ID"] = os.environ.get("GOOGLE_CLIENT_ID")
    app.config["GOOGLE_CLIENT_SECRET"] = os.environ.get("GOOGLE_CLIENT_SECRET")
    app.config["DEV_AUTO_LOGIN_EMAIL"] = os.environ.get("DEV_AUTO_LOGIN_EMAIL")
    app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB upload limit

    if test_config:
        app.config.update(test_config)

    # Fail fast on Railway if required environment variables are missing or insecure.
    # Called before db.init_app() so the error is clear even if the URL is malformed.
    _validate_railway_env(db_url)

    # Trust Railway's HTTPS proxy so url_for(..., _external=True) produces https://
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    db.init_app(app)
    csrf.init_app(app)

    with app.app_context():
        _validate_railway_db()
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
    from otj_helper.routes.events import bp as events_bp
    from otj_helper.routes.recommendations import bp as recommendations_bp

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
    app.register_blueprint(events_bp)
    app.register_blueprint(recommendations_bp)

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


_RAILWAY_DB_PROBE_RETRIES = 3
_RAILWAY_DB_PROBE_BASE_DELAY = 2  # seconds


def _validate_railway_db() -> None:
    """Validate PostgreSQL is attached and reachable when running on Railway.

    Railway sets the ``RAILWAY_ENVIRONMENT`` variable automatically.  If it is
    present and the configured database is SQLite (i.e. ``DATABASE_URL`` was
    never linked to this service), the app raises ``RuntimeError`` immediately
    so the deploy fails with a clear log message rather than silently running
    against an ephemeral filesystem database.

    A live ``SELECT 1`` probe is executed with retries to catch cases where
    ``DATABASE_URL`` is set but the PostgreSQL instance is temporarily
    unreachable (e.g. still starting up after a deploy, brief network blip,
    or credentials not yet propagated).
    """
    if not os.environ.get("RAILWAY_ENVIRONMENT"):
        return

    if db.engine.dialect.name != "postgresql":
        raise RuntimeError(
            f"RAILWAY_ENVIRONMENT is set but the configured database dialect "
            f"'{db.engine.dialect.name}' is not supported — only PostgreSQL is "
            f"supported in this environment.\n"
            "Fix: open your Railway project, add a PostgreSQL addon, and link its "
            "DATABASE_URL variable to this service, then redeploy."
        )

    db_uri = db.engine.url.render_as_string(hide_password=True)
    logger.info("Railway environment detected (db=%s) — probing PostgreSQL connection...", db_uri)

    last_exc = None
    for attempt in range(1, _RAILWAY_DB_PROBE_RETRIES + 1):
        try:
            with db.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info(
                "Railway PostgreSQL connection probe: OK (attempt %d/%d)",
                attempt,
                _RAILWAY_DB_PROBE_RETRIES,
            )
            return
        except Exception as exc:
            last_exc = exc
            if attempt < _RAILWAY_DB_PROBE_RETRIES:
                delay = _RAILWAY_DB_PROBE_BASE_DELAY ** attempt  # 2s, 4s
                logger.warning(
                    "Railway PostgreSQL probe attempt %d/%d failed: %s "
                    "— retrying in %ds",
                    attempt,
                    _RAILWAY_DB_PROBE_RETRIES,
                    exc,
                    delay,
                )
                time.sleep(delay)

    # All retries exhausted — raise with an actionable hint.
    exc_str = str(last_exc)
    hint = (
        "The password in DATABASE_URL does not match the PostgreSQL service. "
        "This usually means the addon was re-provisioned after DATABASE_URL was set. "
        "Fix: open the Railway PostgreSQL addon → Variables tab, copy the current "
        "DATABASE_URL value, and update the reference on this service."
        if "password authentication failed" in exc_str
        else "Verify that DATABASE_URL is correct and the PostgreSQL service is running."
    )
    raise RuntimeError(
        f"Railway PostgreSQL connection failed at startup after "
        f"{_RAILWAY_DB_PROBE_RETRIES} attempts: {last_exc}\n{hint}"
    ) from last_exc


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
