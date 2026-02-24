"""Auth helpers: login_required decorator."""

from functools import wraps

from flask import g, redirect, request, session, url_for


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if g.user is None:
            session["next"] = request.url
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return decorated
