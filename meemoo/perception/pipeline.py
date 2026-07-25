"""Perception pipeline: three-tier duty cycle wiring camera → bus events.

Research 05 §F.3:
  IDLE      motion gate only (3 fps, tiny grayscale frame-diff)
  ACTIVE    person present/moving: pose at 15 fps → signals → state machine
  TRACKING  candidate fall in progress: pose held at 15 fps, evidence recorded

The §F.3 subtlety is LAW here: the motion gate is never the only path in.
Once a person has been seen, pose keeps running until they are confirmed
upright-and-gone (absence timeout) — a fallen person generates no motion, and
the gate must not blind the system to exactly the state it is hunting.
"""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from pathlib import Path
from typing import Any

from meemoo.core import topics
from meemoo.core.bus import EventBus
from meemoo.core.config import Settings
from meemoo.core.versioning import set_version
from meemoo.perception.calibration import CalibrationState
from meemoo.perception.motion import MotionGate
from meemoo.perception.pose import PoseEstimator
from meemoo.perception.ring_buffer import SkeletonRingBuffer
from meemoo.perception.signals import SignalExtractor
from meemoo.perception.state_machine import FallState, FallStateMachine
from meemoo.perception.thresholds import Thresholds, load_thresholds
from meemoo.perception.types import PoseFrame
from meemoo.perception.video import VideoSource, to_gate_gray

logger = logging.getLogger(__name__)

IDLE_FPS = 3.0
ACTIVE_FPS = 15.0
ABSENT_TIMEOUT_S = 30.0

_BUS_TOPICS = {
    "candidate.fall": topics.CANDIDATE_FALL,
    "person.down": topics.PERSON_DOWN,
    "person.recovered": topics.PERSON_RECOVERED,
}


class Tier(Enum):
    IDLE = "IDLE"
    ACTIVE = "ACTIVE"
    TRACKING = "TRACKING"


def next_tier(
    current: Tier,
    *,
    person_visible: bool,
    in_candidate_path: bool,
    motion_hit: bool,
    absent_for: float,
    absent_timeout: float = ABSENT_TIMEOUT_S,
) -> Tier:
    """Pure tier-transition rule. The never-drop-a-seen-person rule lives here."""
    if in_candidate_path:
        return Tier.TRACKING  # candidate in progress: NOTHING demotes us
    if current is Tier.IDLE:
        return Tier.ACTIVE if motion_hit else Tier.IDLE
    if person_visible:
        return Tier.ACTIVE
    # person not visible: only confirmed-gone (timeout) may drop to IDLE
    if absent_for >= absent_timeout:
        return Tier.IDLE
    return current if current is not Tier.TRACKING else Tier.ACTIVE


class FrameHub:
    """Holds the latest annotated JPEG for the (step 07) /ws/video endpoint."""

    def __init__(self) -> None:
        self.seq = 0
        self.latest_jpeg: bytes | None = None
        self._changed = asyncio.Event()

    def set_frame(self, jpeg: bytes) -> None:
        self.latest_jpeg = jpeg
        self.seq += 1
        self._changed.set()
        self._changed.clear()

    async def wait_frame(self) -> bytes | None:
        await self._changed.wait()
        return self.latest_jpeg


