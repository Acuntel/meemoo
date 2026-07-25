"""Anti-repetition paraphrase bank + continuity lines (research 07 §F.5–6).

Fasola & Matarić: 10+ phrasings per intent, sampled without replacement, with
a surfaced "repetition rate" metric. Continuity behaviors: name at greeting
and farewell, reference to the last session, forward-reference to the next
check-in — the visible-memory cues that make the robot feel like it knows you.
"""

from __future__ import annotations

import logging
import random
from collections import deque

logger = logging.getLogger(__name__)

BANKS: dict[str, list[str]] = {
    "greeting": [
        "Hello, {name}! It's lovely to see you.",
        "Hi there, {name}. I was hoping we'd talk.",
        "Good to see you, {name}.",
        "Hello hello, {name}!",
        "There you are, {name}. How nice.",
        "Hi, {name}. I'm glad you're here.",
        "Well hello, {name}!",
        "It's me, {name} — just floating by to say hi.",
        "Hey, {name}. Wonderful timing.",
        "Hello, {name}. I've been looking forward to this.",
        "Hi, {name}! Always a treat.",
        "Good day, {name}.",
    ],
    "praise": [
        "That's wonderful, {name}.",
        "Nicely done!",
        "I'm proud of you, {name}.",
        "Look at you go!",
        "That's the spirit.",
        "Beautifully done.",
        "You make it look easy, {name}.",
        "That was great.",
        "Excellent work.",
        "You should be pleased with that.",
        "Really well done, {name}.",
    ],
    "reminder": [
        "Just a gentle reminder, {name}: {task}.",
        "When you have a moment, {name} — {task}.",
        "A little nudge from me: {task}.",
        "Don't forget, {name}: {task}.",
        "Whenever you're ready: {task}.",
        "Quick reminder — {task}.",
        "It's about time for this one, {name}: {task}.",
        "Popping in to remind you: {task}.",
        "One small thing, {name}: {task}.",
        "Here's your reminder: {task}.",
        "Friendly nudge: {task}.",
    ],
    "farewell": [
        "Goodbye for now, {name}. I'll be nearby.",
        "Talk soon, {name}.",
        "Rest well, {name}. I'm right here if you need me.",
        "Bye for now, {name}!",
        "Until next time, {name}.",
        "Take care, {name}. I'll check on you later.",
        "See you soon, {name}.",
        "I'll let you be, {name}. Call me anytime.",
        "Off I float, {name}. Back before you know it.",
        "Goodbye, {name}. It was lovely talking.",
    ],
}

#: How many recent picks per intent are excluded from re-selection.
DEFAULT_WINDOW = 6


class ParaphraseBank:
    """Samples phrasings without replacement inside a sliding window.

    ``repetition_rate`` = fraction of picks that had already been used within
    the window (0.0 while the bank is big enough; honest about exhaustion).
    Logged per pick so the dashboard can surface it (research 07 §F.5).
    """

    def __init__(
        self,
        banks: dict[str, list[str]] | None = None,
        *,
        window: int = DEFAULT_WINDOW,
        rng: random.Random | None = None,
    ) -> None:
        self._banks = banks if banks is not None else BANKS
        self._window = window
        self._rng = rng or random.Random()
        self._recent: dict[str, deque[str]] = {}
        self.picks = 0
        self.repeats = 0

    @property
    def repetition_rate(self) -> float:
        return self.repeats / self.picks if self.picks else 0.0

    def pick(self, intent: str, **fmt: str) -> str:
        bank = self._banks.get(intent)
        if not bank:
            logger.warning("no paraphrase bank for intent",
                           extra={"fields": {"intent": intent}})
            return ""
        recent = self._recent.setdefault(
            intent, deque(maxlen=min(self._window, max(len(bank) - 1, 1)))
        )
        fresh = [line for line in bank if line not in recent]
        self.picks += 1
        if fresh:
            choice = self._rng.choice(fresh)
        else:  # bank exhausted inside the window — count the repeat honestly
            self.repeats += 1
            choice = self._rng.choice(bank)
        recent.append(choice)
        logger.debug(
            "paraphrase pick",
            extra={"fields": {"intent": intent,
                              "repetition_rate": round(self.repetition_rate, 3)}},
        )
        return choice.format(**{"name": fmt.get("name", "friend"), **fmt})


# --- Continuity (research 07 §F.6: Fasola's callbacks) -----------------------

def greeting_line(bank: ParaphraseBank, name: str, last_note: str | None = None) -> str:
    """Greet by name; reference the last session when we have a note for it."""
    line = bank.pick("greeting", name=name)
    if last_note:
        line += f" Last time we talked, {last_note}"
        if not line.endswith((".", "!", "?")):
            line += "."
    return line


def farewell_line(bank: ParaphraseBank, name: str, next_checkin: str | None = None) -> str:
    """Say goodbye by name; forward-reference the next check-in when known."""
    line = bank.pick("farewell", name=name)
    if next_checkin:
        line += f" I'll come find you again around {next_checkin}."
    return line
