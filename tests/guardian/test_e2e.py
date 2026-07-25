"""Step-05 gate, end to end: fake ``person.down`` → whale flies over (sim
stand-in) → two voice asks through the REAL voice pipeline (NullTTS timed
audio — hardware doesn't exist; the audio path is the real one) → no
response → L1 with the simulated notifier → dashboard-less ack via the REST
API → escalation halted."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import Session, sessionmaker

from meemoo.api.deps import get_db
from meemoo.api.guardian_routes import router
from meemoo.core import topics
from meemoo.core.bus import EventBus
from meemoo.core.models import Alert, AuditLog
from meemoo.guardian.machine import State
from meemoo.guardian.registry import set_active_service
from meemoo.voice.audio_io import BufferSource, CollectSink
from meemoo.voice.pipeline import VoicePipeline
from meemoo.voice.session import SessionManager
from meemoo.voice.tts import NullTTS
from meemoo.voice.vad import EnergyVAD
from tests.guardian.conftest import FakeClock, ServiceFactory, mstate


class SimWhale:
    """Phase-6 stand-in: answers every flight.dispatch with a waypoint reach."""

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._sub = bus.subscribe(topics.FLIGHT_DISPATCH, replay_last=False)
        self.flights: list[dict[str, object]] = []
        self._task: asyncio.Task[None] | None = None

    async def _run(self) -> None:
        async for event in self._sub:
            self.flights.append(event.payload)
            await self._bus.publish(
                topics.FLIGHT_WAYPOINT_REACHED,
                {"waypoint": "person", "reason": event.payload.get("reason")},
            )

    def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._sub.close()
        if self._task is not None:
            await self._task


@pytest.fixture
def api_app(db_factory: sessionmaker[Session]) -> Iterator[FastAPI]:
    app = FastAPI()
    app.include_router(router)

    def override() -> Iterator[Session]:
        with db_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override
    yield app
    set_active_service(None)


@pytest.fixture
async def api_client(api_app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=api_app), base_url="http://test"
    ) as client:
        yield client


async def test_fall_to_l1_to_api_ack_halts(
    bus: EventBus,
    db_factory: sessionmaker[Session],
    seeded: dict[str, int],
    clock: FakeClock,
    make_service: ServiceFactory,
    api_client: AsyncClient,
) -> None:
    device_id = seeded["device_id"]

    # REAL voice pipeline: NullTTS renders timed audio into a collecting sink.
    sink = CollectSink()
    sessions = SessionManager(bus, db_factory, clock=clock)
    pipeline = VoicePipeline(
        bus,
        source=BufferSource(),
        sink=sink,
        stt=None,
        tts=NullTTS(),
        vad=EnergyVAD(),
        sessions=sessions,
        device_id=device_id,
        clock=clock,
    )

    service = make_service(speak=pipeline.speak, tick_interval_s=0.01)
    set_active_service(service)
    whale = SimWhale(bus)
    whale.start()
    speaking_sub = bus.subscribe(topics.VOICE_SPEAKING, replay_last=False)
    await service.start()
    try:
        # 1. fake person.down on the bus (what perception publishes at 15 s)
        await bus.publish(
            topics.PERSON_DOWN, {"device_id": device_id, "t": clock(), "ballistic": True}
        )
        await asyncio.sleep(0.05)
        assert mstate(service.machine) is State.CONCERN

        # 2. the whale flew over (sim stand-in consumed flight.dispatch)
        assert whale.flights and whale.flights[0]["reason"] == "verify"

        # 3. first ask already spoken as real audio; timeout → second ask
        audio_after_first_ask = len(sink.chunks)
        assert audio_after_first_ask > 0  # actual PCM went to the sink
        clock.advance(service.machine.config.verify_ask_timeout_s)
        await service.tick()
        assert len(sink.chunks) > audio_after_first_ask  # ask #2 audible too

        # 4. no response → L1 (alert open, simulated notifier fired)
        clock.advance(service.machine.config.verify_ask_timeout_s)
        await service.tick()
        assert mstate(service.machine) is State.ESCALATE_L1
        with db_factory() as db:
            alert = db.query(Alert).one()
            assert alert.state == "open" and alert.level == "L1"
            alert_id = alert.id

        # both asks went through the real pipeline: two speaking on/off cycles
        speaking_events: list[bool] = []
        while not speaking_sub._queue.empty():  # test-only peek
            speaking_events.append(bool((await speaking_sub.get()).payload["on"]))
        assert speaking_events.count(True) == 2  # exactly two spoken asks

        # 5. dashboard-less ack via the REST API halts everything
        response = await api_client.post(
            f"/api/v1/alerts/{alert_id}/ack",
            json={"contact_id": seeded["daughter_id"], "via": "dashboard"},
        )
        assert response.status_code == 200
        assert response.json()["machine_state"] == "IDLE"
        assert mstate(service.machine) is State.IDLE

        # ladder is dead — nothing more fires even much later
        clock.advance(10_000.0)
        await service.tick()
        assert mstate(service.machine) is State.IDLE

        with db_factory() as db:
            row = db.get(Alert, alert_id)
            assert row is not None and row.state == "acknowledged:dashboard"
            walk = [
                (r.from_state, r.to_state)
                for r in db.query(AuditLog)
                .filter(AuditLog.action == "guardian.transition")
                .order_by(AuditLog.id)
            ]
            assert walk == [
                ("IDLE", "CONCERN"),
                ("CONCERN", "CONCERN"),
                ("CONCERN", "ESCALATE_L1"),
                ("ESCALATE_L1", "IDLE"),
            ]
    finally:
        speaking_sub.close()
        await service.stop()
        await whale.stop()
        set_active_service(None)
