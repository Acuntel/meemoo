"""Voice motion commands (Amendment A5) — LOCAL intent matching, no LLM.

Same discipline as :mod:`meemoo.voice.distress`: normalization plus fuzzy
phrase matching over a fixed grammar (:mod:`meemoo.voice.phrases`). No
network, no API key, no model file. "Stop" has to work when the Wi-Fi is down
and the brain is offline, so nothing in this path may reach for one.

The grammar is small on purpose:

    stop / hold still / freeze     -> halt (highest priority after distress)
    go left | right | up | down    -> one gentle drift step
    come here                      -> fly over to the person
    go to <named pin>              -> fly to an onboarding waypoint (A6)
    spin / do a trick              -> the one trick Meemoo has
    go home                        -> back to the dock

A hit becomes a typed ``flight.command`` event that the sim executes; the
voice layer never touches the aircraft directly (Art. II §2). Anything Meemoo
cannot do (a roll, a flip, going fast, a place nobody has shown it) gets a
graceful spoken decline from :mod:`meemoo.flight.capabilities` and NO flight
event at all. That module is a shared contract like ``core/topics.py``, not
another module's internals.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from meemoo.flight.capabilities import FlightCommand, MotionKind, decline_line
from meemoo.voice.phrases import PhraseMatcher, normalize

#: Named destinations: pin name -> (x, y) in floor-plan meters.
PinBook = Mapping[str, tuple[float, float]]
PinProvider = Callable[[], PinBook]

# --- the grammar ------------------------------------------------------------
# Deliberately tight. A phrase earns its place only if it is unambiguous in a
# room where someone is also having a conversation: "come down" is out (it
# fuzzy-matches "came down"), "lower" is out (it matches "slower").

STOP_PHRASES: tuple[str, ...] = (
    "stop",
    "stop moving",
    "stop flying",
    "stop right there",
    "stop there",
    "stay there",
    "stay put",
    "hold still",
    "freeze",
    "halt",
    "don't move",
    "dont move",
)

DIRECTION_PHRASES: dict[str, tuple[str, ...]] = {
    "left": ("go left", "move left", "drift left", "left a bit", "scoot left",
             "go to your left", "move to your left", "a little left"),
    "right": ("go right", "move right", "drift right", "right a bit", "scoot right",
              "go to your right", "move to your right", "a little right"),
    "up": ("go up", "move up", "up a bit", "float up", "fly up", "get higher"),
    "down": ("go down", "move down", "down a bit", "float down", "fly down", "get lower"),
}

COME_HERE_PHRASES: tuple[str, ...] = (
    "come here",
    "come over here",
    "come to me",
    "come over to me",
    "come closer",
    "come see me",
    "over here",
)

SPIN_PHRASES: tuple[str, ...] = (
    "spin",
    "spin around",
    "do a spin",
    "give me a spin",
    "twirl",
    "turn around",
    "do a trick",
    "show me a trick",
)

DOCK_PHRASES: tuple[str, ...] = (
    "go home",
    "go to your dock",
    "go back to your dock",
    "back to the dock",
    "go to bed",
    "go rest",
    "go take a rest",
)

#: Capability key (see ``capabilities.CANNOT_DO``) -> the phrases that ask for it.
IMPOSSIBLE_PHRASES: dict[str, tuple[str, ...]] = {
    "roll": ("do a roll", "roll over", "barrel roll", "do a barrel roll", "can you roll"),
    "flip": ("do a flip", "flip over", "backflip", "do a backflip", "somersault",
             "do a somersault", "flip upside down"),
    "fast": ("go fast", "go faster", "fly fast", "fly faster", "speed up",
             "hurry up", "as fast as you can", "race me"),
}

#: Openers for "go to <place>". Matched as a literal token prefix, in order.
GOTO_PREFIXES: tuple[str, ...] = (
    "go over to the",
    "go over to",
    "go to the",
    "go to",
    "fly over to the",
    "fly over to",
    "fly to the",
    "fly to",
    "head to the",
    "head to",
    "meet me at the",
    "meet me at",
)

#: Openers for "do a <trick>". An unknown trick declines, it never guesses.
TRICK_PREFIXES: tuple[str, ...] = (
    "can you do a",
    "can you do",
    "show me a",
    "do a",
    "do some",
)

# --- spoken replies (product copy: warm, plain, no em dashes — A7) ----------
STOP_LINE = "Okay, stopping right here."
DIRECTION_LINES: dict[str, str] = {
    "left": "Okay, drifting to my left.",
    "right": "Okay, drifting to my right.",
    "up": "Okay, floating up a little.",
    "down": "Okay, coming down a little.",
}
COME_HERE_LINE = "On my way over to you."
SPIN_LINE = "Here comes a spin."
DOCK_LINE = "Okay, heading back to my dock."


@dataclass(frozen=True, slots=True)
class MotionResult:
    """What the voice layer does with a heard motion command.

    ``command is None`` means Meemoo declined: it speaks ``speech`` and
    publishes NOTHING, so an impossible request never becomes a flight.
    """

    speech: str
    command: FlightCommand | None = None
    is_stop: bool = False

    @property
    def declined(self) -> bool:
        return self.command is None


#: Pin names that already read as a phrase take no article in front.
_ARTICLES = ("the ", "a ", "an ", "my ", "your ", "our ")


def spoken_place(name: str) -> str:
    """"the kitchen", but "Ruth's chair" and "the window" keep their own names."""
    lowered = name.lower()
    if name[:1].isupper() or lowered.startswith(_ARTICLES):
        return name
    return f"the {name}"


def _place_line(place: str) -> str:
    return (
        f"I don't know where {spoken_place(place)} is yet. Drop a pin for it "
        "in setup and then I can fly there."
    )


class MotionMatcher:
    """The local motion grammar. Constructing it touches nothing external."""

    def __init__(self, *, device_id: int = 1, pins: PinProvider | None = None) -> None:
        self._device_id = device_id
        self._pins = pins
        self._stop = PhraseMatcher(STOP_PHRASES)
        self._directions = {d: PhraseMatcher(p) for d, p in DIRECTION_PHRASES.items()}
        self._come = PhraseMatcher(COME_HERE_PHRASES)
        self._spin = PhraseMatcher(SPIN_PHRASES)
        self._dock = PhraseMatcher(DOCK_PHRASES)
        self._impossible = {k: PhraseMatcher(v) for k, v in IMPOSSIBLE_PHRASES.items()}
        self._goto_names: frozenset[str] = frozenset()
        self._goto_matcher: PhraseMatcher | None = None
        self._goto_owner: dict[str, str] = {}

    # ------------------------------------------------------------- matching
    def is_stop(self, text: str) -> bool:
        """True for a halt-the-aircraft phrase (checked during barge-in too)."""
        return self._stop.match(text) is not None

    def check(self, text: str) -> MotionResult | None:
        """The heard motion command, or ``None`` to keep going down the pipeline."""
        if self.is_stop(text):
            return MotionResult(STOP_LINE, self._command(MotionKind.STOP), is_stop=True)
        for key, matcher in self._impossible.items():
            if matcher.match(text) is not None:
                return MotionResult(decline_line(key))  # declined: no flight event
        if self._dock.match(text) is not None:
            return MotionResult(DOCK_LINE, self._command(MotionKind.DOCK))
        if self._come.match(text) is not None:
            return MotionResult(COME_HERE_LINE, self._command(MotionKind.COME_HERE))
        if self._spin.match(text) is not None:
            return MotionResult(SPIN_LINE, self._command(MotionKind.SPIN))
        for direction, matcher in self._directions.items():
            if matcher.match(text) is not None:
                return MotionResult(
                    DIRECTION_LINES[direction],
                    self._command(MotionKind.MOVE, direction=direction),
                )
        return self._check_goto(text) or self._check_unknown(text)

    def _command(
        self,
        kind: MotionKind,
        *,
        direction: str | None = None,
        label: str | None = None,
        x: float | None = None,
        y: float | None = None,
    ) -> FlightCommand:
        return FlightCommand(
            command=kind.value, device_id=self._device_id,
            direction=direction, label=label, x=x, y=y,
        )

    # ----------------------------------------------------------- named pins
    def _check_goto(self, text: str) -> MotionResult | None:
        """"Go to <pin>" for a place someone actually named (A6 pin drop)."""
        pins = dict(self._pins()) if self._pins is not None else {}
        self._refresh_goto(pins)
        if self._goto_matcher is None:
            return None
        hit = self._goto_matcher.match(text)
        if hit is None:
            return None
        name = self._goto_owner[hit.phrase]
        x, y = pins[name]
        return MotionResult(
            f"Okay, heading to {spoken_place(name)}.",
            self._command(MotionKind.GOTO, label=name, x=x, y=y),
        )

    def _refresh_goto(self, pins: PinBook) -> None:
        """Rebuild the pin matcher only when the set of names changed."""
        names = frozenset(pins)
        if names == self._goto_names and self._goto_matcher is not None:
            return
        self._goto_names = names
        phrases: list[str] = []
        owner: dict[str, str] = {}
        for name in sorted(names):
            if not normalize(name):
                continue
            for prefix in GOTO_PREFIXES:
                phrase = f"{prefix} {name}"
                phrases.append(phrase)
                owner[phrase] = name
        self._goto_matcher = PhraseMatcher(tuple(phrases)) if phrases else None
        self._goto_owner = owner

    # ------------------------------------------------------------- declines
    def _check_unknown(self, text: str) -> MotionResult | None:
        """Anchored "go to <somewhere>" / "do a <something>" we cannot honour.

        Anchored at the START of the utterance on purpose: "I have to go to
        the doctor tomorrow" is conversation, not a destination request.
        """
        heard = normalize(text)
        place = _after_prefix(heard, GOTO_PREFIXES)
        if place is not None:
            return MotionResult(_place_line(" ".join(place)))
        trick = _after_prefix(heard, TRICK_PREFIXES)
        if trick is not None:
            return MotionResult(decline_line(" ".join(trick)))
        return None


def _after_prefix(heard: list[str], prefixes: tuple[str, ...]) -> list[str] | None:
    """Tokens following the first prefix the utterance STARTS with, else None."""
    for prefix in prefixes:
        tokens = normalize(prefix)
        n = len(tokens)
        if len(heard) > n and heard[:n] == tokens:
            return heard[n:]
    return None
