"""The escalation state machine — pure, side-effect-free (Constitution Art. IV).

States and transitions are EXACTLY the MASTER_PROMPT §4 spec:

    IDLE → CHECK_IN_DUE → CHECKING (voice check-in active)
    CHECKING → OK (person responded fine) → IDLE
    CHECKING → NO_RESPONSE (timeout) → CONCERN
    person.down event → CONCERN
    CONCERN → verify: fly to person (sim), ask "are you okay?" twice
    CONCERN → OK (responds fine) → IDLE, log the event
    CONCERN → ESCALATE_L1 → (N min, no ack) → ESCALATE_L2 → ESCALATE_L3
    utterance.distress (the voice bypass) → ESCALATE_L1 directly

This module performs NO I/O: no bus, no DB, no clock reads. Time comes in as
an argument; effects come OUT as data (:class:`Effect` values on each
:class:`Transition`) for :mod:`meemoo.guardian.service` to execute. That is
what makes the full state walk, the timeout ladders, and the bypass testable
to the last second (Art. IX §2).

MONOTONIC-URGENCY RULE (safety reading of "from ANY state"): ``person.down``
and ``distress`` move the machine TOWARD escalation but never backward.
Once at ESCALATE_L2, a fresh ``person.down`` must not restart the CONCERN
verify loop — that would reset the L2→L3 ack timer and, with a repeating
detector, livelock the ladder below L3 forever (the catastrophic miss).
Repeated ``person.down`` while already in CONCERN likewise does not reset the
ask counter. Downgrades happen only via a person responding, or a human ack.

NO GENERATIVE MODEL is consulted anywhere in this module (Art. IV §4): every
transition is a deterministic table lookup.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from meemoo.guardian.types import (
    CONFIG_VERSION,
    ESCALATED_STATES,
    Effect,
    GuardianConfig,
    State,
    Transition,
    Trigger,
)

__all__ = [
    "CONFIG_VERSION",
    "ESCALATED_STATES",
    "Effect",
    "EscalationMachine",
    "GuardianConfig",
    "State",
    "Transition",
    "Trigger",
]


@dataclass
class EscalationMachine:
    """Pure machine: feed triggers + ticks, get transitions with effects out."""

    config: GuardianConfig = field(default_factory=GuardianConfig)
    state: State = State.IDLE
    deadline: float | None = None
    asks_sent: int = 0
    episode_trigger: str | None = None  # what started the episode (for logs)

    # ------------------------------------------------------------------ input
    def handle(self, trigger: Trigger, now: float, detail: str | None = None) -> list[Transition]:
        """Apply one trigger at time ``now``; returns transitions (maybe [])."""
        if trigger is Trigger.PERSON_DOWN:
            return self._on_person_down(now, detail)
        if trigger is Trigger.DISTRESS:
            return self._on_distress(now, detail)
        if trigger is Trigger.ACK:
            return self._on_ack(now, detail)
        if trigger is Trigger.CHECKIN_DUE:
            return self._on_checkin_due(now, detail)
        if trigger is Trigger.CHECKIN_STARTED:
            return self._on_checkin_started(now)
        if trigger is Trigger.PERSON_RESPONDED:
            return self._on_person_responded(now, detail)
        return self._on_timeout(now)

    def tick(self, now: float) -> list[Transition]:
        """Advance time; fires the pending timeout when its deadline passes."""
        if self.deadline is not None and now >= self.deadline:
            return self._on_timeout(now)
        return []

    # ------------------------------------------------------------ transitions
    def _move(
        self,
        to_state: State,
        trigger: Trigger | str,
        now: float,
        *,
        effects: tuple[Effect, ...] = (),
        deadline: float | None = None,
        detail: str | None = None,
    ) -> Transition:
        trig = trigger.value if isinstance(trigger, Trigger) else trigger
        t = Transition(self.state, to_state, trig, now, effects, detail)
        self.state = to_state
        self.deadline = deadline
        return t

    def _enter_concern(self, trigger: Trigger, now: float, detail: str | None) -> Transition:
        self.asks_sent = 1
        self.episode_trigger = trigger.value
        return self._move(
            State.CONCERN,
            trigger,
            now,
            effects=(Effect.FLY_TO_PERSON, Effect.ASK_ARE_YOU_OK),
            deadline=now + self.config.verify_ask_timeout_s,
            detail=detail,
        )

    def _resolve_ok(self, now: float, detail: str | None) -> list[Transition]:
        effects: tuple[Effect, ...] = (Effect.LOG_OK, Effect.RESOLVE)
        if self.state is State.CONCERN or self.state in ESCALATED_STATES:
            # An episode that reached verify-or-worse and ended with the person
            # fine counts against the false-alarms/week headline (Art. VIII §3).
            effects = (Effect.LOG_OK, Effect.LOG_FALSE_ALARM, Effect.RESOLVE)
        note = f"episode={self.episode_trigger or 'unknown'}"
        detail = f"{detail}; {note}" if detail else note
        t = self._move(State.IDLE, Trigger.PERSON_RESPONDED, now, effects=effects, detail=detail)
        self.asks_sent = 0
        self.episode_trigger = None
        return [t]

    # ------------------------------------------------------------- per-trigger
    def _on_checkin_due(self, now: float, detail: str | None) -> list[Transition]:
        if self.state is not State.IDLE:
            return []  # never interrupt an active episode with a routine check-in
        self.episode_trigger = Trigger.CHECKIN_DUE.value
        return [
            self._move(
                State.CHECK_IN_DUE,
                Trigger.CHECKIN_DUE,
                now,
                effects=(Effect.START_CHECKIN,),
                # Safety net: if the check-in never starts, the timeout still
                # walks CHECK_IN_DUE → NO_RESPONSE → CONCERN.
                deadline=now + self.config.checkin_response_timeout_s,
                detail=detail,
            )
        ]

    def _on_checkin_started(self, now: float) -> list[Transition]:
        if self.state is not State.CHECK_IN_DUE:
            return []
        return [
            self._move(
                State.CHECKING,
                Trigger.CHECKIN_STARTED,
                now,
                deadline=now + self.config.checkin_response_timeout_s,
            )
        ]

    def _on_person_responded(self, now: float, detail: str | None) -> list[Transition]:
        if self.state in (State.CHECK_IN_DUE, State.CHECKING, State.CONCERN):
            return self._resolve_ok(now, detail)
        # After L1 the contacts are already ringing: a voice reply is recorded
        # by the service but only a HUMAN ack halts the ladder (Art. IV).
        return []

    def _on_person_down(self, now: float, detail: str | None) -> list[Transition]:
        if self.state in ESCALATED_STATES or self.state is State.CONCERN:
            return []  # monotonic-urgency rule (module docstring)
        transitions: list[Transition] = []
        if self.state in (State.CHECK_IN_DUE, State.CHECKING):
            transitions.append(
                self._move(State.NO_RESPONSE, Trigger.PERSON_DOWN, now, detail=detail)
            )
        transitions.append(self._enter_concern(Trigger.PERSON_DOWN, now, detail))
        return transitions

    def _on_distress(self, now: float, detail: str | None) -> list[Transition]:
        if self.state in ESCALATED_STATES:
            return []  # already at L1+; never restart the ack timer downward
        self.episode_trigger = Trigger.DISTRESS.value
        return [
            self._move(
                State.ESCALATE_L1,
                Trigger.DISTRESS,
                now,
                effects=(Effect.NOTIFY_L1,),
                deadline=now + self.config.l1_ack_timeout_s,
                detail=detail,
            )
        ]

    def _on_ack(self, now: float, detail: str | None) -> list[Transition]:
        if self.state not in ESCALATED_STATES:
            return []
        t = self._move(State.IDLE, Trigger.ACK, now, effects=(Effect.RESOLVE,), detail=detail)
        self.asks_sent = 0
        self.episode_trigger = None
        return [t]

    def _on_timeout(self, now: float) -> list[Transition]:
        cfg = self.config
        if self.state in (State.CHECK_IN_DUE, State.CHECKING):
            return [
                self._move(State.NO_RESPONSE, Trigger.TIMEOUT, now),
                self._enter_concern(Trigger.TIMEOUT, now, "no response to check-in"),
            ]
        if self.state is State.CONCERN:
            if self.asks_sent < cfg.verify_asks:
                self.asks_sent += 1
                self.deadline = now + cfg.verify_ask_timeout_s
                return [
                    self._move(
                        State.CONCERN,
                        Trigger.TIMEOUT,
                        now,
                        effects=(Effect.ASK_ARE_YOU_OK,),
                        deadline=self.deadline,
                        detail=f"verify ask {self.asks_sent}/{cfg.verify_asks}",
                    )
                ]
            return [
                self._move(
                    State.ESCALATE_L1,
                    Trigger.TIMEOUT,
                    now,
                    effects=(Effect.NOTIFY_L1,),
                    deadline=now + cfg.l1_ack_timeout_s,
                    detail="no response to verify asks",
                )
            ]
        if self.state is State.ESCALATE_L1:
            return [
                self._move(
                    State.ESCALATE_L2,
                    Trigger.TIMEOUT,
                    now,
                    effects=(Effect.NOTIFY_L2,),
                    deadline=now + cfg.l2_ack_timeout_s,
                    detail="no acknowledgment at L1",
                )
            ]
        if self.state is State.ESCALATE_L2:
            return [
                self._move(
                    State.ESCALATE_L3,
                    Trigger.TIMEOUT,
                    now,
                    effects=(Effect.NOTIFY_L3,),
                    deadline=None,  # terminal until a human acks
                    detail="no acknowledgment at L2",
                )
            ]
        self.deadline = None  # stale deadline in IDLE/L3 — nothing to do
        return []
