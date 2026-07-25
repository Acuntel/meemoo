"""Anti-repetition bank + continuity lines (research 07 §F.5–6)."""

from __future__ import annotations

import random

from meemoo.brain.paraphrase import (
    BANKS,
    ParaphraseBank,
    farewell_line,
    greeting_line,
)


def test_banks_have_ten_plus_variants_each() -> None:
    for intent in ("greeting", "praise", "reminder", "farewell"):
        assert len(BANKS[intent]) >= 10, intent


def test_no_repeat_within_window() -> None:
    bank = ParaphraseBank(rng=random.Random(7), window=6)
    picks = [bank.pick("greeting", name="Ruth") for _ in range(30)]
    for i in range(len(picks) - 1):
        window = picks[max(0, i - 5) : i]
        assert picks[i] not in window
    assert bank.repetition_rate == 0.0  # big bank, honest zero


def test_exhausted_bank_counts_repeats_honestly() -> None:
    tiny = {"greeting": ["a {name}", "b {name}"]}
    bank = ParaphraseBank(tiny, rng=random.Random(1), window=6)
    for _ in range(10):
        bank.pick("greeting", name="x")
    assert bank.picks == 10
    assert bank.repetition_rate == 0.0  # window clamps to len(bank)-1

    always_stale = ParaphraseBank({"g": ["only {name}"]}, rng=random.Random(1))
    always_stale.pick("g", name="x")
    always_stale.pick("g", name="x")  # single-line bank must repeat
    assert always_stale.repeats >= 1
    assert always_stale.repetition_rate > 0.0


def test_unknown_intent_is_empty_not_crash() -> None:
    assert ParaphraseBank().pick("nonexistent") == ""


def test_reminder_formats_task() -> None:
    bank = ParaphraseBank(rng=random.Random(3))
    line = bank.pick("reminder", name="Ruth", task="water the plants")
    assert "water the plants" in line


def test_continuity_greeting_references_last_session() -> None:
    bank = ParaphraseBank(rng=random.Random(5))
    line = greeting_line(bank, "Ruth", last_note="you told me about the garden")
    assert "Ruth" in line
    assert "Last time we talked" in line
    plain = greeting_line(bank, "Ruth")
    assert "Last time" not in plain


def test_continuity_farewell_forward_references_next_checkin() -> None:
    bank = ParaphraseBank(rng=random.Random(5))
    line = farewell_line(bank, "Ruth", next_checkin="one o'clock")
    assert "Ruth" in line and "one o'clock" in line
