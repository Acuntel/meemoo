"""Guardian vocabulary: states, triggers, effects, config, transitions.

Shared by the pure machine (:mod:`meemoo.guardian.machine`) and the effect
executor (:mod:`meemoo.guardian.service`). See machine.py's docstring for the
full spec and the monotonic-urgency rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

CONFIG_VERSION = "guardian-sm-v1"  # stamped into audit detail on every transition


class State(StrEnum):
    """Guardian escalation states (MASTER_PROMPT §4)."""

    IDLE = "IDLE"
    CHECK_IN_DUE = "CHECK_IN_DUE"
    CHECKING = "CHECKING"
    NO_RESPONSE = "NO_RESPONSE"  # transient: always advances to CONCERN
    CONCERN = "CONCERN"  # verify loop: fly to person + "are you okay?" ×2
    ESCALATE_L1 = "ESCALATE_L1"
    ESCALATE_L2 = "ESCALATE_L2"
    ESCALATE_L3 = "ESCALATE_L3"


ESCALATED_STATES = frozenset({State.ESCALATE_L1, State.ESCALATE_L2, State.ESCALATE_L3})


class Trigger(StrEnum):
    """External inputs (bus events) + the internal timeout tick."""

    CHECKIN_DUE = "checkin.due"
    CHECKIN_STARTED = "checkin.started"
    PERSON_RESPONDED = "person.responded"  # any non-distress utterance heard
    PERSON_DOWN = "person.down"
    DISTRESS = "utterance.distress"
    ACK = "escalation.acknowledged"
    TIMEOUT = "timeout"


class Effect(StrEnum):
    """Side effects requested by a transition — executed by the service."""

    START_CHECKIN = "start_checkin"  # sim round dispatch + spoken greeting
    FLY_TO_PERSON = "fly_to_person"  # sim flight to the person's location
    ASK_ARE_YOU_OK = "ask_are_you_ok"  # spoken verify prompt (fixed template)
    NOTIFY_L1 = "notify_l1"  # open alert + notify family contacts
    NOTIFY_L2 = "notify_l2"  # notify remaining contacts / staff
    NOTIFY_L3 = "notify_l3"  # ring TEST number + full-screen alert (never 911)
    LOG_OK = "log_ok"  # person responded fine
    LOG_FALSE_ALARM = "log_false_alarm"  # concern+ episode resolved by voice OK
    RESOLVE = "resolve"  # close the episode/alert


@dataclass(frozen=True)
class GuardianConfig:
    """Timeout ladder. Committed defaults — override per deployment, never in
    tests to make a walk pass (the sim-honesty rule applies to time too)."""

    checkin_response_timeout_s: float = 30.0
    verify_ask_timeout_s: float = 20.0
    verify_asks: int = 2
    l1_ack_timeout_s: float = 180.0  # "N minutes" — 3 min default
    l2_ack_timeout_s: float = 180.0
    # Art. IV §1: auto-911 requires a signed regulatory review to add. The flag
    # exists so the gate is explicit, SHIPS OFF, and the feature is deliberately
    # NOT implemented — see service._run_notify (documented TODO).
    auto_dial_911: bool = False


@dataclass(frozen=True)
class Transition:
    """One recorded state change (audit row source)."""

    from_state: State
    to_state: State
    trigger: str
    at: float
    effects: tuple[Effect, ...] = ()
    detail: str | None = None
