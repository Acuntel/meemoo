"""GuardianService — drives the pure machine from the bus; executes effects.

Bus in (Art. II §2, the ONLY coupling to other modules): ``person.down``,
``utterance.distress``, ``checkin.due``, ``utterance.heard``,
``utterance.crisis``. Bus out: ``guardian.state``, ``flight.dispatch``,
``escalation.l1/l2/l3/acknowledged/resolved``. Every transition and notify
attempt writes an immutable, hash-chained, version-stamped audit row via
:class:`GuardianRecorder` (research 03 §C.2); DB/voice/notifier are all
optional and their absence never crashes anything (Art. IX §3).

L3 rings the configured TEST number and raises a full-screen alert.
AUTO-911 IS NOT IMPLEMENTED — Art. IV §1 requires a signed regulatory review
to add it; the ``auto_dial_911`` flag SHIPS OFF (see :meth:`_run_notify`).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable

from sqlalchemy.orm import Session, sessionmaker

from meemoo.core import topics
from meemoo.core.bus import EventBus, Subscription
from meemoo.core.logging import escalation_extra
from meemoo.guardian.machine import EscalationMachine
from meemoo.guardian.notifier import Notifier
from meemoo.guardian.recorder import GuardianRecorder
from meemoo.guardian.types import (
    CONFIG_VERSION,
    Effect,
    GuardianConfig,
    Transition,
    Trigger,
)

logger = logging.getLogger(__name__)

Speak = Callable[[str], Awaitable[None]]

CHECKIN_GREETING = "Hi, it's Meemoo — just checking in. How are you feeling right now?"
VERIFY_PROMPT = "Are you okay? Please say something if you can hear me."

_TOPIC_TRIGGERS: dict[str, Trigger] = {
    topics.PERSON_DOWN: Trigger.PERSON_DOWN,
    topics.DISTRESS_HEARD: Trigger.DISTRESS,
    topics.CHECKIN_DUE: Trigger.CHECKIN_DUE,
    topics.UTTERANCE_HEARD: Trigger.PERSON_RESPONDED,
    topics.CRISIS_HEARD: Trigger.PERSON_RESPONDED,  # talking = conscious; crisis.py handles 988
}
_EVIDENCE_TOPICS = frozenset({topics.PERSON_DOWN, topics.DISTRESS_HEARD})

_LEVEL_BY_EFFECT = {Effect.NOTIFY_L1: "L1", Effect.NOTIFY_L2: "L2", Effect.NOTIFY_L3: "L3"}
_TOPIC_BY_LEVEL = {"L1": topics.ESCALATION_L1, "L2": topics.ESCALATION_L2,
                   "L3": topics.ESCALATION_L3}
_REASONS = {
    Trigger.PERSON_DOWN.value: "fall detected, no response to voice checks",
    Trigger.DISTRESS.value: "distress phrase heard",
    Trigger.CHECKIN_DUE.value: "no response to scheduled check-in",
}


class GuardianService:
    """One device's escalation spine. Deterministic; no model anywhere."""

    def __init__(
        self,
        bus: EventBus,
        db_factory: sessionmaker[Session] | None = None,
        *,
        device_id: int = 1,
        config: GuardianConfig | None = None,
        notifier: Notifier | None = None,
        speak: Speak | None = None,
        clock: Callable[[], float] | None = None,
        test_number: str | None = None,
        tick_interval_s: float = 0.5,
    ) -> None:
        self._bus = bus
        self.device_id = device_id
        self.machine = EscalationMachine(config or GuardianConfig())
        self._rec = GuardianRecorder(db_factory, device_id)
        self._notifier = notifier
        self._speak = speak
        self._clock: Callable[[], float] = clock or time.monotonic
        self._test_number = test_number
        self._tick_interval_s = tick_interval_s
        self.alert_id: int | None = None
        self._evidence_event_id: int | None = None
        self._tasks: list[asyncio.Task[None]] = []
        self._sub: Subscription | None = None

    # -------------------------------------------------------------- lifecycle
    async def start(self) -> None:
        """Subscribe + run the listener and the timeout ticker."""
        sub = self._bus.subscribe(*_TOPIC_TRIGGERS.keys(), replay_last=False)

        async def _listen() -> None:
            async for event in sub:
                await self.handle_event(event.topic, event.payload)

        async def _tick_loop() -> None:
            while True:
                await asyncio.sleep(self._tick_interval_s)
                await self.tick()

        self._tasks = [asyncio.create_task(_listen()), asyncio.create_task(_tick_loop())]
        self._sub = sub
        logger.info("guardian started", extra={"fields": {
            "device_id": self.device_id, "config": CONFIG_VERSION}})

    async def stop(self) -> None:
        if self._sub is not None:
            self._sub.close()
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except asyncio.CancelledError:
                logger.debug("guardian task cancelled")
        self._tasks = []

    # ------------------------------------------------------------------ input
    async def handle_event(self, topic: str, payload: dict[str, object]) -> None:
        """Feed one bus event through the machine (also the test entry point)."""
        trigger = _TOPIC_TRIGGERS.get(topic)
        if trigger is None:
            return
        event_device = payload.get("device_id")
        if event_device is not None and event_device != self.device_id:
            return  # another device's event
        now = self._clock()
        if topic in _EVIDENCE_TOPICS:
            self._evidence_event_id = self._rec.record_evidence(topic, payload)
        transitions = self.machine.handle(trigger, now, json.dumps({"topic": topic}))
        if not transitions and topic in _EVIDENCE_TOPICS:
            # Monotonic-urgency rule swallowed the transition — still audit it.
            self._audit(
                action="guardian.event_noted",
                trigger=topic,
                detail=f"no transition from {self.machine.state.value} (monotonic urgency)",
            )
        await self._apply(transitions)

    async def tick(self, now: float | None = None) -> None:
        """Advance the timeout ladder (ticker task calls this every 0.5 s)."""
        await self._apply(self.machine.tick(self._clock() if now is None else now))

    async def acknowledge(
        self,
        alert_id: int | None = None,
        *,
        contact_id: int | None = None,
        via: str = "dashboard",
    ) -> dict[str, object]:
        """Human acknowledgment — halts escalation, logs who/when/latency."""
        target = alert_id if alert_id is not None else self.alert_id
        latency: float | None = None
        if target is not None:
            latency = self._rec.ack_alert(target, contact_id=contact_id, via=via)
        self._audit(action="guardian.acknowledged", trigger=via, detail=json.dumps(
            {"alert_id": target, "contact_id": contact_id, "latency_s": latency},
            sort_keys=True))
        await self._bus.publish(
            topics.ESCALATION_ACKNOWLEDGED,
            {"alert_id": target, "contact_id": contact_id, "via": via, "latency_s": latency},
        )
        await self._apply(self.machine.handle(Trigger.ACK, self._clock(), f"ack via {via}"))
        return {"alert_id": target, "latency_s": latency, "state": self.machine.state.value}

    def false_alarms_per_week(self) -> int | None:
        """The Art. VIII §3 headline number (None without a DB)."""
        return self._rec.false_alarms_per_week()

    # ------------------------------------------------------------ transitions
    def _audit(
        self,
        *,
        action: str,
        trigger: str | None,
        detail: str | None,
        from_state: str | None = None,
        to_state: str | None = None,
    ) -> None:
        self._rec.audit(
            action=action, trigger=trigger, detail=detail,
            from_state=from_state, to_state=to_state,
            evidence_event_id=self._evidence_event_id,
        )

    async def _apply(self, transitions: list[Transition]) -> None:
        for t in transitions:
            logger.warning(
                "guardian transition",
                extra=escalation_extra(
                    from_state=t.from_state.value, to_state=t.to_state.value,
                    trigger=t.trigger, detail=t.detail, config=CONFIG_VERSION,
                ),
            )
            self._audit(
                action="guardian.transition",
                from_state=t.from_state.value,
                to_state=t.to_state.value,
                trigger=t.trigger,
                detail=json.dumps(
                    {"effects": [e.value for e in t.effects], "note": t.detail,
                     "config": CONFIG_VERSION},
                    sort_keys=True,
                ),
            )
            await self._bus.publish(
                topics.GUARDIAN_STATE,
                {"device_id": self.device_id, "from": t.from_state.value,
                 "to": t.to_state.value, "trigger": t.trigger},
            )
            for effect in t.effects:
                await self._run_effect(effect, t)

    # ---------------------------------------------------------------- effects
    async def _run_effect(self, effect: Effect, t: Transition) -> None:
        if effect is Effect.START_CHECKIN:
            await self._dispatch_flight("checkin")
            await self._say(CHECKIN_GREETING)
            await self._apply(self.machine.handle(Trigger.CHECKIN_STARTED, self._clock()))
        elif effect is Effect.FLY_TO_PERSON:
            await self._dispatch_flight("verify")
        elif effect is Effect.ASK_ARE_YOU_OK:
            await self._say(VERIFY_PROMPT)
        elif effect in _LEVEL_BY_EFFECT:
            await self._run_notify(_LEVEL_BY_EFFECT[effect])
        elif effect is Effect.LOG_OK:
            self._audit(action="guardian.person_ok", trigger=t.trigger, detail=t.detail)
        elif effect is Effect.LOG_FALSE_ALARM:
            self._rec.record_false_alarm(
                {"episode": t.detail, "resolved_by": "person_responded"}
            )
        elif effect is Effect.RESOLVE:
            await self._resolve(t)

    async def _dispatch_flight(self, reason: str) -> None:
        await self._bus.publish(
            topics.FLIGHT_DISPATCH,
            {"device_id": self.device_id, "reason": reason, "target": "person"},
        )

    async def _say(self, line: str) -> None:
        if self._speak is None:
            logger.info("guardian (no voice): %s", line)
            return
        await self._speak(line)

    async def _run_notify(self, level: str) -> None:
        reason = _REASONS.get(
            self.machine.episode_trigger or "", self.machine.episode_trigger or "unknown"
        )
        self.alert_id = self._rec.open_or_bump_alert(
            level, reason, alert_id=self.alert_id, evidence_event_id=self._evidence_event_id
        )
        payload: dict[str, object] = {"device_id": self.device_id,
                                      "alert_id": self.alert_id, "reason": reason}
        if level == "L3":
            payload["full_screen_alert"] = True
            if self.machine.config.auto_dial_911:
                # TODO(regulatory): real emergency dialing requires a signed
                # regulatory review (Constitution Art. IV §1). The flag ships
                # OFF and this branch deliberately does NOT dial anything.
                logger.error(
                    "auto_dial_911 flag is set but auto-911 is NOT implemented "
                    "— Art. IV §1 regulatory gate; ringing the TEST number only"
                )
        await self._bus.publish(_TOPIC_BY_LEVEL[level], payload)
        results = await self._rec.fan_out(
            self._notifier, level=level, reason=reason,
            alert_id=self.alert_id, test_number=self._test_number,
        )
        for notification, result in results:
            self._audit(
                action="guardian.notify",
                trigger=level,
                detail=json.dumps(
                    {"channel": notification.channel, "to": notification.to,
                     "contact": notification.contact_name, "delivered": result.delivered,
                     "provider": result.provider, "note": result.detail},
                    sort_keys=True,
                ),
            )

    async def _resolve(self, t: Transition) -> None:
        self._rec.close_alert(self.alert_id, "resolved:person_ok")
        await self._bus.publish(
            topics.ESCALATION_RESOLVED,
            {"device_id": self.device_id, "alert_id": self.alert_id, "trigger": t.trigger},
        )
        self.alert_id = None
        self._evidence_event_id = None
