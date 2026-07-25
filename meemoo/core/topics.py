"""Typed event-bus topic strings (Constitution Art. II §2).

Modules communicate ONLY over the bus; these constants are the shared
vocabulary. Topics are dot-separated, lowercase, most-general first
(``person.down``, ``escalation.l1``). Subscribers may use wildcard patterns
(``person.*`` or ``*``) — see :func:`topic_matches`.

Add new topics HERE, not as ad-hoc strings in modules, so the vocabulary
stays greppable and typo-proof.
"""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Final

# --- Perception -------------------------------------------------------------
PERSON_DETECTED: Final = "person.detected"
CANDIDATE_FALL: Final = "candidate.fall"  # internal ~5 s signal — dispatch blimp, no alarm
PERSON_DOWN: Final = "person.down"
PERSON_RECOVERED: Final = "person.recovered"

# --- Voice ------------------------------------------------------------------
UTTERANCE_HEARD: Final = "utterance.heard"
UTTERANCE_PARTIAL: Final = "utterance.partial"  # streaming partial transcript
DISTRESS_HEARD: Final = "utterance.distress"  # local keyword hit — Art. IV §4/§5
CRISIS_HEARD: Final = "utterance.crisis"  # deterministic 988 protocol — Art. V §5
STOP_HEARD: Final = "voice.stop"  # barge-in: stop playback immediately
VOICE_SESSION_OPENED: Final = "voice.session_opened"
VOICE_SESSION_CLOSED: Final = "voice.session_closed"
VOICE_SPEAKING: Final = "voice.speaking"  # payload {"on": bool} — ducking hook

# --- Guardian ---------------------------------------------------------------
CHECKIN_DUE: Final = "checkin.due"
ESCALATION_L1: Final = "escalation.l1"
ESCALATION_L2: Final = "escalation.l2"
ESCALATION_L3: Final = "escalation.l3"  # payload includes {"full_screen_alert": True}
ESCALATION_ACKNOWLEDGED: Final = "escalation.acknowledged"
ESCALATION_RESOLVED: Final = "escalation.resolved"
GUARDIAN_STATE: Final = "guardian.state"  # every transition, for the dashboard
NOTIFY_SENT: Final = "notify.sent"  # payload {"simulated": bool, ...} — drives fake call UI

# --- Flight -----------------------------------------------------------------
FLIGHT_DISPATCH: Final = "flight.dispatch"  # guardian requests a flight (Phase 6 subscribes)
FLIGHT_TAKEOFF: Final = "flight.takeoff"
FLIGHT_WAYPOINT_REACHED: Final = "flight.waypoint_reached"
FLIGHT_BATTERY: Final = "flight.battery"
FLIGHT_LANDED: Final = "flight.landed"

# --- Dock (its own device — Constitution Art. II §3) ------------------------
DOCK_REQUESTED: Final = "dock.requested"
DOCK_CAPTURED: Final = "dock.captured"
DOCK_RELEASED: Final = "dock.released"
DOCK_CHARGING: Final = "dock.charging"

ALL_TOPICS: Final[frozenset[str]] = frozenset(
    v for k, v in globals().items() if k.isupper() and isinstance(v, str) and "." in v
)


def topic_matches(pattern: str, topic: str) -> bool:
    """True if ``topic`` matches ``pattern`` (exact, ``person.*``, or ``*``)."""
    if pattern == topic:
        return True
    return fnmatchcase(topic, pattern)
