"""In-funnel slide monitoring — the gates that decide a capture is lost.

Inside the cone the dock camera is blind by construction (it looks OUT along
the approach corridor), so range and lateral come from a σ-5 cm room pose
swung through a 0.3-0.6 m nose boom. Judging a multi-second slide on single
samples of THAT is what threw away 209 MuJoCo approaches, 35 of them within
5 cm of the magnet, in the v1 measurement (docs/PHYSICS_VALIDATION.md).

The rules, in order:

1. contact telemetry outranks dead reckoning;
2. never abort while the range to the magnet is still shrinking;
3. a retreat must be SUSTAINED and must have actually undone progress;
4. a funnel narrows, so |lateral| can only shrink once inside — if it grows
   we are not in a cone, we are leaning on the rim beside the mouth;
5. a stalled slide gets PUSHED harder before it is abandoned, and when it is
   abandoned it goes back to the planner, not back to the standoff.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from meemoo.flight.types import CaptureTelemetry

if TYPE_CHECKING:
    from meemoo.flight.docking import _AxisErrors


@dataclass(frozen=True, slots=True)
class SlideVerdict:
    """What to do while the nose is in the cone."""

    hold_thrust: bool  # floor forward thrust: held thrust is what slides us in
    vertical_m: float  # filtered vertical error (raw is σ-5 cm dead reckoning)
    push_gf: float = 6.0  # slide thrust, escalated when the nose stops moving
    abort: str | None = None
    back_to_approach: bool = False  # bounced clear: re-plan, don't retreat


class SlideMonitor:
    """In-funnel gate logic — the fix for 209 thrown-away captures.

    The hard part is that nothing in the telemetry says "you are in the
    cone" until the charge rings touch. What IS observable: inside the cone
    the wall constrains the nose (dead-reckoned lateral collapses toward the
    axis) and the range keeps shrinking; pressed against the rim after a
    rejected contact it does not. So progress, not a clock, decides — with a
    stall test so that pushing 8 gf into a rim we never entered ends in a
    re-plan after ~3 s instead of a 25 s timeout.
    """

    def __init__(
        self, *, retreat_s: float = 0.6, bypass_s: float = 0.8, stall_s: float = 5.0
    ) -> None:
        self.retreat_s = retreat_s
        self.bypass_s = bypass_s
        self.stall_s = stall_s
        self.r_f = 0.0
        self.r_min = 0.0
        self.v_f = 0.0
        self.l_f = 0.0
        self.z_f = 0.0
        self.contact = False
        self.holding = False
        self.l_ref = 0.0
        self._retreat_t = 0.0
        self._bypass_t = 0.0
        self._stall_t = 0.0
        self._diverge_t = 0.0
        self.push_gf = 6.0

    def reset(self, err: _AxisErrors) -> None:
        self.r_f = self.r_min = err.range_m
        self.v_f = err.v_axis_mps
        self.l_f = err.lateral_m
        self.z_f = err.vertical_m
        self.l_ref = abs(err.lateral_m)
        self.contact = False
        self.holding = False
        self._retreat_t = self._bypass_t = self._stall_t = 0.0
        self._diverge_t = 0.0
        self.push_gf = 6.0

    def update(
        self, err: _AxisErrors, capture: CaptureTelemetry, dt: float
    ) -> SlideVerdict:
        a = min(1.0, dt / 0.5)
        self.r_f += (err.range_m - self.r_f) * a
        self.v_f += (err.v_axis_mps - self.v_f) * min(1.0, dt / 0.35)
        self.l_f += (err.lateral_m - self.l_f) * a
        self.z_f += (err.vertical_m - self.z_f) * a
        self.contact = self.contact or capture.contact_continuity or (
            capture.retention_engaged
        )
        # Progress = the filtered range to the magnet reaching a new low.
        # The ratchet must hold its old low to compare against: updating
        # r_min every tick makes "a new low" mean "a new low THIS TICK",
        # which a 0.01-0.06 m/s slide never manages — and then a healthy
        # 5-second slide reads as a stall and gets thrown away one funnel
        # depth from the magnet. 1 cm is ~1 sigma of the filtered dead
        # reckoning; being generous here errs toward holding thrust, which
        # is the direction that captures.
        progressing = self.r_f < self.r_min - 0.01
        if progressing:
            self.r_min = self.r_f
        # THE cone-evidence test, and it needs no cone geometry: a funnel
        # narrows, so once the nose is inside, |lateral| can only shrink. If
        # it grows instead we are not in a cone — we are pressing 8 gf past
        # the mouth rim beside the dock, which is how the v2 first cut sailed
        # through the dock face 256 times.
        self.l_ref = min(self.l_ref, abs(self.l_f))
        diverging = abs(self.l_f) > self.l_ref + 0.08 and not self.contact
        self._diverge_t = self._diverge_t + dt if diverging else 0.0
        if self._diverge_t > 0.5:
            return SlideVerdict(False, self.z_f, back_to_approach=True)
        # hold the slide thrust from the moment we are at/inside the mouth,
        # and LATCH it: dropping below min_slide_thrust mid-slide stalls the
        # nose and walks it back out (research/06 §B.1), and a dead-reckoned
        # range that flickers 5 cm must never be what drops it.
        # The latch has to be FAST: funnel entry starts with ~2% of progress
        # and a stalled nose loses it in about a second (§B.1 back-out), so a
        # half-second filter lag is the difference between sliding in and
        # sliding back out. A raw sample under 2 cm is a 2-sigma event on
        # σ-5 cm dead reckoning and the latch is sticky, so one hit is
        # enough; the divergence/stall/retreat tests below unlatch it.
        if self.contact or self.r_f < 0.05 or err.range_m < 0.02:
            self.holding = True
        # A stalled slide gets PUSHED before it is abandoned: held thrust is
        # what substitutes for gravity in a funnel (research/06 §B.1), and a
        # tip stuck in the throat's centering cup 2-7 cm from the magnet is
        # asking for more of it, not for a go-around. Escalate toward
        # saturation, and drop straight back the moment the nose moves.
        self.push_gf = min(12.0, 6.0 + 2.0 * self._stall_t)
        # 1. contact telemetry outranks dead reckoning; 2. never abort while
        # the range to the magnet is still shrinking
        if self.contact or progressing:
            self._retreat_t = self._bypass_t = self._stall_t = 0.0
            self.push_gf = 6.0
            return SlideVerdict(self.holding, self.z_f, self.push_gf)
        # 3. a retreat must be SUSTAINED and must have undone real progress
        self._retreat_t = self._retreat_t + dt if self.v_f < -0.05 else 0.0
        if self._retreat_t > self.retreat_s and self.r_f > self.r_min + 0.12:
            return SlideVerdict(False, self.z_f, back_to_approach=True)
        # sailed past BESIDE the dock: deep past the mouth plane, far off
        # axis, never any contact. On filtered signals this needs a real
        # miss, not a noise sample.
        beside = self.r_f < -0.30 and abs(self.l_f) > 0.25
        self._bypass_t = self._bypass_t + dt if beside else 0.0
        if self._bypass_t > self.bypass_s:
            return SlideVerdict(False, self.z_f, abort="slide_bypass")
        # Not sliding and not retreating: we are leaning on a rim we never
        # entered (a rejected contact) or parked short of the mouth. Once the
        # escalating push has had its window, re-plan the line — and do it
        # WITHOUT spending an attempt. (The clock runs whether or not the
        # thrust floor latched: a nose parked 5 cm short is just as stuck.)
        self._stall_t += dt
        if self._stall_t > self.stall_s:
            return SlideVerdict(False, self.z_f, back_to_approach=True)
        return SlideVerdict(self.holding, self.z_f, self.push_gf)
