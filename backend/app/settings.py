"""Configuration from environment variables (feature 002, research R2; feature 003, R1/R4).

Values are never written in code or committed files: docker-compose.yml sets them for local
development, and CI sets them for tests.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

_TRUE = {"true", "1", "yes"}
_FALSE = {"false", "0", "no"}
# The thinking levels Gemini accepts (google-genai ThinkingLevel), lower-cased.
_EFFORTS = ("minimal", "low", "medium", "high")


@dataclass(frozen=True)
class Settings:  # pylint: disable=too-many-instance-attributes  # one field per setting
    """The app's settings; read once per process with get_settings()."""

    database_url: str
    # Send the session cookie over HTTPS only. On unless explicitly turned off, so a missing
    # setting fails safe; only local development over plain HTTP sets COOKIE_SECURE=false.
    cookie_secure: bool
    # Gemini API key (free, from AI Studio) for document extraction. Optional, so tests and CI
    # (fake extractor) run without one; extraction then fails with a clear reason. Kept out of
    # repr so printing or logging the settings never reveals it.
    gemini_api_key: str | None = field(default=None, repr=False)
    # Research R1: Flash-Lite passed the eval (T029); Flash timed out on the free tier.
    extraction_model: str = "gemini-3.5-flash-lite"
    extraction_effort: str = "low"
    # Research R4: uploaded files live in a Docker volume, never under the app's own folder.
    upload_dir: Path = Path("/data/uploads")
    # Feature 003 FR-018: the private Cloud Storage bucket for uploads in the deployed app; None
    # (development, tests) keeps them in upload_dir. Reached with the VM's own identity: no key.
    upload_bucket: str | None = None
    # Feature 006, research R5 (amended): the model that answers from the cited passages.
    answer_model: str = "gemini-3.5-flash-lite"
    answer_effort: str = "minimal"
    # Feature 006, FR-009b: questions a day for the whole app (the free Gemini quota is shared).
    ask_daily_limit: int = 200
    # Feature 008, research R1: telemetry to the backend logs ("console") or nowhere ("none").
    otel_exporter: str = "console"
    # Feature 011, research R3: signs the admin area's CSRF and flash cookies. Optional: without
    # it the library makes a start-up key (one backend process). Kept out of repr.
    admin_secret_key: str | None = field(default=None, repr=False)
    # Feature 011, research R9: save request and AI-call telemetry in the database (on unless
    # TELEMETRY_STORE=off; tests set it off).
    telemetry_store: bool = True


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

    effort = _effort(environ, "EXTRACTION_EFFORT")

    return Settings(
        database_url=database_url,
        cookie_secure=cookie_secure,
        gemini_api_key=environ.get("GEMINI_API_KEY", "").strip() or None,
        extraction_model=environ.get("EXTRACTION_MODEL", "").strip() or "gemini-3.5-flash-lite",
        extraction_effort=effort,
        upload_dir=Path(environ.get("UPLOAD_DIR", "").strip() or "/data/uploads"),
        upload_bucket=environ.get("UPLOAD_BUCKET", "").strip() or None,
        answer_model=environ.get("ANSWER_MODEL", "").strip() or "gemini-3.5-flash-lite",
        answer_effort=_effort(environ, "ANSWER_EFFORT", default="minimal"),
        ask_daily_limit=_positive_int(environ, "ASK_DAILY_LIMIT", default=200),
        otel_exporter=otel_exporter(environ),
        admin_secret_key=admin_secret_key(environ),
        telemetry_store=telemetry_store(environ),
    )


def otel_exporter(environ: Mapping[str, str]) -> str:
    """Where telemetry goes; anything but console or none is refused (no viewer in 008). Read
    on its own by app.telemetry, so importing the app needs no DATABASE_URL."""
    exporter = environ.get("OTEL_EXPORTER", "console").strip().lower()
    if exporter not in ("console", "none"):
        raise ValueError(f"OTEL_EXPORTER must be console or none, not {exporter!r}.")
    return exporter


def admin_secret_key(environ: Mapping[str, str]) -> str | None:
    """The admin area's signing key, or None (feature 011, research R3). Read on its own, so
    mounting the admin area when the app is imported needs no DATABASE_URL."""
    return environ.get("ADMIN_SECRET_KEY", "").strip() or None


def telemetry_store(environ: Mapping[str, str]) -> bool:
    """Whether telemetry is saved in the database (feature 011): `on` (default) or `off`. Read on
    its own, like otel_exporter, so the telemetry setup needs no DATABASE_URL."""
    raw = environ.get("TELEMETRY_STORE", "on").strip().lower()
    if raw not in ("on", "off"):
        raise ValueError(f"TELEMETRY_STORE must be on or off, not {raw!r}.")
    return raw == "on"


def _positive_int(environ: Mapping[str, str], name: str, default: int) -> int:
    """A whole number above zero; anything else is refused."""
    raw = environ.get(name, "").strip()
    if not raw:
        return default
    if not raw.isdigit() or int(raw) < 1:
        raise ValueError(f"{name} must be a whole number above 0, not {raw!r}.")
    return int(raw)


def _effort(environ: Mapping[str, str], name: str, default: str = "low") -> str:
    """An effort setting; anything the API wouldn't accept is refused."""
    effort = environ.get(name, default).strip().lower()
    if effort not in _EFFORTS:
        raise ValueError(f"{name} must be one of {', '.join(_EFFORTS)}, not {effort!r}.")
    return effort


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """The process's settings, read from os.environ on first use."""
    return load_settings(os.environ)


# The tax years the app can calculate: the one list the profile offers (FR-017, research R13).
# A year is added here only together with its FBR rates (feature 004 tests that each has them).
SUPPORTED_TAX_YEARS: tuple[str, ...] = ("2025-26",)
