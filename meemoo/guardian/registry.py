"""Process-wide handle to the running GuardianService.

The REST layer (acknowledge endpoint, SMS webhook) must reach the live
machine to halt escalation — but api/ must not construct guardian internals
(Art. II §2). Whoever wires the app (demo runner, main entrypoint, tests)
registers the service here; the API only calls its public methods. With no
service registered the API still works DB-only (ack rows persist; the
machine halt is a no-op) — nothing crashes (Art. IX §3).
"""

from __future__ import annotations

from meemoo.guardian.service import GuardianService

_active: GuardianService | None = None


def set_active_service(service: GuardianService | None) -> None:
    """Register (or clear) the running guardian for API access."""
    global _active
    _active = service


def get_active_service() -> GuardianService | None:
    return _active
