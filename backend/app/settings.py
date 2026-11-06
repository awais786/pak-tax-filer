"""Configuration from environment variables (feature 002, research R2).

Values are never written in code or committed files: docker-compose.yml sets them for local
development, and CI sets them for tests.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache

_TRUE = {"true", "1", "yes"}
_FALSE = {"false", "0", "no"}


@dataclass(frozen=True)
class Settings:
    """The app's settings; read once per process with get_settings()."""

    database_url: str
    # Send the session cookie over HTTPS only. On unless explicitly turned off, so a missing
    # setting fails safe; only local development over plain HTTP sets COOKIE_SECURE=false.
    cookie_secure: bool


def load_settings(environ: Mapping[str, str]) -> Settings:
    """Build Settings from an environment mapping, refusing missing or unclear values."""
    database_url = environ.get("DATABASE_URL", "")
    if not database_url:
        raise ValueError("DATABASE_URL is not set; docker-compose.yml sets it for the backend.")

    raw = environ.get("COOKIE_SECURE", "true").strip().lower()
    if raw in _TRUE:
        cookie_secure = True
    elif raw in _FALSE:
        cookie_secure = False
    else:
        raise ValueError(f"COOKIE_SECURE must be true or false, not {raw!r}.")

    return Settings(database_url=database_url, cookie_secure=cookie_secure)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """The process's settings, read from os.environ on first use."""
    return load_settings(os.environ)


# The tax years the app can calculate: the one list the profile offers (FR-017, research R13).
# A year is added here only together with its FBR rates (feature 004 tests that each has them).
SUPPORTED_TAX_YEARS: tuple[str, ...] = ("2025-26",)
