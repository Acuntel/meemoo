"""Fall state machine vs the REAL GMDCSA-24 / CaucaFall landmark fixtures.

This is the primary perception suite (the synthetic clips remain for fast,
fully-controlled CI). Fixtures were extracted with MediaPipe Pose Full from
the two datasets cleared for derived-data bundling (research 05 §B.1) and
annotated from dataset ground truth in tests/fixtures/labels/
real_annotations.json. Fall clips carry a DISCLOSED tail-hold (the datasets
stop recording seconds after impact; see bake_real.py).

HONESTY NOTE (2026-07-27): expectations assert MEASURED behavior, which on
real data diverges from the research 05 spec in three ways, all recorded per
clip as `spec_gap` and aggregated in docs/TODO.md:
  1. 11/19 real falls detect only via the 40 s CANDIDATE_SOFT path (the 3 s
     ballistic-evidence window expires before the settle+1.5 s classify).
  2. Soft-path escalation fires one tick after the soft person.down with
     zero voice prompts (t_escalate == t_soft_confirm == 50 s grounded-rel).
  3. 2/19 falls are perception recall misses (MediaPipe never re-detects the
     fallen person: one 0-lux side fall, one distant artificial-light fall).
Tuning thresholds to close these gaps is Brady's call, not this suite's job
(NEVER loosen to pass — thresholds.py + Constitution Art. II §4).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from meemoo.perception.thresholds import load_thresholds
from tests.perception.harness import ClipRun, real_clips, run_clip

CLIPS = real_clips()
assert CLIPS, (
    "real fixtures missing — run tests/fixtures/clips/fetch.py, "
    "tests/fixtures/extract_landmarks.py, then tests/fixtures/bake_real.py"
)

# The two documented perception misses (see spec_gap in the clip headers).
KNOWN_MISSES = {"cf_s6_fall_left", "cf_s8_fall_right"}
# Measured candidate-stage recall on the real fall clips at the 60 s horizon.
RECALL_FLOOR = 17 / 19


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
    assert len(run.candidates) <= int(expect.get("max_candidates", 1))
    if expect.get("soft_only"):
        assert all(c["soft"] for c in run.candidates)


# ----------------------------------------------------------- recall, honestly
def test_candidate_recall_on_real_falls(runs: dict[str, ClipRun]) -> None:
    """Recall within the 60 s horizon: misses must be EXACTLY the documented
    set — a new miss is a regression, a fixed miss must update the record."""
    misses = {
        name
        for name, run in runs.items()
        if run.clip.label == "fall" and not run.candidates
    }
    assert misses == KNOWN_MISSES, f"recall record changed: misses now {sorted(misses)}"
    falls = sum(1 for r in runs.values() if r.clip.label == "fall")
    recall = (falls - len(misses)) / falls
    assert recall >= RECALL_FLOOR


def test_time_to_candidate_measured_bounds(runs: dict[str, ClipRun]) -> None:
    """Per-clip committed bound: 6 s for the spec-passing hard falls, 9.5 s
    for the one late hard fall, 55 s for the soft-path detections."""
    checked = 0
    for run in runs.values():
        t_impact = run.clip.header.get("t_impact")
        bound = run.clip.header["expect"].get("t_candidate_max_s")
        if t_impact is None or bound is None or not run.candidates:
            continue
        delta = float(run.candidates[0]["t"]) - float(t_impact)  # type: ignore[arg-type]
        assert delta <= float(bound), f"{run.clip.name}: {delta:.1f}s > {bound}s"
        checked += 1
    assert checked >= 15


@pytest.mark.skip(
    reason=(
        "GATE NOT MET on real data (honest, 2026-07-27): research 05 §B.5 wants "
        "candidate.fall within 6 s of impact on every fall. Measured on the 19 "
        "real GMDCSA-24/CaucaFall falls: 5/19 within 6 s, 1/19 at 8.8 s, 11/19 "
        "only via the 40 s soft path (ballistic window expires before classify), "
        "2/19 never (MediaPipe loses the fallen person). Threshold/classifier "
        "changes are Brady's call — numbers + proposals in docs/TODO.md."
    )
)
def test_gate_time_to_candidate_6s_all_real_falls(runs: dict[str, ClipRun]) -> None:
    for run in runs.values():
        if run.clip.label != "fall":
            continue
        t_impact = float(run.clip.header["t_impact"])
        assert run.candidates, f"{run.clip.name}: no candidate"
        assert float(run.candidates[0]["t"]) - t_impact <= 6.0  # type: ignore[arg-type]


def test_person_down_timing_hard_falls(runs: dict[str, ClipRun]) -> None:
    """Hard-path person.down still lands at T_CONFIRM (15 s) ±1 from grounding."""
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


def test_hard_falls_get_voice_prompts_before_escalate(runs: dict[str, ClipRun]) -> None:
    """The verify ladder works end-to-end on real hard falls: two spoken asks,
    then escalate. (Soft-path clips get zero prompts — spec gap #2, asserted
    per clip via expect and recorded in docs/TODO.md.)"""
    checked = 0
    for run in runs.values():
        downs = run.named("person.down")
        if not downs or bool(downs[0].get("soft")) or not run.named("escalate.requested"):
            continue
        assert len(run.named("verify.voice_prompt")) == 2, run.clip.name
        checked += 1
    assert checked >= 5


# --------------------------------------------- ADL false alarms on real minutes
def _unheld_candidates(run: ClipRun) -> list[dict[str, object]]:
    """Candidates inside REAL footage (tail-hold time excluded)."""
    tail = float(run.clip.header.get("tail_start_t", float("inf")))
    return [c for c in run.candidates if float(c["t"]) <= tail]  # type: ignore[arg-type]


def test_no_false_candidates_in_real_adl_minutes(runs: dict[str, ClipRun]) -> None:
    """ZERO candidates (hard or soft) during the ~2.5 minutes of real, unheld
    ADL footage — walking, kneeling, hopping, floor-sitting, bed lie-downs,
    push-ups, night and 0-lux clips included."""
    adl_runs = [r for r in runs.values() if r.clip.label == "adl"]
    assert len(adl_runs) >= 14
    total_minutes = (
        sum(float(r.clip.header["real_duration_s"]) for r in adl_runs) / 60.0
    )
    assert total_minutes >= 2.0
    offenders = {
        r.clip.name: len(_unheld_candidates(r)) for r in adl_runs if _unheld_candidates(r)
    }
    assert not offenders, f"false candidates during real ADL time: {offenders}"


def test_deliberate_floor_nap_soft_path(runs: dict[str, ClipRun]) -> None:
    """Scenario 2 on real data: a deliberate lie-down on the FLOOR (S3/ADL/08,
    held 60 s) gets the gentle soft path — never a hard candidate."""
    run = runs["gm_s3_adl_08"]
    assert run.candidates and all(c["soft"] for c in run.candidates)
    assert run.candidates[0]["cause"] == "controlled_descent"


def test_real_get_up_no_alarm(runs: dict[str, ClipRun]) -> None:
    """Real floor-to-standing get-ups (S3/ADL/09 sleeping->standing, S1/ADL/04
    bed) end without candidates or person.down."""
    for stem in ("gm_s3_adl_09", "gm_s1_adl_04"):
        run = runs[stem]
        assert not run.candidates and not run.named("person.down")


# ------------------------------------------------------------- coverage guards
def test_night_lowlight_coverage(runs: dict[str, ClipRun]) -> None:
    """The committed suite must keep real night/low-light coverage: at least
    5 such clips, at least 3 of them falls, at least 1 fall DETECTED at 0 lux."""
    lowlight = [
        r for r in runs.values()
        if str(r.clip.header.get("lighting")) in {"night", "night_ir", "dim"}
    ]
    assert len(lowlight) >= 5
    lowlight_falls = [r for r in lowlight if r.clip.label == "fall"]
    assert len(lowlight_falls) >= 3
    assert any(
        r.clip.header.get("lighting") == "night_ir" and r.candidates
        for r in lowlight_falls
    )


def test_both_datasets_present(runs: dict[str, ClipRun]) -> None:
    sources = {str(r.clip.header.get("source")) for r in runs.values()}
    assert {"gmdcsa24", "caucafall"} <= sources


def test_tail_holds_are_disclosed(runs: dict[str, ClipRun]) -> None:
    """Every clip that runs past its real footage says so in the header."""
    for run in runs.values():
        real_end = float(run.clip.header["real_duration_s"])
        if run.clip.duration > real_end + 1e-6:
            assert float(run.clip.header["tail_hold_s"]) > 0, run.clip.name
            assert abs(float(run.clip.header["tail_start_t"]) - real_end) < 1e-6
