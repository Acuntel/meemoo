"""Shared fixtures: a clean environment with NO credentials configured."""

from __future__ import annotations

from pathlib import Path

import pytest

from meemoo.core.config import Settings, get_settings

_CRED_VARS = [
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GOOGLE_API_KEY",
    "OLLAMA_URL",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_FROM_NUMBER",
    "MEEMOO_FERNET_KEY",
]


@pytest.fixture
def bare_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    """Settings built with zero credentials in the environment and no .env file."""
    for var in _CRED_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)  # relative ".env" resolves here: none exists
    get_settings.cache_clear()
    return Settings()
