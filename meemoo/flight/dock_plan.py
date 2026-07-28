"""Short-horizon approach planning: the commit decision.

A deterministic judge the docking state machine consults each tick (its
sibling, the in-funnel :class:`~meemoo.flight.dock_slide.SlideMonitor`,
lives next door). Both exist because the measured failures (docs/PHYSICS_VALIDATION.md) were not
"the vehicle could not fly there" — they were *the controller threw away
approaches it was winning*.

The last metre is planned, not reacted to. It
carries the state forward to the mouth plane over a short horizon (time to
the mouth at the current closing speed, plus what the estimated draft will
do over that time), and uses the answer to decide ONE thing: commit through
the mouth now, or hold range on the corridor until the cross-error window
opens. Holding costs seconds; a go-around costs an attempt and ~25 s of
retreat, which is why 341/506 aborts (2D/MuJoCo) fired inside 30 cm of the
mouth with a 5-15 cm error — recoverable states, thrown away.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from meemoo.flight.constants import GF_TO_N, DockConfig, PhysicsConfig

if TYPE_CHECKING:
    from meemoo.flight.docking import _AxisErrors


@dataclass(frozen=True, slots=True)
class ApproachPlan:
    """What the planner wants this tick."""

    v_des: float  # commanded closing speed (m/s)
    hold: bool  # station-keep on the corridor instead of closing
    hold_r_m: float  # nose range to hold at while waiting
    committed: bool
    predicted_miss_m: float
    replanned: bool = False  # this tick gave up a commit and went back to hold
    abort: str | None = None  # go around: re-planning cannot help


class ApproachPlanner:
    """Receding-horizon commit judge for FINAL_APPROACH.

    The test is a FEASIBILITY test, not a ballistic one. A ballistic
    extrapolation reads a healthy damped convergence as an overshoot (that
    was the v1 mouth gate, and it aborted 341/506 recoverable approaches).
    What actually matters is whether the lateral authority the airframe has
    can null the cross error in the time left before the mouth plane, with
    the estimated draft eating its share:

        a_req = 2·|l + v_l·T| / T²      (constant-accel null at the mouth)
        a_res = residual draft accel the crab feedforward will not cancel
        commit iff  a_req + a_res < margin · a_lat_max

    a_lat_max is honest: forward thrust times the sine of the largest crab
    the nose can hold, over the effective (added-mass) mass. Roughly
    0.09 m/s² — the same order as the draft itself, which is exactly why
    the timing of the commit is the whole game (research/06 §G.5).
    """

    def __init__(
        self,
        phys_cfg: PhysicsConfig,
        dock_cfg: DockConfig,
        *,
        gate_r_m: float = 0.62,
        max_commits: int = 10,
        lat_authority_gf: float = 8.0,  # peak crab force the mixer delivers
        commit_margin: float = 0.65,
        wave_off_margin: float = 1.0,
    ) -> None:
        self.phys_cfg = phys_cfg
        self.dock_cfg = dock_cfg
        self.gate_r_m = gate_r_m
        self.max_commits = max_commits
        self.a_lat_max = lat_authority_gf * GF_TO_N / phys_cfg.effective_mass_kg
        self.commit_margin = commit_margin
        self.wave_off_margin = wave_off_margin
        self.commit_vlat = 0.12  # not flying sideways
        self.commit_lat_m = 0.35  # not on a wholly different line
        self.commits = 0
        self._l_f = 0.0
        self._vl_f = 0.0
        self._pm_f = 0.0
        self._committed = False
        self._hold_r = gate_r_m
        self._seeded = False

    def reset(self, *, keep_commits: bool = False) -> None:
        self._committed = False
        self._seeded = False
        self._hold_r = self.gate_r_m
        if not keep_commits:
            self.commits = 0

    def _demand(
        self, err: _AxisErrors, draft_lat_gf: float, v_des: float
    ) -> tuple[float, float]:
        """(required lateral accel, predicted ballistic miss) at the mouth."""
        # horizon at the speed we will actually commit at — using the CURRENT
        # closing speed while holding station gives an infinite horizon and
        # the window never opens
        v_ref = max(err.v_axis_mps, 0.6 * v_des)
        t_go = min(8.0, max(0.5, max(0.0, err.range_m) / v_ref))
        drift = self._l_f + self._vl_f * t_go
        a_req = 2.0 * abs(drift) / (t_go * t_go)
        # Holding the crab against the draft costs lateral authority whether
        # or not the estimator is confident — the wind does not care. Scaling
        # this by (1 − confidence) made a MuJoCo approach with a 5 gf draft
        # and a jittery estimate permanently "infeasible": it never committed
        # once, spent its commit budget holding, and went around.
        a_wind = abs(draft_lat_gf) * GF_TO_N / self.phys_cfg.effective_mass_kg
        return a_req + a_wind, drift

    def update(
        self,
        err: _AxisErrors,
        draft_lat_gf: float,
        dt: float,
        *,
        force_hold: bool = False,
    ) -> ApproachPlan:
        """Plan one tick from the nose state and the draft estimate.

        ``draft_lat_gf`` is taken at face value on purpose — the estimator's
        confidence scales the FEEDFORWARD (docking_laws), but the authority
        the wind consumes is not a matter of how sure we are about it."""
        if not self._seeded:
            self._l_f, self._vl_f = err.lateral_m, err.v_lat_mps
            self._seeded = True
        a = min(1.0, dt / 0.25)
        self._l_f += (err.lateral_m - self._l_f) * a
        self._vl_f += (err.v_lat_mps - self._vl_f) * a
        # Arrival speed is a CAPTURE constraint, not a comfort setting: the
        # funnel rejects contact above v_max_capture, and the v1 profile
        # equilibrated ABOVE it (measured contact speeds 0.21-0.39 m/s
        # against a 0.15 m/s limit — "too_fast" rejections the controller
        # never even saw). Plan the leg at 0.55-0.85 of the limit and spend
        # the extra seconds on cross error: a_req falls as 1/T².
        v_cap = self.dock_cfg.v_max_capture_mps
        v_des = min(0.85 * v_cap, max(0.55 * v_cap,
                                      0.6 * v_cap + 0.10 * (err.range_m - 0.35)))
        demand, drift = self._demand(err, draft_lat_gf, v_des)
        self._pm_f += (drift - self._pm_f) * a

        def plan(**kw: object) -> ApproachPlan:
            base: dict[str, object] = {
                "v_des": v_des, "hold": False, "hold_r_m": self._hold_r,
                "committed": self._committed, "predicted_miss_m": self._pm_f,
            }
            base.update(kw)
            return ApproachPlan(**base)  # type: ignore[arg-type]

        if err.range_m > self.gate_r_m and not force_hold:
            # cruise: converge out here, where a metre of range buys seconds
            # of lateral authority. No commit decision this far out.
            self._committed = False
            return plan()
        if not self._committed:
            if self.commits >= self.max_commits:
                # the line has been re-planned as often as an attempt is
                # worth; hand the retry counter its go-around
                return plan(abort="commit_window", hold=True)
            ready = (
                err.fresh
                and not force_hold
                and demand < self.commit_margin * self.a_lat_max
                and abs(self._vl_f) < self.commit_vlat
                and abs(self._l_f) < self.commit_lat_m
                # never commit already too fast to be captured
                and err.v_axis_mps < 0.9 * self.dock_cfg.v_max_capture_mps
            )
            if not ready:
                self._hold_r = min(self.gate_r_m, max(0.30, err.range_m))
                return plan(hold=True, hold_r_m=self._hold_r)
            self._committed = True
            self.commits += 1
        # committed: fly the last leg, and wave off (NOT a go-around) if the
        # correction stops fitting inside the authority while there is still
        # room to fix it
        if err.range_m > 0.10 and demand > self.wave_off_margin * self.a_lat_max:
            self._committed = False
            self._hold_r = min(self.gate_r_m, max(0.30, err.range_m))
            if self.commits >= self.max_commits:
                return plan(abort="commit_window", hold=True)
            return plan(hold=True, hold_r_m=self._hold_r, replanned=True,
                        committed=False)
        return plan(committed=True)
