"""Meemoo data model — every table keyed by ``device_id`` (fleet-ready).

Split across small modules (300-line rule); import everything from here so
``Base.metadata`` always knows the full schema:

- fleet: devices, persons, contacts, settings
- providers: provider_keys (Fernet-encrypted), model_config, usage
- care: checkin_schedule, conversations, messages, alerts, consent_records,
  memory_facts
- flight: routes, waypoints, dock_telemetry
- audit: events + audit_log (append-only via DB triggers; hash-chained)

By design there are NO biometric columns anywhere (Constitution Art. V §1).
"""

from meemoo.core.models.audit import (
    APPEND_ONLY_TABLES,
    AuditLog,
    Event,
    append_audit,
    verify_audit_chain,
)
from meemoo.core.models.base import Base, utcnow
from meemoo.core.models.care import (
    Alert,
    CheckinSchedule,
    ConsentRecord,
    Conversation,
    MemoryFact,
    Message,
)
from meemoo.core.models.fleet import Contact, Device, Person, Setting
from meemoo.core.models.flight import DockTelemetry, Route, Waypoint
from meemoo.core.models.onboarding import (
    ROOM_PHOTO_TARGET,
    NoGoZoneRow,
    OnboardingRecord,
    RoomCapture,
)
from meemoo.core.models.providers import TIERS, ModelConfig, ProviderKey, Usage

__all__ = [
    "APPEND_ONLY_TABLES",
    "ROOM_PHOTO_TARGET",
    "TIERS",
    "Alert",
    "AuditLog",
    "Base",
    "CheckinSchedule",
    "ConsentRecord",
    "Contact",
    "Conversation",
    "Device",
    "DockTelemetry",
    "Event",
    "MemoryFact",
    "Message",
    "ModelConfig",
    "NoGoZoneRow",
    "OnboardingRecord",
    "Person",
    "ProviderKey",
    "RoomCapture",
    "Route",
    "Setting",
    "Usage",
    "Waypoint",
    "append_audit",
    "utcnow",
    "verify_audit_chain",
]
