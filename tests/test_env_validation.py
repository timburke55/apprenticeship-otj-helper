"""Tests for Railway environment variable validation and DATABASE_URL normalisation."""

import pytest

from otj_helper.app import _normalize_db_url_password, _validate_railway_env


# ---------------------------------------------------------------------------
# _normalize_db_url_password
# ---------------------------------------------------------------------------


def test_normalize_plain_url_unchanged():
    """A URL with no special characters in the password is returned unchanged."""
    url = "postgresql://user:simplepass@host:5432/db"
    assert _normalize_db_url_password(url) == url


def test_normalize_encodes_at_sign_in_password():
    """An un-encoded @ in the password is re-encoded as %40."""
    url = "postgresql://user:p%40ss@host:5432/db"
    result = _normalize_db_url_password(url)
    assert "%40" in result
    assert result.count("@") == 1  # only the userinfo/host separator remains


def test_normalize_encodes_hash_in_password():
    """A # character (which starts a URL fragment) is encoded as %23."""
    # Simulate a pre-encoded URL where the password contains a literal #
    url = "postgresql://user:pass%23word@host:5432/db"
    result = _normalize_db_url_password(url)
    assert "%23" in result


def test_normalize_encodes_percent_in_password():
    """A literal % in the password (encoded as %25) survives the round-trip."""
    url = "postgresql://user:pass%25word@host:5432/db"
    result = _normalize_db_url_password(url)
    assert "%25" in result


def test_normalize_no_password_returns_unchanged():
    """A URL without a password component is returned unchanged."""
    url = "postgresql://host:5432/db"
    assert _normalize_db_url_password(url) == url


def test_normalize_preserves_host_and_port():
    """Host and port are not altered during normalisation."""
    url = "postgresql://user:p%40ss@myhost.railway.internal:5432/railway"
    result = _normalize_db_url_password(url)
    assert "myhost.railway.internal" in result
    assert "5432" in result
    assert "/railway" in result


def test_normalize_invalid_url_returns_unchanged():
    """An unparseable string is returned as-is rather than raising."""
    bad = "not_a_url"
    assert _normalize_db_url_password(bad) == bad


# ---------------------------------------------------------------------------
# _validate_railway_env
# ---------------------------------------------------------------------------


def _good_db_url():
    return "postgresql://user:secret@host:5432/db"


def test_validate_no_railway_env_is_noop(monkeypatch):
    """Outside Railway the validator is a no-op regardless of other vars."""
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    # No error even though SECRET_KEY and OAuth are missing
    _validate_railway_env(_good_db_url())


def test_validate_all_good(monkeypatch):
    """No error when all required variables are set correctly on Railway."""
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "a" * 64)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "client-secret")
    _validate_railway_env(_good_db_url())


def test_validate_dev_login_accepted_instead_of_oauth(monkeypatch):
    """DEV_AUTO_LOGIN_EMAIL satisfies the auth requirement when OAuth is absent."""
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "a" * 64)
    monkeypatch.setenv("DEV_AUTO_LOGIN_EMAIL", "dev@example.com")
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    _validate_railway_env(_good_db_url())


def test_validate_missing_secret_key(monkeypatch):
    """A missing SECRET_KEY raises RuntimeError with an actionable message."""
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        _validate_railway_env(_good_db_url())


def test_validate_insecure_default_secret_key(monkeypatch):
    """The hardcoded dev SECRET_KEY default is rejected on Railway."""
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "dev-key-change-in-production")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        _validate_railway_env(_good_db_url())


def test_validate_no_auth_method(monkeypatch):
    """Missing both OAuth credentials and DEV_AUTO_LOGIN_EMAIL raises RuntimeError."""
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "a" * 64)
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("DEV_AUTO_LOGIN_EMAIL", raising=False)
    with pytest.raises(RuntimeError, match="login method"):
        _validate_railway_env(_good_db_url())


def test_validate_partial_oauth_counts_as_missing(monkeypatch):
    """Only GOOGLE_CLIENT_ID set (no secret) is treated as no OAuth configured."""
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "a" * 64)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("DEV_AUTO_LOGIN_EMAIL", raising=False)
    with pytest.raises(RuntimeError, match="login method"):
        _validate_railway_env(_good_db_url())


def test_validate_db_url_missing_password(monkeypatch):
    """A DATABASE_URL with no password component raises RuntimeError."""
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "a" * 64)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
    no_password_url = "postgresql://user@host:5432/db"
    with pytest.raises(RuntimeError, match="password"):
        _validate_railway_env(no_password_url)


def test_validate_db_url_missing_host(monkeypatch):
    """A DATABASE_URL with no host raises RuntimeError."""
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "a" * 64)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
    with pytest.raises(RuntimeError, match="host"):
        _validate_railway_env("postgresql://user:pass@/db")


def test_validate_multiple_errors_reported_together(monkeypatch):
    """All problems are reported in a single RuntimeError, not one at a time."""
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("DEV_AUTO_LOGIN_EMAIL", raising=False)
    with pytest.raises(RuntimeError) as exc_info:
        _validate_railway_env(_good_db_url())
    message = str(exc_info.value)
    assert "SECRET_KEY" in message
    assert "login method" in message
