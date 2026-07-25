"""Care tables: check-in schedule, conversations, alerts, consent, memory.

``memory_facts`` is Meemoo's per-person structured memory (Constitution
Art. V §1): names, preferences, workout history — explicit, inspectable,
deletable rows. There are deliberately NO biometric columns (no face
templates, no voiceprints, no embeddings) anywhere in this schema; a reviewer
must be able to inspect the pipeline and find no template store.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from meemoo.core.models.base import Base, CreatedAtMixin, utcnow


class CheckinSchedule(Base):
    """Scheduled check-in times per device (defaults: 9a / 1p / 6p / 9p)."""

    __tablename__ = "checkin_schedule"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False, index=True)
    time_of_day: Mapped[str] = mapped_column(String(5), nullable=False)  # "HH:MM" local
    label: Mapped[str | None] = mapped_column(String(120))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Conversation(Base):
    """One voice session; ``mood_note`` is the brain's post-chat summary."""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False, index=True)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("persons.id"))
    started_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column()
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="companion")
    mood_note: Mapped[str | None] = mapped_column(Text)


class Message(Base):
    """One utterance in a conversation (transcripts; raw audio never kept)."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id"), nullable=False, index=True
    )
    ts: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user|assistant|system
    content: Mapped[str] = mapped_column(Text, nullable=False)


class Alert(Base):
    """An escalation instance with its acknowledgment state.

    Escalation-relevant → carries model/prompt/threshold version stamps.
    """

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False, index=True)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("persons.id"))
    level: Mapped[str] = mapped_column(String(4), nullable=False)  # L1|L2|L3
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
    acknowledged_at: Mapped[datetime | None] = mapped_column()
    acknowledged_by_contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id"))
    evidence_event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"))
    model_version: Mapped[str | None] = mapped_column(String(80))
    prompt_version: Mapped[str | None] = mapped_column(String(80))
    threshold_version: Mapped[str | None] = mapped_column(String(80))


class ConsentRecord(Base, CreatedAtMixin):
    """Person-scoped consent (Constitution Art. V; roommate/surrogate-ready).

    ``scope`` examples: "camera", "transcripts", "event_clips", "share:nurse".
    ``method`` examples: "verbal", "written", "app". Surrogate fields support
    LAR/roommate consent objects required before go-live (Art. VI §2).
    """

    __tablename__ = "consent_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False, index=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id"), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(120), nullable=False)
    method: Mapped[str] = mapped_column(String(40), nullable=False)
    consenting_party: Mapped[str] = mapped_column(String(120), nullable=False)
    is_surrogate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    surrogate_relationship: Mapped[str | None] = mapped_column(String(60))
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    revoked_at: Mapped[datetime | None] = mapped_column()


class MemoryFact(Base, CreatedAtMixin):
    """One structured memory fact about a person — NO biometrics by design.

    Categories: "name", "preference", "workout", "schedule", "context".
    Rows are inspectable and deletable (``deleted_at`` soft delete keeps the
    audit trail honest while honoring "forget that").
    """

    __tablename__ = "memory_facts"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False, index=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    source_conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id"))
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=100)  # 0..100
    updated_at: Mapped[datetime | None] = mapped_column()
    deleted_at: Mapped[datetime | None] = mapped_column()
