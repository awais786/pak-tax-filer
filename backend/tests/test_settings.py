"""app.settings: configuration from the environment (feature 002, task T004, research R2)."""

from pathlib import Path

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


# Feature 003, task T002: document extraction settings (research R1, R4).


def test_extraction_defaults() -> None:
    """Fails if the defaults differ from research R1/R4 (model, effort, upload folder)."""
    settings = load_settings({"DATABASE_URL": DB})

    assert settings.gemini_api_key is None
    assert settings.extraction_model == "gemini-3.5-flash-lite"
    assert settings.extraction_effort == "low"
    assert settings.upload_dir == Path("/data/uploads")


def test_extraction_settings_are_read() -> None:
    """Fails if the environment can't change the key, model, effort or upload folder."""
    settings = load_settings(
        {
            "DATABASE_URL": DB,
            "GEMINI_API_KEY": "test-key-not-real",
            "EXTRACTION_MODEL": "gemini-3.5-flash-lite",
            "EXTRACTION_EFFORT": "medium",
            "UPLOAD_DIR": "/tmp/uploads",
        }
    )

    assert settings.gemini_api_key == "test-key-not-real"
    assert settings.extraction_model == "gemini-3.5-flash-lite"
    assert settings.extraction_effort == "medium"
    assert settings.upload_dir == Path("/tmp/uploads")


def test_empty_api_key_counts_as_missing() -> None:
    """Fails if .env.example's blank `GEMINI_API_KEY=` would be sent as a key."""
    assert load_settings({"DATABASE_URL": DB, "GEMINI_API_KEY": "  "}).gemini_api_key is None


def test_unrecognised_effort_is_refused() -> None:
    """Fails if a typo like 'lwo' would only surface later as a failed extraction."""
    with pytest.raises(ValueError, match="EXTRACTION_EFFORT"):
        load_settings({"DATABASE_URL": DB, "EXTRACTION_EFFORT": "lwo"})


def test_api_key_never_appears_when_settings_are_printed() -> None:
    """Fails if logging or printing the settings would reveal the API key (security rule)."""
    settings = load_settings({"DATABASE_URL": DB, "GEMINI_API_KEY": "test-key-not-real"})

    assert "test-key-not-real" not in repr(settings)
    assert "test-key-not-real" not in str(settings)


@pytest.mark.parametrize("level", ["minimal", "low", "medium", "high"])
def test_every_gemini_thinking_level_is_accepted(level: str) -> None:
    """Fails if a thinking level Gemini accepts is refused (switch to Gemini, task T034)."""
    assert (
        load_settings({"DATABASE_URL": DB, "EXTRACTION_EFFORT": level}).extraction_effort == level
    )


@pytest.mark.parametrize("level", ["xhigh", "max"])
def test_claude_only_effort_levels_are_refused(level: str) -> None:
    """Fails if a Claude-only effort level slips through and fails every extraction later."""
    with pytest.raises(ValueError, match="EXTRACTION_EFFORT"):
        load_settings({"DATABASE_URL": DB, "EXTRACTION_EFFORT": level})


def test_the_old_anthropic_key_is_ignored() -> None:
    """Fails if a leftover ANTHROPIC_API_KEY were mistaken for the Gemini key."""
    settings = load_settings({"DATABASE_URL": DB, "ANTHROPIC_API_KEY": "old-key-not-real"})

    assert settings.gemini_api_key is None


# Feature 004, task T001: the tax summary's model and effort (research R8).


def test_summary_defaults() -> None:
    """Fails if the summary's defaults differ from feature 004's plan."""
    settings = load_settings({"DATABASE_URL": DB})

    assert settings.summary_model == "gemini-3.5-flash-lite"
    # Minimal: with "low", thinking used the token budget, cutting answers short, and took up
    # to 7.6 s against the 4 s limit (quickstart 2.2, 2026-11-10); minimal answered in ~2.5 s.
    assert settings.summary_effort == "minimal"