class PerceptionPipeline:
    """Owns the perception loop for one camera / one room."""

    def __init__(
        self,
        bus: EventBus,
        settings: Settings,
        source: VideoSource,
        pose: PoseEstimator,
        calibration: CalibrationState | None = None,
        thresholds: Thresholds | None = None,
        events_dir: Path = Path("data/events"),
    ) -> None:
        self.bus = bus
        self.settings = settings
        self.source = source
        self.pose = pose
        self.calibration = calibration or CalibrationState()
        self.th = thresholds or load_thresholds()
        set_version("threshold", self.th.version)
        self.events_dir = events_dir
        self.hub = FrameHub()
        self.tier = Tier.IDLE
        self.gate = MotionGate()
        self.extractor = SignalExtractor(self.calibration.floor)
        self.ring = SkeletonRingBuffer()
        self._pending: list[tuple[str, dict[str, object]]] = []
        self.machine = FallStateMachine(
            self.th,
            self.calibration.zones,
            on_event=lambda name, payload: self._pending.append((name, payload)),
            learning=self.calibration.in_learning,
        )
        self._t0 = time.monotonic()
        self._last_seen: float | None = None  # sig.t of last present frame
        self._last_sig_t: float | None = None  # sig.t of last pose frame processed
        self._person_visible = False
        self._running = False

    # ------------------------------------------------------------------ main loop
    async def run(self) -> None:
        """Read frames until the source is exhausted or stop() is called."""
        self._running = True
        logger.info(
            "perception pipeline starting",
            extra={"fields": self.calibration.status_fields()},
        )
        try:
            while self._running:
                frame = self.source.read()
                if frame is None:
                    logger.info("video source exhausted; pipeline stopping")
                    break
                await self.step(frame)
                await asyncio.sleep(1.0 / (IDLE_FPS if self.tier is Tier.IDLE else ACTIVE_FPS))
        finally:
            self._running = False
            self.source.close()
            self.pose.close()

    def stop(self) -> None:
        self._running = False

    async def step(self, frame_bgr: Any) -> None:
        """Process one frame according to the current tier."""
        now = time.monotonic() - self._t0
        motion_hit = False
        if self.tier is Tier.IDLE:
            motion_hit = self.gate.triggered(to_gate_gray(frame_bgr))
            pose_frame: PoseFrame | None = None
        else:
            pose_frame = self.pose.infer(frame_bgr, now)
            await self._process_pose(pose_frame, frame_bgr)

        # absence is measured on the SIGNAL timeline (sig.t), which equals wall
        # time for live sources and clip time for playback — never mix the two
        ref_t = self._last_sig_t if self._last_sig_t is not None else now
        absent_for = (ref_t - self._last_seen) if self._last_seen is not None else 1e9
        new_tier = next_tier(
            self.tier,
            person_visible=self._person_visible,
            in_candidate_path=self.machine.state
            in (FallState.GROUNDED_CANDIDATE, FallState.VERIFYING, FallState.ESCALATE),
            motion_hit=motion_hit,
            absent_for=absent_for,
        )
        if new_tier is not self.tier:
            logger.info("perception tier %s -> %s", self.tier.value, new_tier.value)
            if new_tier is Tier.IDLE:
                self.gate.reset()
                self.extractor.reset_motion_history()
            self.tier = new_tier

    # ------------------------------------------------------------------ internals
    async def _process_pose(self, pose_frame: PoseFrame, frame_bgr: Any) -> None:
        sig = self.extractor.update(pose_frame)
        self._last_sig_t = sig.t
        was_visible = self._person_visible
        self._person_visible = sig.present
        if sig.present:
            self._last_seen = sig.t
            self.ring.append(pose_frame)
            self.calibration.observe(sig, pose_frame.landmarks)
            if not was_visible:
                await self.bus.publish(
                    topics.PERSON_DETECTED, {"t": sig.t, "x": sig.x}
                )
        self.machine.tick(sig)
        await self._flush_events(frame_bgr)
        self._annotate(frame_bgr, pose_frame)

    async def _flush_events(self, frame_bgr: Any) -> None:
        pending, self._pending = self._pending, []
        for name, payload in pending:
            if name == "candidate.fall":
                event_dir = self.ring.dump(
                    self.events_dir,
                    reason="candidate.fall",
                    extra_header={"payload": payload},
                    thumbnail_bgr=frame_bgr,
                )
                payload = dict(payload) | {"evidence_dir": str(event_dir)}
            topic = _BUS_TOPICS.get(name)
            if topic is not None:
                await self.bus.publish(topic, payload)
            else:
                # verify prompts / escalate requests: Guardian wiring is step 05
                logger.info(
                    "machine event %s", name, extra={"fields": dict(payload)}
                )

    def _annotate(self, frame_bgr: Any, pose_frame: PoseFrame) -> None:
        try:
            from meemoo.perception.annotate import annotate_frame, encode_jpeg

            annotated = annotate_frame(
                frame_bgr,
                pose_frame.landmarks,
                self.machine.state.value,
                extra_label=f"tier={self.tier.value}",
            )
            jpeg = encode_jpeg(annotated)
            if jpeg is not None:
                self.hub.set_frame(jpeg)
        except ImportError:
            pass  # headless/no-cv2 environments: annotation is optional polish
