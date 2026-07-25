"""Fall state machine vs the committed landmark fixtures — the safety suite.

The three spec scenarios (research 05 §B.5) plus the §A.3 metric assertions:
per-event recall at the candidate stage MUST be 100% on bundled fall clips
(a miss here is the catastrophic class), false-candidate rate per ADL-minute,
and the time-to-candidate distribution.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from meemoo.perception.state_machine import FallState, FallStateMachine
from meemoo.perception.thresholds import load_thresholds
from meemoo.perception.types import RestZoneOracle
from tests.perception.harness import ClipRun, run_clip, sf, synthetic_clips

CLIPS = synthetic_clips()
assert CLIPS, "fixtures missing — run `uv run python -m tests.fixtures.generate_synthetic`"


def _ids(paths: list[Path]) -> list[str]:
    return [p.stem for p in paths]


@pytest.fixture(scope="module")
def runs() -> dict[str, ClipRun]:
    return {p.stem: run_clip(p) for p in CLIPS}


# ---------------------------------------------------------------- per-clip spec
@pytest.mark.parametrize("path", CLIPS, ids=_ids(CLIPS))
def test_clip_matches_expectations(path: Path, runs: dict[str, ClipRun]) -> None:
    run = runs[path.stem]
    expect = run.clip.header["expect"]
    assert (len(run.candidates) > 0) == expect["candidate"], "candidate.fall mismatch"
    assert (len(run.named("person.down")) > 0) == expect["person_down"]
    assert (len(run.named("person.recovered")) > 0) == expect["recovered"]
    assert (len(run.named("escalate.requested")) > 0) == expect["escalate"]
    max_candidates = int(expect.get("max_candidates", 1))
    assert len(run.candidates) <= max_candidates
    if expect.get("soft_only"):
        assert all(c["soft"] for c in run.candidates)


# ------------------------------------------------- scenario 1: recall = 100%
def test_candidate_recall_100_on_fall_clips(runs: dict[str, ClipRun]) -> None:
    """THE headline safety metric: every bundled fall clip must reach candidate."""
    misses = [
        name
        for name, run in runs.items()
        if run.clip.label == "fall" and not run.candidates
    ]
    total = sum(1 for r in runs.values() if r.clip.label == "fall")
    assert not misses, f"candidate-stage recall {total - len(misses)}/{total}; missed: {misses}"


def test_time_to_candidate_distribution(runs: dict[str, ClipRun]) -> None:
    """Hard falls: candidate.fall within 6 s of impact (research 05 §B.5)."""
    deltas: dict[str, float] = {}
    for name, run in runs.items():
        t_impact = run.clip.header.get("t_impact")
        if t_impact is None or not run.candidates:
            continue
        deltas[name] = float(run.candidates[0]["t"]) - float(t_impact)  # type: ignore[arg-type]
    assert deltas, "no hard-fall clips with t_impact found"
    late = {n: d for n, d in deltas.items() if d > 6.0}
    assert not late, f"time-to-candidate over 6 s: {late}"


def test_person_down_timing(runs: dict[str, ClipRun]) -> None:
    """person.down lands at T_CONFIRM (15 s) ±1 s from grounding on hard falls."""
    th = load_thresholds()
    checked = 0
    for run in runs.values():
        downs = run.named("person.down")
        if not downs or bool(downs[0].get("soft")):
            continue
        delta = float(downs[0]["t"]) - float(downs[0]["grounded_at"])  # type: ignore[arg-type]
        assert th.t_confirm - 1.0 <= delta <= th.t_confirm + 1.0, run.clip.name
        checked += 1
    assert checked >= 5


def test_candidate_timing_hard_falls(runs: dict[str, ClipRun]) -> None:
    th = load_thresholds()
    for run in runs.values():
        for c in run.candidates:
            if bool(c.get("soft")):
                continue
            delta = float(c["t"]) - float(c["grounded_at"])  # type: ignore[arg-type]
            assert th.t_candidate - 0.5 <= delta <= th.t_candidate + 1.0, run.clip.name


# --------------------------------------------- scenario 2: ADL false-alarm rate
def test_false_candidate_rate_per_adl_minute(runs: dict[str, ClipRun]) -> None:
    adl_runs = [r for r in runs.values() if r.clip.label == "adl"]
    assert adl_runs
    total_minutes = sum(r.clip.duration for r in adl_runs) / 60.0
    candidates = sum(len(r.candidates) for r in adl_runs)
    hard = sum(1 for r in adl_runs for c in r.candidates if not c.get("soft"))
    assert hard == 0, "HARD candidates during ADLs are precision failures"
    rate = candidates / total_minutes
    assert rate <= 0.5, f"false-candidate rate {rate:.2f}/ADL-minute exceeds 0.5"


def test_adls_never_reach_person_down(runs: dict[str, ClipRun]) -> None:
    offenders = [
        r.clip.name
        for r in runs.values()
        if r.clip.label == "adl" and r.named("person.down")
    ]
    assert not offenders, f"person.down during ADLs: {offenders}"


# ------------------------------------------------------------ ladder + parallel
def test_full_ladder_no_response(runs: dict[str, ClipRun]) -> None:
    run = runs["fall_no_response"]
    assert len(run.named("verify.voice_prompt")) == 2
    escalates = run.named("escalate.requested")
    assert len(escalates) == 1 and escalates[0]["reason"] == "no_response"
    assert run.machine.state is FallState.ESCALATE


def test_longlie_path_flags(runs: dict[str, ClipRun]) -> None:
    run = runs["fall_longlie_unmapped"]
    assert run.candidates[0]["cause"] == "longlie"
    assert run.candidates[0]["ballistic"] is False


def test_vanished_down_path(runs: dict[str, ClipRun]) -> None:
    run = runs["fall_vanish_bottom"]
    assert run.candidates[0]["cause"] == "vanished_down"
    # person.down fired while the pose was absent — timers ran without frames
    assert run.named("person.down")


def test_ballistic_overrides_furniture_fixture(runs: dict[str, ClipRun]) -> None:
    run = runs["fall_out_of_bed"]
    assert run.candidates and run.named("person.down")


# ------------------------------------------------------------- learning phase
class _NoZones:
    def is_rest_zone(self, x: float, y: float) -> bool:
        return False


def _machine(
    events: list[tuple[str, dict[str, object]]], learning: bool
) -> FallStateMachine:
    zones: RestZoneOracle = _NoZones()
    return FallStateMachine(
        load_thresholds(),
        zones,
        on_event=lambda n, p: events.append((n, p)),
        learning=lambda: learning,
    )


def test_learning_phase_demotes_nonballistic_to_soft() -> None:
    """During the 7-14 day learning phase, non-ballistic candidates go soft
    (later, gentler) — but the event still fires: reduced sensitivity, not
    suppression."""
    th = load_thresholds()
    events: list[tuple[str, dict[str, object]]] = []
    m = _machine(events, learning=True)
    t = 0.0
    while t < th.t_longlie + th.t_soft_candidate + 5.0:
        t += 0.2
        m.tick(sf(t, torso_angle=80.0, elevation=0.5, motion_energy=0.005))
    cands = [p for (n, p) in events if n == "candidate.fall"]
    assert len(cands) == 1
    assert cands[0]["soft"] is True and cands[0]["learning"] is True
    grounded = float(cands[0]["grounded_at"])  # type: ignore[arg-type]
    assert float(cands[0]["t"]) - grounded >= th.t_soft_candidate - 0.5  # type: ignore[arg-type]


def test_learning_phase_keeps_ballistic_hard() -> None:
    """A ballistic fall during learning is NOT demoted — recall is sacred."""
    th = load_thresholds()
    events: list[tuple[str, dict[str, object]]] = []
    m = _machine(events, learning=True)
    t = 0.0
    while t < 2.0:  # upright
        t += 1 / 15
        m.tick(sf(t))
    while t < 2.5:  # ballistic descent
        t += 1 / 15
        m.tick(
            sf(t, torso_angle=70.0, elevation=0.2, v_descent=2.5, motion_energy=0.5)
        )
    while t < 12.0:  # still on the floor
        t += 1 / 15
        m.tick(sf(t, torso_angle=85.0, elevation=0.05, motion_energy=0.005))
    cands = [p for (n, p) in events if n == "candidate.fall"]
    assert len(cands) == 1
    assert cands[0]["soft"] is False and cands[0]["ballistic"] is True
    assert float(cands[0]["t"]) <= 2.5 + th.t_settle + th.t_candidate + 1.0  # type: ignore[arg-type]
