"""Config smoke tests: missing credentials must never crash (Art. IX §3)."""

from __future__ import annotations

from meemoo.core.config import Settings, get_settings


def test_settings_load_with_no_credentials(bare_settings: Settings) -> None:
    assert bare_settings.anthropic_api_key is None
    assert bare_settings.openai_api_key is None
    assert bare_settings.google_api_key is None
    assert bare_settings.ollama_url is None
    assert bare_settings.twilio_account_sid is None
    assert bare_settings.twilio_auth_token is None
    assert bare_settings.twilio_from_number is None
    assert bare_settings.meemoo_fernet_key is None


def test_settings_defaults(bare_settings: Settings) -> None:
    assert bare_settings.video_source == "webcam"
    assert bare_settings.meemoo_db_path == "data/meemoo.db"
    assert bare_settings.meemoo_port == 8000
    assert bare_settings.log_json is False


def test_get_settings_is_cached() -> None:
    get_settings.cache_clear()
    assert get_settings() is get_settings()
