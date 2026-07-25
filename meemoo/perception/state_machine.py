"""Fall state machine — persistence-primary (research 05 §A.4, implemented exactly).

Trigger structure is `persistence OR (transition AND persistence)`, NEVER
`transition AND persistence`: descent velocity is a precision tool; persistence
is the recall engine. Parallel LONG_LIE and VANISHED_DOWN paths remove the
"we never saw the descent" miss class — the class that contains the
catastrophic failures.

Pure module: consumes SignalFrames, emits events through a callback. No
camera, no bus, no LLM — deterministic and fully testable (Art. IV §4, IX §2).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from enum import Enum

from meemoo.core.logging import escalation_extra
from meemoo.perception.suppression import GroundedClass, GroundedContext, classify_grounded
from meemoo.perception.thresholds import Thresholds
from meemoo.perception.trackers import EpisodeTrackers
from meemoo.perception.types import RestZoneOracle, SignalFrame

logger = logging.getLogger(__name__)

EventCallback = Callable[[str, dict[str, object]], None]

_ABSENT_GRACE_S = 5.0


class FallState(Enum):
    UPRIGHT = "UPRIGHT"
    DESCENDING = "DESCENDING"
    SUPPRESSED = "SUPPRESSED_FURNITURE"
    GROUNDED_CANDIDATE = "GROUNDED_CANDIDATE"
    VERIFYING = "VERIFYING"
    ESCALATE = "ESCALATE"
    SNOOZED = "SNOOZED"  # voice-verified fine while still on the floor
    ABSENT = "ABSENT"


_CANDIDATE_PATH = frozenset(
    {FallState.GROUNDED_CANDIDATE, FallState.VERIFYING, FallState.ESCALATE}
)


class FallStateMachine:
    """One person's fall state. Feed time-ordered SignalFrames via tick()."""

    def __init__(
        self,
        thresholds: Thresholds,
        zones: RestZoneOracle,
        on_event: EventCallback,
        habitual_rest_time: Callable[[float], bool] | None = None,
        learning: Callable[[], bool] | None = None,
    ) -> None:
        self.th = thresholds
        self.zones = zones
        self._on_event = on_event
        self._habitual = habitual_rest_time or (lambda _t: False)
        self._learning = learning or (lambda: False)
        self.state = FallState.UPRIGHT
        self.flags: dict[str, object] = {}
        self.near_misses: list[dict[str, object]] = []
        self.transitions: list[tuple[float, str, str]] = []
        self.trk = EpisodeTrackers(thresholds)
        self._upright_since: float | None = None
        self._grounded_at = 0.0
        self._soft = False
        self._candidate_emitted = False
        self._down_at = 0.0
        self._prompts_sent = 0
        self._absent_since: float | None = None
        self._snooze_until = 0.0
        self._last_present: SignalFrame | None = None

    # ------------------------------------------------------------------ external
    def notify_voice_ok(self, t: float) -> None:
        """Voice verification succeeded ('I'm fine'). Downgrades, snoozes."""
        if self.state in (FallState.VERIFYING, FallState.GROUNDED_CANDIDATE):
            self._emit("person.recovered", {"t": t, "reason": "voice_ok"})
            self._snooze_until = t + self.th.furniture_still_escape_s
            self._to(FallState.SNOOZED, t)

    def notify_voice_help(self, t: float) -> None:
        """Distress word during verification — escalate immediately."""
        if self.state in (FallState.GROUNDED_CANDIDATE, FallState.VERIFYING):
            self._escalate(t, "voice_help")

    def reset(self) -> None:
        self._to(FallState.UPRIGHT, self._last_present.t if self._last_present else 0.0)
        self._candidate_emitted = False
        self.flags = {}

    # ---------------------------------------------------------------------- tick
    def tick(self, sig: SignalFrame) -> FallState:
        if not sig.present:
            self._tick_absent(sig)
            return self.state
        self._absent_since = None
        if self.state == FallState.ABSENT:
            self._to(FallState.UPRIGHT, sig.t)
        self._last_present = sig
        self.trk.update(sig)

        if self._check_recovery(sig):
            return self.state
        self._check_long_lie(sig)

        if self.state == FallState.UPRIGHT:
            if self._is_low_or_horizontal(sig):
                self._to(FallState.DESCENDING, sig.t)
        elif self.state == FallState.DESCENDING:
            self._tick_descending(sig)
        elif self.state == FallState.SUPPRESSED:
            self._tick_suppressed(sig)
        elif self.state == FallState.GROUNDED_CANDIDATE:
            self._tick_grounded(sig)
        elif self.state == FallState.VERIFYING:
            self._advance_verify_timers(sig.t)
        elif self.state == FallState.SNOOZED:
            self._tick_snoozed(sig)
        return self.state

    # ------------------------------------------------------------------ internals
    def _is_low_or_horizontal(self, sig: SignalFrame) -> bool:
        return (
            sig.torso_angle > self.th.horizontal_angle_deg
            or sig.elevation < self.th.near_floor_elevation
        )

    def _check_recovery(self, sig: SignalFrame) -> bool:
        upright = (
            sig.torso_angle < self.th.upright_max_angle_deg
            and sig.elevation > self.th.recovered_min_elevation
        )
        if not upright:
            self._upright_since = None
            return False
        self._upright_since = self._upright_since or sig.t
        if sig.t - self._upright_since < self.th.t_recovered:
            return False
        if self.state in (FallState.UPRIGHT, FallState.ABSENT):
            return False
        # person.recovered only matters downstream if a candidate/down event
        # actually fired; a 20 s floor-sit that never hit a timer exits silently.
        if self.state in _CANDIDATE_PATH and self._candidate_emitted:
            self.near_misses.append(
                {"t": sig.t, "state": self.state.value, "flags": dict(self.flags)}
            )
            self._emit("person.recovered", {"t": sig.t, "reason": "stood_up"})
        self._to(FallState.UPRIGHT, sig.t)
        self._candidate_emitted = False
        self.flags = {}
        return True

    def _check_long_lie(self, sig: SignalFrame) -> None:
        posture_ok = self._is_low_or_horizontal(sig) and not self.zones.is_rest_zone(
            sig.x, sig.support_y
        )
        duration = self.trk.longlie_duration(sig, posture_ok)
        eligible = (FallState.UPRIGHT, FallState.DESCENDING, FallState.SUPPRESSED)
        if self.state in eligible and duration >= self.th.t_longlie:
            self._enter_grounded(sig.t, sig.t, soft=False, flag="longlie")

    def _classify(self, sig: SignalFrame, slid: bool) -> GroundedClass:
        ctx = GroundedContext(
            x=sig.x,
            support_y=sig.support_y,
            elevation=sig.elevation,
            v_peak=self.trk.v_peak(sig.t),
            hip_drop_0_8s=self.trk.hip_drop(sig.t),
            motion_energy=sig.motion_energy,
            still_duration=self.trk.still_duration(sig.t),
            slid_toward_floor=slid,
            habitual_rest_time=self._habitual(sig.t),
        )
        return classify_grounded(ctx, self.zones, self.th)

    def _tick_descending(self, sig: SignalFrame) -> None:
        settle = self.trk.settle_since
        if settle is None or sig.t - settle < self.th.t_settle:
            return
        verdict = self._classify(sig, slid=False)
        if verdict == "CANDIDATE":  # backdate grounding to when stillness began
            self._enter_grounded(sig.t, settle, soft=False, flag="fall")
        elif verdict == "CANDIDATE_SOFT":
            self._enter_grounded(sig.t, settle, soft=True, flag="controlled_descent")
        elif verdict == "SUPPRESSED_FURNITURE":
            self._to(FallState.SUPPRESSED, sig.t)
        # MONITOR: stay in DESCENDING; recovery or LONG_LIE will resolve it

    def _tick_suppressed(self, sig: SignalFrame) -> None:
        slid = sig.elevation < self.th.near_floor_elevation
        if self._classify(sig, slid=slid) == "CANDIDATE":
            flag = "slid_toward_floor" if slid else "furniture_escape"
            self._enter_grounded(sig.t, sig.t, soft=False, flag=flag)

    def _enter_grounded(self, now: float, grounded_at: float, soft: bool, flag: str) -> None:
        ballistic = (
            self.trk.v_peak(now) > self.th.ballistic_v
            or self.trk.hip_drop(now) > self.th.ballistic_drop
        )
        learning = self._learning()
        if learning and not ballistic:
            soft = True  # reduced sensitivity during the learning phase
        self.flags = {"cause": flag, "ballistic": ballistic, "learning": learning}
        self._grounded_at = grounded_at
        self._soft = soft
        self._candidate_emitted = False
        self._to(FallState.GROUNDED_CANDIDATE, grounded_at)

    def _tick_grounded(self, sig: SignalFrame) -> None:
        if self._soft and sig.motion_energy > self.th.purposeful_motion:
            self._grounded_at = sig.t  # purposeful floor-sitter: restart timer
            return
        self._advance_grounded_timers(sig.t)

    def _advance_grounded_timers(self, now: float) -> None:
        cand_t = self.th.t_soft_candidate if self._soft else self.th.t_candidate
        conf_t = self.th.t_soft_confirm if self._soft else self.th.t_confirm
        payload = {"grounded_at": self._grounded_at, "soft": self._soft, **self.flags}
        if not self._candidate_emitted and now - self._grounded_at >= cand_t:
            self._candidate_emitted = True
            self._emit("candidate.fall", {"t": now, **payload})
        if self._candidate_emitted and now - self._grounded_at >= conf_t:
            self._down_at = now
            self._prompts_sent = 0
            logger.warning(
                "person.down confirmed",
                extra=escalation_extra(grounded_at=self._grounded_at, **self.flags),
            )
            self._emit("person.down", {"t": now, **payload})
            self._to(FallState.VERIFYING, now)

    def _advance_verify_timers(self, now: float) -> None:
        for n, offset in ((1, self.th.t_voice_1), (2, self.th.t_voice_2)):
            if self._prompts_sent < n and now - self._down_at >= offset:
                self._prompts_sent = n
                self._emit("verify.voice_prompt", {"t": now, "n": n})
        if now - self._grounded_at >= self.th.t_escalate:
            self._escalate(now, "no_response")

    def _tick_snoozed(self, sig: SignalFrame) -> None:
        ballistic = self.trk.v_peak(sig.t, window=1.5) > self.th.ballistic_v
        if ballistic:  # a NEW fall while snoozed is never suppressed
            self._enter_grounded(sig.t, sig.t, soft=False, flag="fall_while_snoozed")
        elif sig.t >= self._snooze_until:
            self._to(FallState.UPRIGHT, sig.t)

    def _escalate(self, now: float, reason: str) -> None:
        if self.state == FallState.ESCALATE:
            return
        logger.error(
            "fall escalation requested",
            extra=escalation_extra(reason=reason, grounded_at=self._grounded_at),
        )
        self._emit("escalate.requested", {"t": now, "reason": reason} | dict(self.flags))
        self._to(FallState.ESCALATE, now)

    def _tick_absent(self, sig: SignalFrame) -> None:
        last = self._last_present
        if self.state in _CANDIDATE_PATH:
            # occluded-while-down is evidence FOR, never against: timers run on
            if self.state == FallState.GROUNDED_CANDIDATE:
                self._advance_grounded_timers(sig.t)
            elif self.state == FallState.VERIFYING:
                self._advance_verify_timers(sig.t)
            return
        if last is not None and self._absent_since is None:
            self._absent_since = sig.t
            vanished = (
                self.trk.v_peak(sig.t, window=self.th.vanish_v_window_s)
                > self.th.ballistic_v
                and last.support_y > self.th.vanish_bottom_y
            )
            if vanished and self.state in (FallState.UPRIGHT, FallState.DESCENDING):
                self._enter_grounded(sig.t, sig.t, soft=False, flag="vanished_down")
                return
        if (
            self._absent_since is not None
            and sig.t - self._absent_since > _ABSENT_GRACE_S
            and self.state != FallState.ABSENT
        ):
            self._to(FallState.ABSENT, sig.t)

    def _to(self, state: FallState, t: float) -> None:
        if state is self.state:
            return
        self.transitions.append((t, self.state.value, state.value))
        logger.info(
            "fall state %s -> %s", self.state.value, state.value, extra={"fields": {"t": t}}
        )
        self.state = state

    def _emit(self, name: str, payload: dict[str, object]) -> None:
        self._on_event(name, payload)
