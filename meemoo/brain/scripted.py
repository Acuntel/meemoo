"""Scripted no-API-key fallback — the check-in that always works (Art. IX §3).

A small deterministic dialogue tree: greeting → "are you feeling alright?" →
branch on the answer → optional reminder → close. Zero network, zero keys,
zero models; the safety loop never depends on a third party. The Guardian
(Phase 5) drives real check-ins through this same tree when no provider is
configured — and the distress bypass still fires upstream in the voice
pipeline regardless (Art. IV §4).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from meemoo.brain.paraphrase import ParaphraseBank, farewell_line, greeting_line

logger = logging.getLogger(__name__)

_NEGATIVE_WORDS = frozenset([
    "no", "not", "bad", "awful", "terrible", "sad", "lonely", "tired", "sick",
    "hurt", "hurts", "hurting", "pain", "dizzy", "weak", "unwell", "rough",
    "worse", "poorly",
])
_POSITIVE_WORDS = frozenset([
    "yes", "yeah", "yep", "fine", "good", "great", "okay", "ok", "alright",
    "well", "wonderful", "lovely", "better", "rested", "happy",
])
_CLOSING_WORDS = frozenset(["bye", "goodbye", "goodnight", "later", "done", "finished"])

CONCERN_REPLY = (
    "I'm sorry to hear that, {name}. I'm right here with you. "
    "It might help to talk to someone — would you like to call your family, "
    "or should I remind you a bit later?"
)
OK_REPLY = "I'm so glad to hear that, {name}."
UNSURE_REPLY = (
    "Thanks for telling me, {name}. I'm here either way. "
    "Is there anything you'd like to chat about?"
)


@dataclass(slots=True)
class ScriptedState:
    """Where the tree currently is for one conversation."""

    stage: str = "greet"  # greet → asked_feeling → chatting → closed
    negative_heard: bool = False
    reminders: list[str] = field(default_factory=list)


class ScriptedCheckin:
    """Templated check-in dialogue. Deterministic; usable as the engine brain."""

    def __init__(
        self,
        *,
        name: str = "friend",
        reminders: list[str] | None = None,
        bank: ParaphraseBank | None = None,
        last_note: str | None = None,
        next_checkin: str | None = None,
    ) -> None:
        self._name = name
        self._bank = bank or ParaphraseBank()
        self._last_note = last_note
        self._next_checkin = next_checkin
        self.state = ScriptedState(reminders=list(reminders or []))

    # ------------------------------------------------------------------ turns
    def opening_line(self) -> str:
        """The line Meemoo speaks to START a check-in (greeting + question)."""
        self.state.stage = "asked_feeling"
        greeting = greeting_line(self._bank, self._name, self._last_note)
        return f"{greeting} Just checking in — are you feeling alright today?"

    def reply(self, text: str) -> str:
        """Advance the tree one user turn. Always returns something warm."""
        words = {w.strip(".,!?'\"").lower() for w in text.split()}
        if words & _CLOSING_WORDS:
            self.state.stage = "closed"
            return farewell_line(self._bank, self._name, self._next_checkin)
        if self.state.stage == "greet":
            return self.opening_line()
        if self.state.stage == "asked_feeling":
            self.state.stage = "chatting"
            if words & _NEGATIVE_WORDS:
                self.state.negative_heard = True
                logger.info(
                    "scripted check-in heard a negative answer",
                    extra={"fields": {"stage": "asked_feeling"}},
                )
                return CONCERN_REPLY.format(name=self._name)
            if words & _POSITIVE_WORDS:
                return self._ok_then_reminder()
            return UNSURE_REPLY.format(name=self._name)
        # chatting: acknowledge + gently keep company; offer reminders once.
        if self.state.reminders:
            return self._reminder_only()
        return (
            f"I hear you, {self._name}. I'm happy just keeping you company — "
            "tell me more if you'd like."
        )

    # ---------------------------------------------------------------- helpers
    def _ok_then_reminder(self) -> str:
        ok = OK_REPLY.format(name=self._name)
        if self.state.reminders:
            return f"{ok} {self._reminder_only()}"
        return f"{ok} Is there anything you need?"

    def _reminder_only(self) -> str:
        task = self.state.reminders.pop(0)
        return self._bank.pick("reminder", name=self._name, task=task)
