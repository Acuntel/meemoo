"""Pure state-machine tests: full walk, bypass, ack halts, timeout ladders,
person.down from every state (Constitution Art. IX §2; step-05 gate)."""

from __future__ import annotations

import pytest

from meemoo.guardian.machine import (
    ESCALATED_STATES,
    Effect,
    EscalationMachine,
    GuardianConfig,
    State,
    Transition,
    Trigger,
)
from tests.guardian.conftest import mstate

CFG = GuardianConfig()


def machine_in(state: State, *, asks_sent: int = 0, deadline: float | None = None,
               episode: str | None = None) -> EscalationMachine:
    m = EscalationMachine(CFG)
    m.state = state
    m.asks_sent = asks_sent
    m.deadline = deadline
    m.episode_trigger = episode
    return m


def states_of(transitions: list[Transition]) -> list[tuple[str, str]]:
    return [(t.from_state.value, t.to_state.value) for t in transitions]


def effects_of(transitions: list[Transition]) -> list[Effect]:
    return [e for t in transitions for e in t.effects]


def dl(m: EscalationMachine) -> float:
    """The machine's current deadline, asserted present (mypy narrowing)."""
    assert m.deadline is not None
    return m.deadline


def dl_opt(m: EscalationMachine) -> float | None:
    """Fresh un-narrowed read of the deadline (mypy equality-narrowing)."""
    return m.deadline


# ------------------------------------------------------------ full state walk
def test_full_walk_checkin_to_l3() -> None:
    """IDLE → CHECK_IN_DUE → CHECKING → NO_RESPONSE → CONCERN (2 asks) →
    L1 → L2 → L3 — every state of the spec, driven purely by time."""
    m = EscalationMachine(CFG)
    t0 = 100.0

    out = m.handle(Trigger.CHECKIN_DUE, t0)
    assert states_of(out) == [("IDLE", "CHECK_IN_DUE")]
    assert effects_of(out) == [Effect.START_CHECKIN]

    out = m.handle(Trigger.CHECKIN_STARTED, t0 + 1)
    assert mstate(m) is State.CHECKING
    assert m.deadline == t0 + 1 + CFG.checkin_response_timeout_s

    # one second early: nothing fires
    assert m.tick(dl(m) - 1.0) == []

    # timeout: CHECKING → NO_RESPONSE → CONCERN with fly + first ask
    out = m.tick(dl(m))
    assert states_of(out) == [("CHECKING", "NO_RESPONSE"), ("NO_RESPONSE", "CONCERN")]
    assert effects_of(out) == [Effect.FLY_TO_PERSON, Effect.ASK_ARE_YOU_OK]
    assert m.asks_sent == 1

    # second ask after the verify timeout
    out = m.tick(dl(m))
    assert states_of(out) == [("CONCERN", "CONCERN")]
    assert effects_of(out) == [Effect.ASK_ARE_YOU_OK]
    assert m.asks_sent == 2

    # both asks exhausted → L1
    out = m.tick(dl(m))
    assert states_of(out) == [("CONCERN", "ESCALATE_L1")]
    assert effects_of(out) == [Effect.NOTIFY_L1]

    # N minutes, no ack → L2
    out = m.tick(dl(m))
    assert states_of(out) == [("ESCALATE_L1", "ESCALATE_L2")]
    assert effects_of(out) == [Effect.NOTIFY_L2]

    # still no ack → L3, terminal (no further deadline)
    out = m.tick(dl(m))
    assert states_of(out) == [("ESCALATE_L2", "ESCALATE_L3")]
    assert effects_of(out) == [Effect.NOTIFY_L3]
    assert dl_opt(m) is None  # terminal: no deadline pending
    assert m.tick(1e9) == []  # L3 holds until a human acks


def test_checking_ok_returns_to_idle() -> None:
    m = EscalationMachine(CFG)
    m.handle(Trigger.CHECKIN_DUE, 0.0)
    m.handle(Trigger.CHECKIN_STARTED, 1.0)
    out = m.handle(Trigger.PERSON_RESPONDED, 5.0)
    assert states_of(out) == [("CHECKING", "IDLE")]
    assert Effect.LOG_OK in effects_of(out)
    assert Effect.RESOLVE in effects_of(out)
    assert Effect.LOG_FALSE_ALARM not in effects_of(out)  # never reached CONCERN
    assert m.deadline is None


# ------------------------------------------------------- CONCERN verify paths
def test_concern_verify_ok_resolves_and_counts_false_alarm() -> None:
    m = EscalationMachine(CFG)
    m.handle(Trigger.PERSON_DOWN, 10.0)
    assert mstate(m) is State.CONCERN
    out = m.handle(Trigger.PERSON_RESPONDED, 12.0)
    assert states_of(out) == [("CONCERN", "IDLE")]
    fx = effects_of(out)
    assert Effect.LOG_OK in fx and Effect.LOG_FALSE_ALARM in fx and Effect.RESOLVE in fx
    assert out[0].detail is not None and "person.down" in out[0].detail


def test_concern_asks_exactly_twice_then_l1() -> None:
    m = EscalationMachine(CFG)
    m.handle(Trigger.PERSON_DOWN, 0.0)
    asks = 1  # entering CONCERN speaks ask 1
    while m.state is State.CONCERN:
        out = m.tick(dl(m))
        asks += sum(1 for e in effects_of(out) if e is Effect.ASK_ARE_YOU_OK)
    assert asks == CFG.verify_asks
    assert mstate(m) is State.ESCALATE_L1


