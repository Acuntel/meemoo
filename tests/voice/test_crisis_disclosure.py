"""988 crisis protocol + AI disclosure tests (Constitution Art. V §5)."""

from __future__ import annotations

import logging

import pytest

from meemoo.core import topics
from meemoo.core.bus import EventBus
from meemoo.voice.crisis import CRISIS_RESPONSE, CrisisDetector
from meemoo.voice.disclosure import (
    DISCLOSURE_LINE,
    REALNESS_ANSWER,
    REDISCLOSURE_LINE,
    DisclosureSchedule,
    RealnessDetector,
)
from meemoo.voice.pipeline import VoicePipeline

from .conftest import CountingBrain, FakeTTS


class TestCrisis:
    @pytest.mark.parametrize(
        "utterance",
        [
            "I want to die",
            "I'm going to kill myself",
            "im going to kil myself",  # STT typo — fuzzy catch
            "I feel suicidle",  # STT typo — fuzzy catch
            "sometimes I think about suicide",
            "there's no reason to live",
            "I want to end my life",
            "I might hurt myself",
        ],
    )
    def test_fires(self, utterance: str) -> None:
        assert CrisisDetector().check(utterance) is not None

    def test_ordinary_sadness_does_not_fire(self) -> None:
        detector = CrisisDetector()
        for text in ["I'm feeling a bit sad today", "I miss my husband", "I'm tired"]:
            assert detector.check(text) is None, text

    def test_response_contains_988(self) -> None:
        assert "9 8 8" in CRISIS_RESPONSE

    async def test_pipeline_crisis_is_deterministic_and_bypasses_brain(
        self,
        pipeline: VoicePipeline,
        bus: EventBus,
        brain: CountingBrain,
        fake_tts: FakeTTS,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        sub = bus.subscribe(topics.CRISIS_HEARD)
        with caplog.at_level(logging.WARNING):
            await pipeline.handle_text("I want to die")
            await pipeline.handle_text("i want to end my life")
        first = await sub.get()
        second = await sub.get()
        assert first.payload["protocol"] == "988"
        assert second.payload["protocol"] == "988"
        assert brain.calls == []  # no LLM anywhere near the crisis path
        responses = [t for t, _v in fake_tts.spoken if t == CRISIS_RESPONSE]
        assert len(responses) == 2  # identical template both times
        assert any("CRISIS" in r.message for r in caplog.records)  # logged


class TestDisclosure:
    def test_session_start_line_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        schedule = DisclosureSchedule()
        with caplog.at_level(logging.INFO):
            line = schedule.session_start_line(now=100.0)
        assert line == DISCLOSURE_LINE
        assert "not a person" in line  # the honest words, spoken aloud
        assert any("disclosure" in r.message for r in caplog.records)

    def test_periodic_redisclosure_timing(self) -> None:
        schedule = DisclosureSchedule(redisclosure_s=600.0)
        schedule.session_start_line(now=0.0)
        assert schedule.maybe_redisclose(now=599.0) is None
        assert schedule.maybe_redisclose(now=600.0) == REDISCLOSURE_LINE
        assert schedule.maybe_redisclose(now=601.0) is None  # timer reset
        assert schedule.maybe_redisclose(now=1200.0) == REDISCLOSURE_LINE

    @pytest.mark.parametrize(
        "utterance",
        ["are you real", "Are you real?", "are you a robot", "are you alive", "are you human"],
    )
    def test_realness_detector(self, utterance: str) -> None:
        assert RealnessDetector().check(utterance)

    async def test_realness_answer_identical_every_time(
        self, pipeline: VoicePipeline, brain: CountingBrain, fake_tts: FakeTTS
    ) -> None:
        await pipeline.handle_text("are you real?")
        await pipeline.handle_text("are you a robot?")
        answers = [t for t, _v in fake_tts.spoken if t == REALNESS_ANSWER]
        assert len(answers) == 2  # honest and IDENTICAL (Art. V §5)
        assert brain.calls == []  # deterministic path, not the brain

    async def test_disclosure_spoken_at_session_open(
        self, pipeline: VoicePipeline, fake_tts: FakeTTS
    ) -> None:
        await pipeline.handle_text("good morning")
        assert fake_tts.spoken[0][0] == DISCLOSURE_LINE  # first words spoken
