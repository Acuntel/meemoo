"""Fleet tables: devices, persons, contacts, settings.

``persons`` is structured, inspectable memory of WHO Meemoo cares for —
names, rooms, notes. By design (Constitution Art. V §1) there are NO biometric
columns anywhere in this schema: no face templates, no voiceprints, no
embeddings. People are keyed by schedule/room/self-identification only.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from meemoo.core.models.base import Base, CreatedAtMixin


class Device(Base, CreatedAtMixin):
    """One Meemoo unit (blimp + dock + base-station config)."""

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # "home" | "facility" — changes spatial + escalation defaults later.
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="home")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Per-device privacy toggle: transcript storage default ON (Art. V §2).
    store_transcripts: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # The code printed on the aircraft (MEEMOO-XXXX-XXXX). Binding it here is
    # the replacement-unit flow's foundation (Amendment A1): unbox the new
    # aircraft, type its code, it connects to this same base station.
    pairing_code: Mapped[str | None] = mapped_column(String(20))

    persons: Mapped[list[Person]] = relationship(back_populates="device")


class Person(Base, CreatedAtMixin):
    """A cared-for person. NO biometric fields — architectural prohibition."""

    __tablename__ = "persons"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    preferred_name: Mapped[str | None] = mapped_column(String(120))
    room: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)

    device: Mapped[Device] = relationship(back_populates="persons")


class Contact(Base, CreatedAtMixin):
    """Escalation contact — ordered per device (L1 walks the order)."""

    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False, index=True)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("persons.id"))
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    relationship_label: Mapped[str | None] = mapped_column(String(60))
    phone: Mapped[str | None] = mapped_column(String(40))
    notify_sms: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notify_call: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Setting(Base):
    """Per-device key/value settings (JSON values)."""

    __tablename__ = "settings"
    __table_args__ = (UniqueConstraint("device_id", "key", name="uq_settings_device_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[dict[str, object]] = mapped_column(nullable=False, default=dict)
    updated_at: Mapped[datetime | None] = mapped_column()
