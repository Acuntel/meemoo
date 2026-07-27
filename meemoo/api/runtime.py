"""AppRuntime — wires the whole product inside the API process.

``make dev`` starts uvicorn; the FastAPI lifespan starts this runtime: DB
migrations, event bus, the simulated blimp (real-time loop), the guardian
spine, the check-in scheduler, the voice pipeline (server mic/speaker when
present, honest degradation when not), and an event recorder that persists
every bus event to the append-only ``events`` table (Art. II §6).

Everything degrades: no mic → text mode, no TTS models → NullTTS, no API key
→ scripted brain, no Twilio → simulated notifier. Startup NEVER crashes on a
missing credential (Art. IX §3) — create_app wraps start() and falls back to
API-only mode if anything unexpected happens.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from meemoo.api.profile import build_brain, load_profile, pin_provider
from meemoo.core.bus import EventBus
from meemoo.core.bus_registry import set_active_bus, set_active_scheduler
from meemoo.core.config import Settings
from meemoo.core.db import get_engine, get_session_factory
from meemoo.core.migrate import upgrade
from meemoo.core.models import Event
from meemoo.core.topics import VOICE_SPEAKING
from meemoo.flight.registry import set_active_sim
from meemoo.flight.sim_blimp import SimulatedBlimp
from meemoo.guardian.notifier import make_notifier
from meemoo.guardian.registry import set_active_service
from meemoo.guardian.scheduler import CheckinScheduler
from meemoo.guardian.service import GuardianService
from meemoo.perception.pipeline import PerceptionPipeline
from meemoo.perception.registry import set_active_pipeline
from meemoo.voice.audio_io import BufferSource, create_mic, create_speaker
from meemoo.voice.pipeline import VoicePipeline
from meemoo.voice.session import SessionManager
from meemoo.voice.stt import create_stt
from meemoo.voice.tts import create_tts
from meemoo.voice.vad import create_vad

logger = logging.getLogger(__name__)

DbFactory = sessionmaker[DbSession]

#: Topics NOT persisted to the events table (high-churn UI plumbing only).
_UNRECORDED_TOPICS = frozenset({VOICE_SPEAKING})


class AppRuntime:
    """Owns the long-running tasks behind the API. One device (fleet-ready)."""

    def __init__(self, settings: Settings, *, device_id: int = 1) -> None:
        self._settings = settings
        self.device_id = device_id
        self.bus = EventBus()
        self.sim: SimulatedBlimp | None = None
        self.perception: PerceptionPipeline | None = None
        self.guardian: GuardianService | None = None
        self.scheduler: CheckinScheduler | None = None
        self.pipeline: VoicePipeline | None = None
        self._tasks: list[asyncio.Task[None]] = []
        self._started = False

    # ----------------------------------------------------------------- start
    async def start(self) -> None:
        """Bring everything up. Missing optional pieces degrade, never crash."""
        engine = get_engine()
        applied = upgrade(engine)
        if applied:
            logger.info("migrations applied", extra={"fields": {"revisions": applied}})
        db_factory = get_session_factory()
        self._seed_device(db_factory)
        set_active_bus(self.bus)

        # --- voice (server mic/speaker; text/null degradation is normal) ----
        profile = load_profile(db_factory, self.device_id)
        mic = create_mic()
        source = mic if mic is not None else BufferSource()
        sessions = SessionManager(
            self.bus, db_factory,
            silence_close_s=self._settings.voice_silence_close_s,
        )
        self.pipeline = VoicePipeline(
            self.bus,
            source=source,
            sink=create_speaker(),
            stt=create_stt(),
            tts=create_tts(),
            vad=create_vad(),
            sessions=sessions,
            brain=build_brain(db_factory, self.device_id),
            voice_key=profile.voice,
            device_id=self.device_id,
            pins=pin_provider(db_factory, self.device_id),
        )
        self._tasks.append(asyncio.create_task(self.pipeline.run()))
        self._tasks.append(asyncio.create_task(self._session_ticker(sessions)))

        # --- perception (camera → fall detection; absence is normal) --------
        self._try_start_perception()

        # --- flight sim (real-time loop publishing to the bus) --------------
        self.sim = SimulatedBlimp(self._settings.meemoo_plan, device_id=self.device_id)
        self._load_no_go_zones(db_factory)
        set_active_sim(self.sim)
        self._tasks.append(asyncio.create_task(self.sim.run(self.bus)))

        # --- guardian + scheduler ------------------------------------------
        self.guardian = GuardianService(
            self.bus, db_factory,
            device_id=self.device_id,
            notifier=make_notifier(self._settings, self.bus),
            speak=self.pipeline.speak,
            test_number=self._settings.guardian_test_number,
        )
        await self.guardian.start()
        set_active_service(self.guardian)
        self.scheduler = CheckinScheduler(self.bus, db_factory, device_id=self.device_id)
        self.scheduler.start()
        set_active_scheduler(self.scheduler)

        # --- flight recorder: every bus event → append-only events table ----
        self._tasks.append(asyncio.create_task(self._record_events(db_factory)))
        self._started = True
        logger.info(
            "runtime started",
            extra={"fields": {
                "device_id": self.device_id,
                "plan": self._settings.meemoo_plan,
                "mic": mic is not None,
            }},
        )

    def _try_start_perception(self) -> None:
        """Start camera perception when a source opens; degrade honestly.

        Headless dev has no cv2/webcam — that is the NORMAL case, logged at
        info, and /ws/video keeps answering ``ready: false``. Demo-script
        step 4 stays available headless via POST /api/v1/perception/replay.
        """
        if self._settings.video_source == "off":
            logger.info("perception disabled (VIDEO_SOURCE=off)")
            return
        try:
            from meemoo.perception.calibration import CalibrationState
            from meemoo.perception.pose import MediaPipePose
            from meemoo.perception.video import open_source

            source = open_source(self._settings)
            calibration = CalibrationState()
            # Dev floor prior (same as perception/demo.py): flat floor near the
            # frame bottom until the install flow calibrates properly.
            calibration.floor.a, calibration.floor.b = 0.0, 0.92
            calibration.floor.fitted = True
            self.perception = PerceptionPipeline(
                self.bus, self._settings, source, MediaPipePose(), calibration
            )
            set_active_pipeline(self.perception)
            self._tasks.append(asyncio.create_task(self.perception.run()))
            logger.info(
                "perception started (dev floor prior active — run install "
                "calibration for real use)",
                extra={"fields": {"source": self._settings.video_source}},
            )
        except Exception as exc:  # any failure = no camera; never crash startup
            self.perception = None
            logger.info(
                "camera perception unavailable — video stays ready:false",
                extra={"fields": {"reason": str(exc)}},
            )

    # ------------------------------------------------------------------ stop
    async def stop(self) -> None:
        if self.scheduler is not None:
            self.scheduler.stop()
        if self.guardian is not None:
            await self.guardian.stop()
        if self.perception is not None:
            self.perception.stop()
            set_active_pipeline(None)
            self.perception = None
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks = []
        set_active_service(None)
        set_active_sim(None)
        set_active_bus(None)
        set_active_scheduler(None)
        self._started = False
        logger.info("runtime stopped")

    @property
    def started(self) -> bool:
        return self._started

    # ---------------------------------------------------------------- pieces
    def _load_no_go_zones(self, db_factory: DbFactory) -> None:
        """Push stored off-limit zones into the sim at boot (Amendment A3)."""
        from meemoo.core.models import NoGoZoneRow
        from meemoo.flight.zones import Zone

        if self.sim is None:
            return
        with db_factory() as db:
            rows = (
                db.query(NoGoZoneRow)
                .filter(NoGoZoneRow.device_id == self.device_id)
                .all()
            )
            self.sim.set_no_go_zones([Zone(z.name, z.x, z.y, z.w, z.h) for z in rows])
        if rows:
            logger.info(
                "off-limit zones loaded", extra={"fields": {"count": len(rows)}}
            )

    def _seed_device(self, db_factory: DbFactory) -> None:
        """Ensure the device row exists so every FK has a home."""
        from meemoo.core.models import Device

        with db_factory() as db:
            if db.get(Device, self.device_id) is None:
                db.add(Device(id=self.device_id, name="Meemoo"))
                db.commit()
                logger.info("seeded default device", extra={"fields": {"id": self.device_id}})

    async def _session_ticker(self, sessions: SessionManager) -> None:
        """Silence-close + periodic AI re-disclosure (Art. V §5)."""
        while True:
            await asyncio.sleep(5.0)
            line = await sessions.tick()
            if line is not None and self.pipeline is not None:
                await self.pipeline.speak(line)

    async def _record_events(self, db_factory: DbFactory) -> None:
        sub = self.bus.subscribe("*", replay_last=False)
        try:
            async for event in sub:
                if event.topic in _UNRECORDED_TOPICS:
                    continue
                try:
                    with db_factory() as db:
                        db.add(Event(
                            device_id=self.device_id,
                            type=event.topic,
                            payload=dict(event.payload),
                        ))
                        db.commit()
                except Exception:
                    logger.exception(
                        "event record failed", extra={"fields": {"topic": event.topic}}
                    )
        finally:
            sub.close()
