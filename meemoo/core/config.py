"""Runtime configuration via pydantic-settings.

Every optional credential defaults to ``None``. A missing credential must NEVER
crash startup (Constitution Art. IX §3) — subsystems check for what they need
and degrade gracefully. See ``.env.example`` for documentation of every variable.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

VideoSource = Literal["webcam", "mjpeg_url", "file", "off"]
SttEngine = Literal["auto", "moonshine", "faster_whisper", "off"]
TtsEngine = Literal["auto", "pocket", "piper", "null"]
VadEngine = Literal["auto", "silero", "energy"]


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

    # --- Guardian (Art. IV) ---
    # L3 rings THIS number — never 911. Unset = simulated ring only.
    guardian_test_number: str | None = None
    # Auto-911 gate: exists so the gate is explicit, SHIPS OFF, and the feature
    # is deliberately unimplemented pending a signed regulatory review
    # (Constitution Art. IV §1). Setting it true logs an error and still rings
    # the test number only.
    guardian_auto_911: bool = False

    # --- Storage ---
    meemoo_db_path: str = "data/meemoo.db"
    # Device-scoped media (onboarding room photos, event evidence). Local only:
    # nothing here leaves the base station.
    meemoo_media_dir: str = "data/media"
    # Fernet key for encrypting provider keys at rest. Never logged. If unset,
    # a key is generated to meemoo_fernet_key_file on first use (never crashes).
    meemoo_fernet_key: str | None = None
    meemoo_fernet_key_file: str = "data/fernet.key"

    # --- Perception input ("off" = camera perception disabled) ---
    video_source: VideoSource = "webcam"
    video_url: str | None = None  # mjpeg_url source (future blimp camera)
    video_file: str | None = None  # file source (recorded test clips)

    # --- Voice (every stage optional; the loop degrades to text/null mode) ---
    voice_stt: SttEngine = "auto"  # auto | moonshine | faster_whisper | off
    voice_tts: TtsEngine = "auto"  # auto | pocket | piper | null
    voice_vad: VadEngine = "auto"  # auto | silero | energy
    voice_character: str = "elder_male"  # elder_male | child | female
    voice_silence_close_s: float = 45.0  # session closes after this much silence
    voice_redisclosure_s: float = 600.0  # periodic AI re-disclosure interval
    piper_voices_dir: str = "data/voices"  # downloaded Piper .onnx voices live here

    # --- Server ---
    meemoo_host: str = "127.0.0.1"
    meemoo_port: int = 8000
    # Full runtime (sim + guardian + scheduler + voice) inside the API process.
    # Off = API-only (live endpoints answer ready:false honestly). MEEMOO_RUNTIME.
    meemoo_runtime: bool = True
    # Floor plan the runtime sim flies ("apartment" | "facility_wing" | path).
    meemoo_plan: str = "apartment"

    # --- Logging ---
    log_level: str = "INFO"
    log_json: bool = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton (cached)."""
    return Settings()