# ------------------------------------------------------------ distress bypass
@pytest.mark.parametrize(
    "state", [State.IDLE, State.CHECK_IN_DUE, State.CHECKING, State.NO_RESPONSE, State.CONCERN]
)
def test_distress_goes_straight_to_l1(state: State) -> None:
    """The "help me" voice bypass: ESCALATE_L1 directly, from any lower state."""
    m = machine_in(state)
    out = m.handle(Trigger.DISTRESS, 50.0)
    assert out[-1].to_state is State.ESCALATE_L1
    assert effects_of(out) == [Effect.NOTIFY_L1]
    assert m.deadline == 50.0 + CFG.l1_ack_timeout_s
    assert m.episode_trigger == "utterance.distress"


@pytest.mark.parametrize("state", sorted(ESCALATED_STATES))
def test_distress_never_resets_an_active_escalation(state: State) -> None:
    m = machine_in(state, deadline=200.0, episode="person.down")
    assert m.handle(Trigger.DISTRESS, 60.0) == []
    assert m.state is state
    assert m.deadline == 200.0  # ack timer untouched


# ------------------------------------------------------- person.down coverage
@pytest.mark.parametrize("state", list(State))
def test_person_down_from_every_state(state: State) -> None:
    """person.down drives toward CONCERN from every state — and never
    DOWNGRADES an active escalation (monotonic-urgency rule)."""
    m = machine_in(state, deadline=500.0 if state is not State.IDLE else None)
    out = m.handle(Trigger.PERSON_DOWN, 42.0)
    if state in ESCALATED_STATES or state is State.CONCERN:
        assert out == []
        assert m.state is state  # never backward
    else:
        assert mstate(m) is State.CONCERN
        assert out[-1].to_state is State.CONCERN
        assert effects_of(out)[-2:] == [Effect.FLY_TO_PERSON, Effect.ASK_ARE_YOU_OK]
        assert m.asks_sent == 1


def test_repeated_person_down_cannot_livelock_below_l1() -> None:
    """A re-firing detector must not keep resetting the verify ladder."""
    m = EscalationMachine(CFG)
    m.handle(Trigger.PERSON_DOWN, 0.0)
    first_deadline = m.deadline
    assert m.handle(Trigger.PERSON_DOWN, 5.0) == []  # no ask-counter reset
    assert m.deadline == first_deadline
    m.tick(dl(m))  # ask 2
    m.tick(dl(m))  # → L1
    assert mstate(m) is State.ESCALATE_L1
    # and repeated person.down at L1 doesn't reset the L1 ack timer either
    l1_deadline = m.deadline
    assert m.handle(Trigger.PERSON_DOWN, 60.0) == []
    assert m.deadline == l1_deadline


# ------------------------------------------------------------------ ack halts
@pytest.mark.parametrize("state", sorted(ESCALATED_STATES))
def test_ack_halts_escalation(state: State) -> None:
    m = machine_in(state, deadline=999.0, episode="person.down")
    out = m.handle(Trigger.ACK, 70.0)
    assert states_of(out) == [(state.value, "IDLE")]
    assert effects_of(out) == [Effect.RESOLVE]
    assert m.deadline is None
    assert m.tick(1e9) == []  # ladder fully stopped


@pytest.mark.parametrize(
    "state", [State.IDLE, State.CHECK_IN_DUE, State.CHECKING, State.CONCERN]
)
def test_ack_is_noop_before_l1(state: State) -> None:
    m = machine_in(state, deadline=100.0 if state is not State.IDLE else None)
    assert m.handle(Trigger.ACK, 10.0) == []
    assert m.state is state


# ----------------------------------------------------------- timing exactness
def test_timeout_ladder_uses_configured_durations() -> None:
    cfg = GuardianConfig(
        checkin_response_timeout_s=7.0, verify_ask_timeout_s=3.0,
        l1_ack_timeout_s=11.0, l2_ack_timeout_s=13.0,
    )
    m = EscalationMachine(cfg)
    m.handle(Trigger.CHECKIN_DUE, 0.0)
    m.handle(Trigger.CHECKIN_STARTED, 1.0)
    assert m.deadline == 8.0
    m.tick(8.0)
    assert mstate(m) is State.CONCERN and m.deadline == 11.0
    m.tick(11.0)
    assert m.deadline == 14.0  # second ask window
    m.tick(14.0)
    assert mstate(m) is State.ESCALATE_L1 and m.deadline == 25.0
    m.tick(25.0)
    assert mstate(m) is State.ESCALATE_L2 and m.deadline == 38.0
    m.tick(38.0)
    assert mstate(m) is State.ESCALATE_L3 and m.deadline is None


def test_checkin_that_never_starts_still_escalates() -> None:
    """Safety net: if START_CHECKIN fails silently, the timeout still walks
    CHECK_IN_DUE → NO_RESPONSE → CONCERN instead of hanging forever."""
    m = EscalationMachine(CFG)
    m.handle(Trigger.CHECKIN_DUE, 0.0)
    assert m.deadline == CFG.checkin_response_timeout_s
    out = m.tick(dl(m))
    assert states_of(out) == [("CHECK_IN_DUE", "NO_RESPONSE"), ("NO_RESPONSE", "CONCERN")]


def test_checkin_due_ignored_during_active_episode() -> None:
    m = machine_in(State.CONCERN, asks_sent=1, deadline=100.0, episode="person.down")
    assert m.handle(Trigger.CHECKIN_DUE, 10.0) == []
    assert mstate(m) is State.CONCERN


def test_person_responded_after_l1_does_not_halt() -> None:
    """After contacts are ringing only a HUMAN ack halts the ladder."""
    m = machine_in(State.ESCALATE_L1, deadline=100.0, episode="utterance.distress")
    assert m.handle(Trigger.PERSON_RESPONDED, 50.0) == []
    assert mstate(m) is State.ESCALATE_L1
    assert m.deadline == 100.0


def test_auto_911_flag_ships_off() -> None:
    assert GuardianConfig().auto_dial_911 is False
