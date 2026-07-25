"""Runtime configuration via pydantic-settings.

Every optional credential defaults to ``None``. A missing credential must NEVER
crash startup (Constitution Art. IX §3) — subsystems check for what they need
and degrade gracefully. See ``.env.example`` for documentation of every variable.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

VideoSource = Literal["webcam", "mjpeg_url", "file"]


class Settings(BaseSettings):
    """All environment-driven configuration in one place."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM providers (all optional; scripted no-key fallback always works) ---
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    google_api_key: str | None = None
    ollama_url: str | None = None

    # --- Twilio: demo calls ONLY, behind the notifier adapter (Art. III §3) ---
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_from_number: str | None = None

    # --- Storage ---
    meemoo_db_path: str = "data/meemoo.db"
    # Fernet key for encrypting provider keys at rest; generated on first run
    # (Phase 1). Never logged.
    meemoo_fernet_key: str | None = None

    # --- Perception input ---
    video_source: VideoSource = "webcam"
    video_url: str | None = None  # mjpeg_url source (future blimp camera)
    video_file: str | None = None  # file source (recorded test clips)

    # --- Server ---
    meemoo_host: str = "127.0.0.1"
    meemoo_port: int = 8000

    # --- Logging ---
    log_level: str = "INFO"
    log_json: bool = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton (cached)."""
    return Settings()
