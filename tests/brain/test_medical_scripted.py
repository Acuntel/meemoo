"""Medical rail (deterministic, recall-leaning) + scripted zero-key check-in."""

from __future__ import annotations

import random

import pytest

from meemoo.brain.medical import MEDICAL_HANDOFF, MedicalDetector
from meemoo.brain.paraphrase import ParaphraseBank
from meemoo.brain.scripted import CONCERN_REPLY, ScriptedCheckin


# ------------------------------------------------------------- medical rail
@pytest.mark.parametrize("text", [
    "should I double my dose of lisinopril",
    "can I stop taking my medication",
    "is it safe to take two pills instead of one",
    "do I have dementia",
    "is this a heart attack",
    "what does my blood pressure reading mean",
    "my blood sugar is 210, is that high",
    "should I go to the emergency room",
    "what are the symptoms of a stroke",
    "can you diagnose this rash",
])
def test_medical_questions_detected(text: str) -> None:
    assert MedicalDetector().check(text) is not None


@pytest.mark.parametrize("text", [
    "good morning meemoo",
    "tell me about your day",
    "my grandson visits on sunday",
    "I took my medication this morning",  # a statement, not a question
    "let's do our exercises",
])
def test_ordinary_talk_not_flagged(text: str) -> None:
    assert MedicalDetector().check(text) is None


def test_handoff_template_is_deterministic_and_human_bound() -> None:
    assert "can't give medical advice" in MEDICAL_HANDOFF
    assert "doctor" in MEDICAL_HANDOFF


# --------------------------------------------------------- scripted check-in
def _tree(**kwargs: object) -> ScriptedCheckin:
    return ScriptedCheckin(
        name="Ruth", bank=ParaphraseBank(rng=random.Random(2)), **kwargs,  # type: ignore[arg-type]
    )


def test_opening_greets_by_name_and_asks_the_question() -> None:
    tree = _tree(last_note="you told me about the roses.")
    opening = tree.opening_line()
    assert "Ruth" in opening
    assert "are you feeling alright today" in opening.lower()
    assert "Last time we talked" in opening


def test_positive_answer_flows_to_reminder_then_close() -> None:
    tree = _tree(reminders=["take your heart medication"])
    tree.opening_line()
    reply = tree.reply("yes I'm feeling good")
    assert "glad" in reply.lower()
    assert "take your heart medication" in reply
    goodbye = tree.reply("goodbye")
    assert "Ruth" in goodbye
    assert tree.state.stage == "closed"


def test_negative_answer_takes_the_concern_branch() -> None:
    tree = _tree()
    tree.opening_line()
    reply = tree.reply("not great, I feel dizzy")
    assert reply == CONCERN_REPLY.format(name="Ruth")
    assert tree.state.negative_heard is True


def test_unclear_answer_stays_warm() -> None:
    tree = _tree()
    tree.opening_line()
    reply = tree.reply("mmm the weather")
    assert "Ruth" in reply


def test_scripted_needs_zero_configuration(bare_settings: object) -> None:
    """The whole tree runs with no keys, no network, no DB."""
    tree = ScriptedCheckin(name="Ruth")
    assert tree.opening_line()
    assert tree.reply("fine thanks")
    assert tree.reply("bye")
