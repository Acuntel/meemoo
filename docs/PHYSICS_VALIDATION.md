# Physics cross-validation: 2D sim vs MuJoCo 3D rig

> 2026-07-28. `sim3d/` package, `make physics3d` reruns everything.
> Raw numbers: `docs/assets/physics3d_results.json`. Both engines ran the
> SAME `DockingController` build (commit of this doc), zero control-logic
> changes. The 2D baseline was re-measured the same day with the same
> episode contract. Nothing was tuned to make either side look better.

## Headline

The docking controller that scores 16% first-attempt in our 2D sim scores
**7% first-attempt in MuJoCo** — and the miss is in the same place (the
underactuated lateral loop vs drafts), so the 2D sim's honest-failure
diagnosis stands. The 3D rig also surfaced four physical findings the 2D
sim could not see (below); two of them change what the Phase-9 bench must
answer.

## Docking: 200 randomized episodes per cell

Contract per episode: random start within 3 m of the dock (front
half-space, +-60 deg), random heading, z 0.6-1.8 m, net buoyancy drawn
from +-5 gf (both signs, drifting), HVAC drafts ON, sigma-5 cm room pose,
20 Hz dock camera, 100 ms command latency, 6 attempts max.

| Metric | 2D sim (50 Hz) | MuJoCo 50 Hz | MuJoCo 10 Hz |
|---|---|---|---|
| First-attempt success | **16.0%** | **7.0%** | 7.5% |
| Success within one retry | 35.0% | 10.5% | 13.5% |
| Success within six attempts | 63.5% | 28.0% | 31.5% |
| Median time-to-dock (successes) | 83.9 s | 81.6 s | 64.1 s |
| p90 time-to-dock | 157.2 s | 129.3 s | 115.5 s |
| Median approach speed at mouth contact | n/a (not recorded) | 0.214 m/s | 0.258 m/s |
| Max capture speed observed | n/a | 0.392 m/s | 0.423 m/s |
| Captures across buoyancy range | yes, both signs | -4.9..+4.8 gf | -4.9..+4.8 gf |

Failure modes, MuJoCo 50 Hz (144 failed episodes, all `DOCK_FAILED` after
6 attempts — no timeouts):

- **FINAL_APPROACH aborts dominate: 772 aborts** (predicted-miss and
  mouth-gate trips). Same signature as the 2D root-cause analysis: with
  near-zero drag and single-digit-gf authority, the reactive lateral loop
  cannot hold the beam against drafts of the same magnitude; braking
  poisons steering.
- **CAPTURE_PENDING aborts: 209.** New in 3D: the cone is 35 cm deep
  (vs 10 cm in the 2D funnel), so the in-funnel slide takes seconds and
  the "bounced off" gate (`v_axis < -0.10`) plus the "went past beside
  the dock" gate (dead-reckoned lateral > 0.15 m on sigma-5 cm noise at
  range < -0.2 m) fire mid-slide. 35 of the 144 failures died within
  **5 cm** of the magnet.
- 247 mouth entries across 200 episodes: the controller reaches the cone
  far more often than it captures. Getting IN the funnel is not the hard
  part; surviving the slide gates is.

Control rate matters less than expected for success (7.0% vs 7.5%), but
station-keeping degrades at 10 Hz in BOTH engines (2D hover error at
10 Hz: 0.54 m mean — the 2D gate itself was measured at the sim's 50 Hz
tick). The interface spec's "10 Hz" is compatible with the observed
success level, but the published 2D gate numbers implicitly assume 50 Hz.

## Bump test: 1 N x 0.2 s shove mid-hover, 50 paired episodes

| Metric | damper ON (50 Hz) | damper OFF (50 Hz) | damper ON (10 Hz) | damper OFF (10 Hz) |
|---|---|---|---|---|
| Median peak tilt after shove | 18.7 deg | 18.9 deg | 17.6 deg | 17.7 deg |
| Runs reaching <2 deg for 3 s within 60 s | 10/50 | 6/50 | 6/50 | 4/50 |
| Median settle time (settled runs only) | 5.4 s | 5.9 s | 12.8 s | 14.1 s |

