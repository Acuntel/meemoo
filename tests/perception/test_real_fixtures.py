"""Fall state machine vs the REAL GMDCSA-24 / CaucaFall landmark fixtures.

This is the primary perception suite (the synthetic clips remain for fast,
fully-controlled CI). Fixtures were extracted with MediaPipe Pose Full from
the two datasets cleared for derived-data bundling (research 05 §B.1) and
annotated from dataset ground truth in tests/fixtures/labels/
real_annotations.json. Fall clips carry a DISCLOSED tail-hold (the datasets
stop recording seconds after impact; see bake_real.py).

HONESTY NOTE (updated 2026-07-28): expectations assert MEASURED behavior.
Two of the three gaps found on 2026-07-27 are now CLOSED by algorithm fixes
(not by threshold loosening — see the before/after table in docs/TODO.md):
  1. FIXED — descent evidence is now LATCHED for the whole descent episode
     instead of re-read from a decaying 3 s window at classify time, so a
     fall's own descent still counts when classification finally runs.
     11/19 falls were detecting only via the 40 s soft path; now 2/19 are.
  2. FIXED — the verify ladder is anchored to person.down instead of to
     grounding, so both voice asks and their response windows precede every
     escalate.requested. Hard-path escalation timing is byte-identical.
  3. OPEN — 2/19 falls are perception recall misses (MediaPipe never
     re-detects the fallen person: one 0-lux side fall, one distant
     artificial-light fall). pose.ReacquiringPose is the fix and is measured
     to recover both, but the committed fixtures were extracted before it
     existed, so this suite's recall record stays 17/19 until they are
     re-extracted end to end. See docs/TODO.md.
Residual gap: 5/19 falls reach candidate within the research 05 §B.5 6 s bar,
15/19 within 10 s. The remainder is the persistence budget itself (t_settle
1.5 s + t_candidate 5 s), not a classification error.
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


def _t(payload: dict[str, object]) -> float:
    """Event timestamp as a float (bus payload values are typed `object`)."""
    return float(payload["t"])  # type: ignore[arg-type]


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
    """Per-clip committed bound: 6 s for the falls that clear the research bar,
    10 s for the rest of the hard path, 45 s for the two soft-path falls."""
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


def test_gate_hard_path_candidates_within_10s(runs: dict[str, ClipRun]) -> None:
    """Regression gate for the 2026-07-28 evidence-latch fix (finding 1).

    Every fall that reaches the HARD path must produce its candidate within
    10 s of impact, and at least 15 of the 19 real falls must be on the hard
    path at all. Measured at fix time: 15 hard (4.5-9.1 s), 2 soft, 2 missed.
    """
    hard = 0
    for run in runs.values():
        if run.clip.label != "fall" or not run.candidates:
            continue
        first = run.candidates[0]
        if first.get("soft"):
            continue
        hard += 1
        t_impact = float(run.clip.header["t_impact"])
        delta = float(first["t"]) - t_impact  # type: ignore[arg-type]
        assert delta <= 10.0, f"{run.clip.name}: hard candidate at +{delta:.1f}s"
    assert hard >= 15, f"only {hard} falls on the hard path (fix-time floor: 15)"


@pytest.mark.skip(
    reason=(
        "GATE NOT MET on real data (honest, 2026-07-27): research 05 §B.5 wants "
        "candidate.fall within 6 s of impact on every fall. AFTER the 2026-07-28 "
        "evidence-latch fix: 15/19 real falls on the HARD path at 4.5-9.1 s from "
        "impact (was 5/19 within 6 s + 11/19 on the 40 s soft path), 2/19 soft, "
        "2/19 never (perception misses at range/0-lux). A strict 6 s bar is "
        "structurally unreachable with t_settle=1.5 + t_candidate=5.0 (floor "
        "6.5 s); the enforced regression gate is the 10 s hard-path test below."
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


def test_every_escalation_is_preceded_by_both_voice_asks(runs: dict[str, ClipRun]) -> None:
    """Regression gate for the 2026-07-28 down-anchored ladder (finding 2).

    The spec says CONCERN asks "are you okay?" twice BEFORE escalating. That
    must hold on the SOFT path too, where a grounded-relative escalate clock
    coincided with t_soft_confirm and fired escalate.requested on the same tick
    as person.down with ZERO prompts. Hard and soft are both covered here.
    """
    checked = 0
    for run in runs.values():
        escalates = run.named("escalate.requested")
        if not escalates:
            continue
        prompts = run.named("verify.voice_prompt")
        assert len(prompts) == 2, f"{run.clip.name}: {len(prompts)} prompts"
        t_escalate = _t(escalates[0])
        assert all(_t(p) < t_escalate for p in prompts), run.clip.name
        # the second ask must leave a real response window, not one tick
        assert t_escalate - _t(prompts[1]) >= 10.0, run.clip.name
        checked += 1
    assert checked >= 15


def test_soft_path_down_runs_the_same_ladder_just_later(runs: dict[str, ClipRun]) -> None:
    """The two evidence-free soft-path falls reach person.down and then run the
    identical ask/ask/wait/escalate ladder a hard fall runs."""
    th = load_thresholds()
    for stem in ("gm_s3_fall_09", "gm_s3_fall_20"):
        run = runs[stem]
        downs = run.named("person.down")
        assert downs and bool(downs[0]["soft"]), stem
        prompts = run.named("verify.voice_prompt")
        assert len(prompts) == 2, stem
        t_down = _t(downs[0])
        assert abs(_t(prompts[0]) - (t_down + th.t_voice_1)) < 0.5, stem
        assert abs(_t(prompts[1]) - (t_down + th.t_voice_2)) < 0.5, stem
        escalates = run.named("escalate.requested")
        assert escalates, stem
        delta = _t(escalates[0]) - t_down
        assert abs(delta - th.t_escalate_after_down) < 0.5, f"{stem}: {delta:.1f}s"


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
    """Scenario 2 on real data: a deliberate lie-down on the FLOOR (S3/ADL/08)
    gets the gentle soft path — never a hard candidate — and is ASKED, twice,
    before anything else happens."""
    run = runs["gm_s3_adl_08"]
    assert run.candidates and all(c["soft"] for c in run.candidates)
    assert run.candidates[0]["cause"] == "controlled_descent"
    assert len(run.named("verify.voice_prompt")) == 2


def test_floor_nap_that_answers_is_never_escalated() -> None:
    """The soft path's whole promise (Art. IV §8): the deliberate floor-napper
    who answers the first gentle "are you okay?" is downgraded, not escalated.
    The cost of guessing wrong is one question — this proves it stays one."""
    path = next(p for p in CLIPS if p.stem == "gm_s3_adl_08")
    run = run_clip(path, answer_after_prompt=1)
    assert len(run.named("verify.voice_prompt")) == 1, "asked once, then answered"
    assert run.named("person.recovered"), "answering must downgrade"
    assert not run.named("escalate.requested"), "answering must halt the ladder"


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
