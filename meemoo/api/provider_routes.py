"""Provider REST: keys (write-only, masked read), tiers, presets, voices, usage.

Keys are Fernet-encrypted at rest and NEVER returned in plaintext — the GET
shows provider + last four characters only (write-only pattern, step-07 §1).
Managed-vs-self-serve framing (Art. VII §2) lives in the UI; this API is the
BYO ("advanced") surface.
"""

from __future__ import annotations

import io
import logging
import wave
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from meemoo.api.deps import get_db
from meemoo.brain.presets import load_presets
from meemoo.brain.providers import KNOWN_PROVIDERS
from meemoo.brain.router import DEFAULT_ROUTES
from meemoo.brain.usage import PRICING_VERSION, price_for
from meemoo.core.models import TIERS, ModelConfig, ProviderKey, Usage
from meemoo.core.secrets import SecretDecryptError, decrypt_secret, encrypt_secret
from meemoo.voice.tts import NullTTS, create_tts
from meemoo.voice.types import TTS
from meemoo.voice.voices import VOICES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["providers"])

Db = Annotated[Session, Depends(get_db)]

PREVIEW_LINES = {
    "elder_male": "Well hello there. I'm Meemoo, and it's lovely to meet you.",
    "child": "Hi hi! I'm Meemoo! Want to be friends?",
    "female": "Hello, I'm Meemoo. I'm so glad you're here.",
}

_tts_cache: TTS | None = None


def _shared_tts() -> TTS:
    """One TTS engine per process (model load is expensive)."""
    global _tts_cache
    if _tts_cache is None:
        _tts_cache = create_tts()
    return _tts_cache


# ---------------------------------------------------------------------- keys
class KeyBody(BaseModel):
    provider: str = Field(min_length=1, max_length=40)
    key: str = Field(min_length=4)


class KeyOut(BaseModel):
    provider: str
    masked: str
    created_at: str


def _masked(row: ProviderKey) -> KeyOut:
    tail = "????"
    try:
        tail = decrypt_secret(row.encrypted_key)[-4:]
    except SecretDecryptError:
        logger.warning("stored key not decryptable for masking")
    return KeyOut(
        provider=row.provider,
        masked=f"••••••••{tail}",
        created_at=row.created_at.isoformat(),
    )


@router.get("/devices/{device_id}/keys")
def list_keys(device_id: int, db: Db) -> list[KeyOut]:
    rows = db.query(ProviderKey).filter(ProviderKey.device_id == device_id).all()
    return [_masked(r) for r in rows]


@router.post("/devices/{device_id}/keys", status_code=201)
def put_key(device_id: int, body: KeyBody, db: Db) -> KeyOut:
    """Store (upsert) a provider key — encrypted at rest, never logged."""
    row = (
        db.query(ProviderKey)
        .filter(ProviderKey.device_id == device_id, ProviderKey.provider == body.provider)
        .one_or_none()
    )
    if row is None:
        row = ProviderKey(
            device_id=device_id, provider=body.provider,
            encrypted_key=encrypt_secret(body.key),
        )
        db.add(row)
    else:
        row.encrypted_key = encrypt_secret(body.key)
    db.commit()
    logger.info(  # provider name only — NEVER key material
        "provider key stored", extra={"fields": {"provider": body.provider}}
    )
    return _masked(row)


@router.delete("/devices/{device_id}/keys/{provider}", status_code=204)
def delete_key(device_id: int, provider: str, db: Db) -> None:
    count = (
        db.query(ProviderKey)
        .filter(ProviderKey.device_id == device_id, ProviderKey.provider == provider)
        .delete()
    )
    db.commit()
    if count == 0:
        raise HTTPException(status_code=404, detail="no key for that provider")


@router.get("/providers")
def list_providers(db: Db, device_id: int = 1) -> list[dict[str, object]]:
    """Known providers + whether a key/URL is configured (env or DB)."""
    from meemoo.core.config import get_settings

    settings = get_settings()
    with_db_key = {
        row.provider
        for row in db.query(ProviderKey).filter(ProviderKey.device_id == device_id)
    }
    env_key = {
        "anthropic": bool(settings.anthropic_api_key),
        "openai": bool(settings.openai_api_key),
        "google": bool(settings.google_api_key),
        "ollama": bool(settings.ollama_url),
    }
    return [
        {
            "name": name,
            "configured": name in with_db_key or env_key.get(name, False),
            "source": "db" if name in with_db_key else ("env" if env_key.get(name) else None),
        }
        for name in KNOWN_PROVIDERS
        if name != "fake"
    ]


# -------------------------------------------------------------- model config
class TierBody(BaseModel):
    provider: str = Field(min_length=1, max_length=40)
    model: str = Field(min_length=1, max_length=120)
    max_tokens: int = Field(default=512, ge=16, le=8192)