Honest reading (see `docs/assets/physics3d_bump_settle.png`): the shove
transient itself dies in ~3-5 s, but the hover CONTROLLER sustains a
3-7 deg rocking at the pendulum period indefinitely — thrust acts at the
gondola, 78 mm below the center of buoyancy, so every horizontal
correction pitches the vehicle. The 2 deg settle band is therefore rarely
held, damper or not. And the damper's effect is marginal in 3D because a
random-azimuth shove mostly excites ROLL, which forward-thrust rate
feedback cannot touch (the published "swing-reducer" only lives in the
pitch plane). At 10 Hz the damper is actively counterproductive on the
true 1.4 s pendulum in single-seed tests (phase lag from 100 ms latency +
ZOH turns rate feedback into excitation); across the ensemble it nets out
to roughly no effect.

## Physical findings (the 3D-only deliverables)

1. **The assigned dock geometry forces a long docking boom.** A 0.61 m
   sphere cannot enter a 40 cm mouth: it seats on the mouth rim with its
   center 23 cm out. Reaching a magnet 35 cm deep therefore requires a
   probe ~0.585 m from sphere center — a **28 cm boom** proud of the
   envelope. Bench question: probe length vs cone depth tradeoff (a
   shallower cone with the magnet at the rim-seat point needs almost no
   boom).
2. **A 12 cm throat cannot hand the tip to a 15 mm-proximity magnet.**
   Measured in-rig: the tip slides the cone and stalls at the throat
   opening up to 5 cm off the magnet axis — capture NEVER triggers. The
   rig adds a second-stage centering cup (12 cm -> 1.2 cm over the last
   6 cm of the same 35 cm depth); with it, capture works from 12 cm of
   initial lateral offset. The bench funnel needs the same feature (or a
   much bigger magnet face).
3. **The 2D sim's added mass is ~2x the first-principles value.** MuJoCo's
   ellipsoid model computes the sphere's virtual mass as 0.5*rho*V =
   71.5 g; the 2D sim (per research/06 SectionG) uses the full displaced
   mass, 144.5 g. Effective inertia: 197 g (engine) vs 269.5 g (2D).
   The controller was left believing the 2D value — model error is part
   of the test — and still worked at the same order of success. The 2D
   constant should be revisited against bench data, not silently changed.
   (Engine gap found on the way: MuJoCo 3.10 computes the virtual-mass
   coefficient but never applies the linear acceleration-reaction force —
   verified with a sphere in density-1000 fluid accelerating at F/m. The
   rig applies the reaction force itself using the engine's own
   coefficient; see `sim3d/world.py`.)
4. **The pendulum is faster than the 2D constant.** First-principles
   period 1.40 s (buoyancy-at-center vs COM 78 mm below, engine-computed
   inertia) vs the 2.2 s the 2D sim assumes. Consequence measured above:
   the swing damper is rate-marginal at 10 Hz. The 2D `swing_period_s`
   came from a research estimate of added-mass stretching; the bench
   (hang the real gondola, shove it) settles this in one afternoon.

## What this does and does not validate

- VALIDATED: the five SectionG behaviors reproduce in an independent
  engine (added mass/coasting, both-sign buoyancy drift, per-motor thrust
  saturation, funnel + two-signal magnet capture, few-gf drafts), and the
  2D sim's failure diagnosis (lateral authority vs drafts) is not an
  artifact of our own physics code.
- NOT VALIDATED: absolute success rates. MuJoCo halves the 2D numbers,
  mostly through the deeper funnel's slide gates and the true contact
  dynamics. Neither engine is the truth — the Phase-9 bench is.
- The Phase-6 gate (>95% first-attempt) remains NOT MET in both engines.
  The next lever is unchanged: a short-horizon trajectory planner with a
  draft estimator, now with two engines to prove it in.

## Reproduce

```bash
make physics3d          # full experiment + plots (about 15 min on an M-class Mac)
uv run --group physics3d pytest tests/sim3d   # rig behavior tests (~1 s)
```
