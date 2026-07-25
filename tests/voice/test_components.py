"""Graceful degradation + voice-character registry tests (Art. IX §3).

These run in an environment with NO voice extras installed — which is exactly
the point: every factory must return a working (or explicitly absent) stage
without crashing, with no API keys and no downloads.
"""

from __future__ import annotations

import sys

import pytest

from meemoo.core.config import Settings, get_settings
from meemoo.voice.audio_io import BufferSource, NullSink
from meemoo.voice.phrases import PhraseMatcher, levenshtein_at_most_1, normalize
from meemoo.voice.tts import NullTTS, create_tts
from meemoo.voice.types import TTS, AudioSink, AudioSource
from meemoo.voice.vad import EnergyVAD, create_vad
from meemoo.voice.voices import DEFAULT_VOICE, VOICES, get_voice
from meemoo.voice.wake import PushToTalk, create_wake

_HEAVY_MODULES = [
    "moonshine_onnx",
    "faster_whisper",
    "pocket_tts",
    "piper",
    "openwakeword",
    "openwakeword.model",
    "sounddevice",
]


@pytest.fixture(autouse=True)
def _bare(bare_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin credential-less settings AND make every heavy dep unimportable,
    so these tests exercise the degradation paths even on a machine where
    ``uv sync --group voice`` has run (a None sys.modules entry ⇒ ImportError)."""
    monkeypatch.setattr("meemoo.voice.tts.get_settings", lambda: bare_settings)
    monkeypatch.setattr("meemoo.voice.vad.get_settings", lambda: bare_settings)
    for mod in _HEAVY_MODULES:
        monkeypatch.setitem(sys.modules, mod, None)
    get_settings.cache_clear()


class TestFactoriesDegrade:
    def test_tts_factory_never_crashes(self) -> None:
        tts = create_tts()
        assert isinstance(tts, TTS)
        chunks = list(tts.synthesize("hello there", "elder_male"))
        assert chunks and all(isinstance(c, bytes) for c in chunks)

    def test_stt_factory_never_crashes(self, bare_settings: Settings,
                                       monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("meemoo.voice.stt.get_settings", lambda: bare_settings)
        from meemoo.voice.stt import create_stt

        engine = create_stt()  # heavy engines blocked ⇒ None, no crash
        assert engine is None

    def test_vad_factory_always_returns_a_vad(self) -> None:
        vad = create_vad()
        assert isinstance(vad, EnergyVAD) or vad.name == "silero"

    def test_wake_factory_never_crashes(self) -> None:
        wake = create_wake()
        assert wake.name in ("ptt", "openwakeword")

    def test_ptt_arms_exactly_one_wake(self) -> None:
        ptt = PushToTalk()
        assert ptt.process(b"") is False
        ptt.press()
        assert ptt.process(b"") is True
        assert ptt.process(b"") is False


class TestNullTTS:
    def test_emits_timed_silence_per_word(self) -> None:
        tts = NullTTS()
        chunks = list(tts.synthesize("one two three", "female"))
        assert len(chunks) == 3  # one chunk per word
        assert all(set(c) == {0} for c in chunks)  # pure silence
        # ~150 ms of samples per word at the pipeline rate
        assert len(chunks[0]) == int(tts.sample_rate * 0.15) * 2

    def test_unknown_voice_falls_back_to_default(self) -> None:
        assert get_voice("nonexistent").key == DEFAULT_VOICE


class TestVoices:
    def test_three_characters_committed(self) -> None:
        assert set(VOICES) == {"elder_male", "child", "female"}

    def test_each_character_maps_every_engine_tier(self) -> None:
        for spec in VOICES.values():
            assert spec.pocket_voice
            assert spec.piper_model
            assert spec.piper_length_scale > 0

    def test_characters_are_distinct_per_engine(self) -> None:
        assert len({s.piper_model for s in VOICES.values()}) == 3
        assert len({s.pocket_voice for s in VOICES.values()}) == 3


class TestAudioInterfaces:
    def test_buffer_source_and_null_sink_satisfy_protocols(self) -> None:
        assert isinstance(BufferSource(), AudioSource)
        assert isinstance(NullSink(), AudioSink)

    async def test_null_sink_counts_bytes(self) -> None:
        sink = NullSink()
        await sink.play(b"\x00" * 100, 16_000)
        assert sink.bytes_played == 100


class TestPhrases:
    def test_normalize(self) -> None:
        assert normalize("Help ME, please!") == ["help", "me", "please"]

    @pytest.mark.parametrize(
        ("a", "b", "expected"),
        [
            ("help", "help", True),
            ("helb", "help", True),
            ("hlp", "help", True),
            ("helpp", "help", True),
            ("hey", "help", False),
            ("kelp", "help", True),  # recall over precision — accepted cost
            ("stop", "shop", True),
            ("morning", "help", False),
        ],
    )
    def test_levenshtein_at_most_1(self, a: str, b: str, expected: bool) -> None:
        assert levenshtein_at_most_1(a, b) is expected

    def test_matcher_finds_phrase_inside_utterance(self) -> None:
        matcher = PhraseMatcher(("help me",))
        match = matcher.match("oh please help me right now")
        assert match is not None
        assert match.phrase == "help me"
        assert match.matched_text == "help me"

    def test_short_tokens_require_exact(self) -> None:
        matcher = PhraseMatcher(("call 911",))
        assert matcher.match("call 911") is not None
        assert matcher.match("call 912") is None  # "911" is exact-only
