"""Process-wide handle to the running SimulatedBlimp (guardian/registry twin).

The API layer must not construct flight internals (Art. II §2); whoever
wires the app registers the sim here. With none registered the endpoints
report ``ready: False`` and nothing crashes (Art. IX §3).
"""

from __future__ import annotations

from meemoo.flight.sim_blimp import SimulatedBlimp

_active: SimulatedBlimp | None = None


def set_active_sim(sim: SimulatedBlimp | None) -> None:
    """Register (or clear) the running sim for API access."""
    global _active
    _active = sim


def get_active_sim() -> SimulatedBlimp | None:
    return _active
