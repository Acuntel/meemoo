"""Recovery paths: standing up, voice verification, snooze, help bypass."""

from __future__ import annotations

from meemoo.perception.state_machine import FallState, FallStateMachine
from meemoo.perception.thresholds import load_thresholds
from tests.perception.harness import ClipRun, run_clip, sf, synthetic_clips


def _clip(name: str) -> ClipRun:
    (path,) = [p for p in synthetic_clips() if p.stem == name]
    return run_clip(path)


# --------------------------------------------------------- scenario 3: fixtures
def test_recovery_before_down_logs_near_miss() -> None:
    run = _clip("recovery_fall_standup")
    assert run.candidates and not run.named("person.down")
    assert run.named("person.recovered")
    assert len(run.machine.near_misses) == 1
    assert run.machine.state is FallState.UPRIGHT


def test_recovery_during_verifying_halts_ladder() -> None:
    run = _clip("recovery_after_down")
    downs = run.named("person.down")
    recovered = run.named("person.recovered")
    assert downs and recovered
    assert recovered[0]["t"] > downs[0]["t"]  # type: ignore[operator]
    assert not run.named("escalate.requested")


def test_short_floor_sit_exits_silently() -> None:
    """A 20 s floor sit never hits a timer: no events, no near-miss spam."""
    run = _clip("adl_sit_floor_short")
    assert not run.events
    assert not run.machine.near_misses


# ------------------------------------------------------------- voice interface
class _NoZones:
    def is_rest_zone(self, x: float, y: float) -> bool:
        return False


def _drive_to_verifying() -> tuple[FallStateMachine, list[tuple[str, dict[str, object]]], float]:
    events: list[tuple[str, dict[str, object]]] = []
    m = FallStateMachine(
        load_thresholds(), _NoZones(), on_event=lambda n, p: events.append((n, p))
    )
    t = 0.0
    while t < 1.0:
        t += 1 / 15
        m.tick(sf(t))
    while t < 1.5:
        t += 1 / 15
        m.tick(sf(t, torso_angle=70.0, elevation=0.2, v_descent=2.5, motion_energy=0.5))
    while m.state is not FallState.VERIFYING and t < 60.0:
        t += 1 / 15
        m.tick(sf(t, torso_angle=85.0, elevation=0.05, motion_energy=0.005))
    assert m.state is FallState.VERIFYING
    return m, events, t


def test_voice_ok_snoozes_and_recovers() -> None:
    m, events, t = _drive_to_verifying()
    m.notify_voice_ok(t)
    assert m.state is FallState.SNOOZED
    recovered = [p for (n, p) in events if n == "person.recovered"]
    assert recovered and recovered[0]["reason"] == "voice_ok"
    # no escalation while snoozed and still on the floor
    for _ in range(60):
        t += 1 / 15
        m.tick(sf(t, torso_angle=85.0, elevation=0.05, motion_energy=0.005))
    assert not [n for (n, _) in events if n == "escalate.requested"]


def test_new_ballistic_fall_while_snoozed_still_fires() -> None:
    """Snooze is NOT blindness: a fresh ballistic descent re-arms instantly."""
    m, events, t = _drive_to_verifying()
    m.notify_voice_ok(t)
    events.clear()
    for _ in range(8):  # new violent drop while snoozed
        t += 1 / 15
        m.tick(sf(t, torso_angle=85.0, elevation=0.05, v_descent=2.8, motion_energy=0.5))
    assert m.state is FallState.GROUNDED_CANDIDATE
    for _ in range(15 * 8):
        t += 1 / 15
        m.tick(sf(t, torso_angle=85.0, elevation=0.05, motion_energy=0.005))
    cands = [p for (n, p) in events if n == "candidate.fall"]
    assert cands and cands[0]["cause"] == "fall_while_snoozed"


def test_voice_help_escalates_immediately() -> None:
    """'help' during verification bypasses every remaining timer (Art. IV §5)."""
    m, events, t = _drive_to_verifying()
    m.notify_voice_help(t)
    assert m.state is FallState.ESCALATE
    escalates = [p for (n, p) in events if n == "escalate.requested"]
    assert escalates and escalates[0]["reason"] == "voice_help"


def test_recovery_from_escalate_emits_recovered() -> None:
    m, events, t = _drive_to_verifying()
    m.notify_voice_help(t)
    events.clear()
    for _ in range(15 * 3):
        t += 1 / 15
        m.tick(sf(t))  # upright defaults
    assert m.state is FallState.UPRIGHT
    assert [n for (n, _) in events if n == "person.recovered"]
