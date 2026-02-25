"""Google OAuth authentication routes."""

import os

from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.flask_client import OAuth
from flask import Blueprint, flash, g, redirect, render_template, session, url_for

from otj_helper.models import User, db

bp = Blueprint("auth", __name__, url_prefix="/auth")
oauth = OAuth()


def init_oauth(app):
    oauth.init_app(app)
    oauth.register(
        name="google",
        client_id=app.config.get("GOOGLE_CLIENT_ID"),
        client_secret=app.config.get("GOOGLE_CLIENT_SECRET"),
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


def _allowed_emails():
    raw = os.environ.get("ALLOWED_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


@bp.route("/login")
def login():
    if g.user:
        return redirect(url_for("dashboard.index"))
    return render_template("auth/login.html")


@bp.route("/google")
def google_login():
    if not oauth.google.client_id or not oauth.google.client_secret:
        flash(
            "Google OAuth is not configured. Set GOOGLE_CLIENT_ID and "
            "GOOGLE_CLIENT_SECRET environment variables, or use "
            "DEV_AUTO_LOGIN_EMAIL for local development.",
            "error",
        )
        return redirect(url_for("auth.login"))
    redirect_uri = url_for("auth.callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@bp.route("/callback")
def callback():
    try:
        token = oauth.google.authorize_access_token()
    except OAuthError as e:
        flash(
            f"Google sign-in failed: {e.description or str(e)}. "
            "Check that your GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are correct "
            "and that the redirect URI is authorised in Google Cloud Console.",
            "error",
        )
        return redirect(url_for("auth.login"))
    userinfo = token.get("userinfo")

    email = userinfo["email"].lower()
    allowed = _allowed_emails()
    if allowed and email not in allowed:
        return redirect(url_for("auth.denied"))

    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(
            email=email,
            name=userinfo.get("name", email),
            google_sub=userinfo.get("sub"),
        )
        db.session.add(user)
        db.session.commit()
    elif user.google_sub is None:
        user.google_sub = userinfo.get("sub")
        db.session.commit()

    session["user_id"] = user.id

    next_url = session.pop("next", None)
    return redirect(next_url or url_for("dashboard.index"))


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/denied")
def denied():
    return render_template("auth/denied.html"), 403
