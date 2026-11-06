"""app.settings: configuration from the environment (feature 002, task T004, research R2)."""

import pytest

from app.settings import load_settings

DB = "postgresql+asyncpg://user:pass@db:5432/example"


def test_cookie_secure_defaults_to_true() -> None:
    """Fails if a missing COOKIE_SECURE would send the session cookie over plain HTTP."""
    assert load_settings({"DATABASE_URL": DB}).cookie_secure is True


@pytest.mark.parametrize("value", ["false", "False", "0", "no"])
def test_cookie_secure_can_be_turned_off_for_local_development(value: str) -> None:
    """Fails if docker-compose's COOKIE_SECURE=false isn't honoured."""
    assert load_settings({"DATABASE_URL": DB, "COOKIE_SECURE": value}).cookie_secure is False


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes"])
def test_cookie_secure_true_values(value: str) -> None:
    """Fails if an explicit true value is misread."""
    assert load_settings({"DATABASE_URL": DB, "COOKIE_SECURE": value}).cookie_secure is True


def test_unrecognised_cookie_secure_value_is_refused() -> None:
    """Fails if a typo like 'flase' silently picks a setting instead of stopping."""
    with pytest.raises(ValueError, match="COOKIE_SECURE"):
        load_settings({"DATABASE_URL": DB, "COOKIE_SECURE": "flase"})


def test_database_url_is_read() -> None:
    """Fails if DATABASE_URL isn't taken from the environment."""
    assert load_settings({"DATABASE_URL": DB}).database_url == DB


def test_missing_database_url_is_refused() -> None:
    """Fails if the app could start without knowing where its database is."""
    with pytest.raises(ValueError, match="DATABASE_URL"):
        load_settings({})