def test_summary_settings_are_read() -> None:
    """Fails if the environment can't change the summary's model or effort."""
    settings = load_settings(
        {"DATABASE_URL": DB, "SUMMARY_MODEL": "gemini-test-model", "SUMMARY_EFFORT": "medium"}
    )

    assert settings.summary_model == "gemini-test-model"
    assert settings.summary_effort == "medium"


def test_unrecognised_summary_effort_is_refused() -> None:
    """Fails if a typo in SUMMARY_EFFORT is only found when a summary is requested."""
    with pytest.raises(ValueError, match="SUMMARY_EFFORT"):
        load_settings({"DATABASE_URL": DB, "SUMMARY_EFFORT": "lwo"})


def test_without_a_bucket_uploads_use_the_disk() -> None:
    """Fails if development or tests could reach Google Cloud Storage by default (FR-018)."""
    assert load_settings({"DATABASE_URL": DB}).upload_bucket is None
    assert load_settings({"DATABASE_URL": DB, "UPLOAD_BUCKET": "  "}).upload_bucket is None


def test_the_upload_bucket_is_read() -> None:
    """Fails if the deployed app can't be pointed at its private bucket (FR-018)."""
    settings = load_settings({"DATABASE_URL": DB, "UPLOAD_BUCKET": " pak-tax-filer-uploads "})

    assert settings.upload_bucket == "pak-tax-filer-uploads"


# Feature 006: the answer model and the whole-app daily cap on questions (FR-009b).


def test_the_assistant_defaults_to_flash_lite_and_200_questions_a_day() -> None:
    """Fails if the assistant's model or daily cap has no sensible default."""
    settings = load_settings({"DATABASE_URL": "postgresql+asyncpg://x"})

    assert settings.answer_model == "gemini-3.5-flash-lite"
    assert settings.answer_effort == "minimal"
    assert settings.ask_daily_limit == 200


def test_the_daily_cap_can_be_set_and_must_be_a_positive_whole_number() -> None:
    """Fails if a typo in ASK_DAILY_LIMIT silently removes the cap or crashes later."""
    env = {"DATABASE_URL": "postgresql+asyncpg://x"}

    assert load_settings({**env, "ASK_DAILY_LIMIT": "50"}).ask_daily_limit == 50
    for bad in ("0", "-5", "lots", "1.5"):
        with pytest.raises(ValueError, match="ASK_DAILY_LIMIT"):
            load_settings({**env, "ASK_DAILY_LIMIT": bad})


# Feature 007: the model behind the guided run's agents (research R6).


def test_the_workflow_agents_default_to_flash_lite_at_minimal_effort() -> None:
    """Fails if the guided run's agents have no sensible model default."""
    settings = load_settings({"DATABASE_URL": "postgresql+asyncpg://x"})

    assert settings.workflow_model == "gemini-3.5-flash-lite"
    assert settings.workflow_effort == "minimal"


def test_the_workflow_model_and_effort_can_be_set_and_effort_is_checked() -> None:
    """Fails if WORKFLOW_MODEL is ignored, or a WORKFLOW_EFFORT the API rejects gets through."""
    env = {"DATABASE_URL": "postgresql+asyncpg://x"}

    settings = load_settings({**env, "WORKFLOW_MODEL": " gemini-x ", "WORKFLOW_EFFORT": "LOW"})

    assert (settings.workflow_model, settings.workflow_effort) == ("gemini-x", "low")
    with pytest.raises(ValueError, match="WORKFLOW_EFFORT"):
        load_settings({**env, "WORKFLOW_EFFORT": "extreme"})


# Feature 008: where telemetry goes (research R1; logs only, for developers).


def test_telemetry_goes_to_the_logs_by_default_and_can_be_switched_off() -> None:
    """Fails if telemetry has no default, or a typo in OTEL_EXPORTER silently loses it."""
    env = {"DATABASE_URL": "postgresql+asyncpg://x"}

    assert load_settings(env).otel_exporter == "console"
    assert load_settings({**env, "OTEL_EXPORTER": " NONE "}).otel_exporter == "none"
    with pytest.raises(ValueError, match="OTEL_EXPORTER"):
        load_settings({**env, "OTEL_EXPORTER": "jaeger"})
