"""Provider tables: encrypted API keys, tier→model routing, token usage.

``provider_keys.encrypted_key`` holds a Fernet token (see
:mod:`meemoo.core.secrets`). The plaintext key exists only transiently in
memory; it is never stored, never logged, and never appears in ``repr()``.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from meemoo.core.models.base import Base, CreatedAtMixin, utcnow

TIERS = ("reflex", "conversation", "reasoning")


class ProviderKey(Base, CreatedAtMixin):
    """An owner-supplied provider API key, Fernet-encrypted at rest."""

    __tablename__ = "provider_keys"
    __table_args__ = (
        UniqueConstraint("device_id", "provider", name="uq_provider_keys_device_provider"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)  # anthropic|openai|...
    encrypted_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column()

    def __repr__(self) -> str:  # NEVER include key material — even ciphertext.
        return f"<ProviderKey id={self.id} device_id={self.device_id} provider={self.provider!r}>"


class ModelConfig(Base):
    """Tier → provider+model mapping per device (reflex/conversation/reasoning)."""

    __tablename__ = "model_config"
    __table_args__ = (UniqueConstraint("device_id", "tier", name="uq_model_config_device_tier"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False, index=True)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=512)


class Usage(Base):
    """One row per LLM request: tokens + estimated cost → the cost meter."""

    __tablename__ = "usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False, index=True)
    ts: Mapped[datetime] = mapped_column(nullable=False, default=utcnow, index=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