@router.get("/devices/{device_id}/model-config")
def get_model_config(device_id: int, db: Db) -> list[dict[str, object]]:
    rows = {
        r.tier: r
        for r in db.query(ModelConfig).filter(ModelConfig.device_id == device_id).all()
    }
    out: list[dict[str, object]] = []
    for tier in TIERS:
        row = rows.get(tier)
        provider, model, max_tokens = (
            (row.provider, row.model, row.max_tokens)
            if row is not None
            else DEFAULT_ROUTES[tier]
        )
        prices = price_for(model)
        out.append({
            "tier": tier, "provider": provider, "model": model,
            "max_tokens": max_tokens, "configured": row is not None,
            "price_per_mtok": {"input": prices[0], "output": prices[1]} if prices else None,
        })
    return out


@router.put("/devices/{device_id}/model-config/{tier}")
def put_model_config(device_id: int, tier: str, body: TierBody, db: Db) -> dict[str, object]:
    if tier not in TIERS:
        raise HTTPException(status_code=404, detail=f"unknown tier; use one of {TIERS}")
    row = (
        db.query(ModelConfig)
        .filter(ModelConfig.device_id == device_id, ModelConfig.tier == tier)
        .one_or_none()
    )
    if row is None:
        row = ModelConfig(device_id=device_id, tier=tier, **body.model_dump())
        db.add(row)
    else:
        for key, value in body.model_dump().items():
            setattr(row, key, value)
    db.commit()
    logger.info(
        "model config updated",
        extra={"fields": {"device_id": device_id, "tier": tier,
                          "provider": body.provider, "model": body.model}},
    )
    return {"tier": tier, **body.model_dump(), "configured": True}


# ------------------------------------------------------------------- presets
@router.get("/presets")
def get_presets() -> list[dict[str, object]]:
    """The role picker's data (Art. VII §3): roles → personality sub-presets."""
    out: list[dict[str, object]] = []
    for preset in load_presets().values():
        out.append({
            "role": preset.role,
            "title": preset.title,
            "version": preset.version,
            "context": preset.context,  # power users may open the raw context
            "default_sub": preset.default_sub,
            "sub_presets": [
                {"key": s.key, "title": s.title, "context": s.context}
                for s in preset.sub_presets.values()
            ],
        })
    return out


# -------------------------------------------------------------------- voices
@router.get("/voices")
def get_voices() -> list[dict[str, object]]:
    return [
        {"key": v.key, "label": v.label, "description": v.description,
         "verified": v.verified}
        for v in VOICES.values()
    ]


@router.get("/voice/preview")
def voice_preview(character: str = "elder_male", text: str | None = None) -> Response:
    """A short WAV in the chosen character — 503 when no TTS engine exists."""
    tts = _shared_tts()
    if isinstance(tts, NullTTS):
        raise HTTPException(
            status_code=503,
            detail="no TTS engine installed (uv sync --group voice + Piper voices)",
        )
    line = text or PREVIEW_LINES.get(character, PREVIEW_LINES["elder_male"])
    pcm = b"".join(tts.synthesize(line[:200], character))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(tts.sample_rate)
        wav.writeframes(pcm)
    return Response(content=buf.getvalue(), media_type="audio/wav")


# --------------------------------------------------------------------- usage
@router.get("/devices/{device_id}/usage")
def get_usage(device_id: int, db: Db, days: int = 30) -> dict[str, object]:
    """The cost meter: today's totals + a daily series (Art. VIII dashboard)."""
    now = datetime.now(UTC).replace(tzinfo=None)
    start = (now - timedelta(days=min(days, 90))).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    rows = (
        db.query(
            func.date(Usage.ts),
            func.count(Usage.id),
            func.coalesce(func.sum(Usage.input_tokens), 0),
            func.coalesce(func.sum(Usage.output_tokens), 0),
            func.coalesce(func.sum(Usage.cost_usd), 0.0),
        )
        .filter(Usage.device_id == device_id, Usage.ts >= start)
        .group_by(func.date(Usage.ts))
        .order_by(func.date(Usage.ts))
        .all()
    )
    series: list[dict[str, object]] = []
    costs: list[float] = []
    for d, n, i, o, c in rows:
        cost = round(float(c), 6)
        costs.append(cost)
        series.append({
            "date": str(d), "requests": int(n), "input_tokens": int(i),
            "output_tokens": int(o), "cost_usd": cost,
        })
    today = str(now.date())
    today_row = next((s for s in series if s["date"] == today), None)
    est_monthly = (sum(costs) / max(len(costs), 1)) * 30.0
    return {
        "pricing_version": PRICING_VERSION,
        "today": today_row or {"date": today, "requests": 0, "cost_usd": 0.0},
        "series": series,
        "estimated_monthly_usd": round(est_monthly, 2),
    }
