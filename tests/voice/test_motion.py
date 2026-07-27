"""Voice motion commands (Amendment A5) — the local grammar itself.

Every command maps to the RIGHT typed ``flight.command``, an impossible
request is declined in words with no command at all, and ordinary
conversation is left alone. The pipeline's priority ladder is proved next
door in test_motion_pipeline.py.

Like the distress tests, these run with the network mocked dead: motion
matching is local intent matching, and "stop" has to work offline.
"""

from __future__ import annotations

import socket

import pytest

from meemoo.flight.capabilities import CANNOT_DO, MotionKind
from meemoo.voice.motion import MotionMatcher, PinBook

PINS: dict[str, tuple[float, float]] = {
    "kitchen": (5.0, 1.5),
    "living room": (2.0, 2.0),
    "Ruth's chair": (6.6, 4.6),
}


@pytest.fixture
def dead_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted in the motion path")

    monkeypatch.setattr(socket.socket, "connect", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)
    monkeypatch.setattr(socket, "getaddrinfo", _refuse)


def pins() -> PinBook:
    return PINS


@pytest.fixture
def matcher() -> MotionMatcher:
    return MotionMatcher(pins=pins)


class TestGrammar:
    """Each phrase maps to the right typed command, with no model involved."""

    @pytest.mark.parametrize(
        ("utterance", "kind", "detail"),
        [
            ("stop", MotionKind.STOP, None),
            ("stop moving", MotionKind.STOP, None),
            ("hold still", MotionKind.STOP, None),
            ("don't move", MotionKind.STOP, None),
            ("go left", MotionKind.MOVE, "left"),
            ("move to your left", MotionKind.MOVE, "left"),
            ("scoot right", MotionKind.MOVE, "right"),
            ("go up", MotionKind.MOVE, "up"),
            ("float down", MotionKind.MOVE, "down"),
            ("come here", MotionKind.COME_HERE, None),
            ("come over to me", MotionKind.COME_HERE, None),
            ("spin around", MotionKind.SPIN, None),
            ("do a spin", MotionKind.SPIN, None),
            ("do a trick", MotionKind.SPIN, None),
            ("go home", MotionKind.DOCK, None),
        ],
    )
    def test_command_maps_to_kind(
        self, matcher: MotionMatcher, utterance: str, kind: MotionKind, detail: str | None
    ) -> None:
        result = matcher.check(utterance)
        assert result is not None, utterance
        assert result.command is not None
        assert result.command.command == kind.value
        if detail is not None:
            assert result.command.direction == detail

    @pytest.mark.parametrize(
        ("utterance", "pin"),
        [
            ("go to the kitchen", "kitchen"),
            ("go to kitchen", "kitchen"),
            ("fly to the living room", "living room"),
            ("go over to Ruth's chair", "Ruth's chair"),
            ("meet me at the kitchen", "kitchen"),
        ],
    )
    def test_goto_resolves_a_named_pin(
        self, matcher: MotionMatcher, utterance: str, pin: str
    ) -> None:
        result = matcher.check(utterance)
        assert result is not None, utterance
        assert result.command is not None
        assert result.command.command == MotionKind.GOTO.value
        assert result.command.label == pin
        assert (result.command.x, result.command.y) == PINS[pin]

    @pytest.mark.parametrize(
        ("pin", "spoken"),
        [
            ("kitchen", "the kitchen"),
            ("living room", "the living room"),
            ("Ruth's chair", "Ruth's chair"),  # a person's pin keeps its name
            ("the window", "the window"),  # no "the the window"
            ("my desk", "my desk"),
        ],
    )
    def test_a_pin_is_spoken_the_way_a_person_would_say_it(
        self, pin: str, spoken: str
    ) -> None:
        book = {pin: (1.0, 1.0)}
        result = MotionMatcher(pins=lambda: book).check(f"go to {pin}")
        assert result is not None and result.speech == f"Okay, heading to {spoken}."

    def test_ordinary_conversation_falls_through_to_the_brain(
        self, matcher: MotionMatcher
    ) -> None:
        for text in [
            "good morning meemoo",
            "how are you today",
            "I have to go to the doctor tomorrow",  # "go to" mid-sentence
            "tell me about the kitchen",  # a pin name, but not a request
            "my grandson visited yesterday",
            "slow down, you're talking too fast",
        ]:
            assert matcher.check(text) is None, text

    def test_matching_is_pure(self, matcher: MotionMatcher, dead_network: None) -> None:
        assert matcher.check("stop") is not None  # no socket, no key, no model

    def test_no_em_dashes_in_spoken_copy(self, matcher: MotionMatcher) -> None:
        """Amendment A7: no em dashes anywhere in product copy."""
        for text in ["stop", "go left", "go to the kitchen", "do a roll",
                     "do a cartwheel", "go to the garage", "spin"]:
            result = matcher.check(text)
            assert result is not None and "—" not in result.speech


class TestCapabilityDeclines:
    """What Meemoo cannot do is said out loud and never flown."""

    @pytest.mark.parametrize(
        ("utterance", "capability"),
        [("do a roll", "roll"), ("roll over", "roll"), ("barrel roll", "roll"),
         ("do a flip", "flip"), ("do a backflip", "flip"), ("somersault", "flip"),
         ("go fast", "fast"), ("go faster", "fast"), ("hurry up", "fast")],
    )
    def test_impossible_request_declines_with_no_command(
        self, matcher: MotionMatcher, utterance: str, capability: str
    ) -> None:
        result = matcher.check(utterance)
        assert result is not None, utterance
        assert result.declined and result.command is None  # NO flight event
        assert result.speech.startswith("I can't")

    def test_decline_names_something_it_can_do(self, matcher: MotionMatcher) -> None:
        result = matcher.check("do a roll")
        assert result is not None
        assert result.speech == "I can't do a roll, but I can do a spin."
        assert CANNOT_DO["roll"] == ("a roll", "spin")

    def test_unknown_trick_declines_with_the_capability_summary(
        self, matcher: MotionMatcher
    ) -> None:
        result = matcher.check("do a cartwheel")
        assert result is not None and result.command is None
        assert "I can hover" in result.speech

    def test_unknown_place_offers_the_pin_drop(self, matcher: MotionMatcher) -> None:
        result = matcher.check("go to the garage")
        assert result is not None and result.command is None
        assert "I don't know where the garage is" in result.speech
        assert "pin" in result.speech
