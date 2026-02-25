"""Shared pytest fixtures for the OTJ Helper test suite."""

import pytest

from otj_helper.app import create_app


@pytest.fixture()
def app():
    """Create an application configured for testing with an in-memory SQLite DB."""
    application = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SECRET_KEY": "test-secret-key",
            "WTF_CSRF_ENABLED": False,
            "DEV_AUTO_LOGIN_EMAIL": "test@example.com",
        }
    )
    yield application


@pytest.fixture()
def client(app):
    """A test client for the application."""
    return app.test_client()


@pytest.fixture()
def _with_spec(client):
    """Set the ST0787 spec on the auto-login test user.

    Asserts the redirect succeeds so test failures surface fixture problems
    rather than hiding them as unrelated assertion errors later.
    """
    resp = client.get("/select-spec?spec=ST0787", follow_redirects=True)
    assert resp.status_code == 200, f"_with_spec fixture failed: HTTP {resp.status_code}"
