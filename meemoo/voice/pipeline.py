"""The voice pipeline: mic → VAD → STT → checks → brain → TTS → speaker.

Processing order for EVERY final transcript is safety-first and fixed
(Constitution Art. IV §4):

1. STOP detector (while speaking) — barge-in, independent of AEC;
2. DISTRESS bypass — publishes ``utterance.distress``; the brain is never
   consulted; a deterministic acknowledgment template is spoken;
3. 988 crisis protocol — deterministic template response, logged;
4. "are you real?" — the identical honest answer (Art. V §5);
5. only then the brain — ``meemoo.brain.engine.ConversationBrain`` in the
   real wiring; ``templated_brain`` stays as the dependency-free default so
   the pipeline is testable in isolation.

Raw audio is deleted the moment transcription finishes (Art. V §2): the
utterance buffer is cleared and its size logged; no audio bytes are ever
persisted. Ducking: the mic drops ~15 dB while Meemoo speaks (never a mute).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from meemoo.core import topics
from meemoo.core.bus import EventBus
from meemoo.voice.crisis import CRISIS_RESPONSE, CrisisDetector, publish_crisis
from meemoo.voice.disclosure import REALNESS_ANSWER, RealnessDetector
from meemoo.voice.distress import (
    DISTRESS_ACK,
    DistressDetector,
    StopDetector,
    publish_distress,
)
from meemoo.voice.session import SessionManager
from meemoo.voice.types import STT, TTS, VAD, AudioSink, AudioSource
from meemoo.voice.vad import SilenceEndpointer

logger = logging.getLogger(__name__)

Brain = Callable[[str], str]  # ConversationBrain is callable with exactly this shape


def templated_brain(text: str) -> str:
    """Deterministic placeholder brain — echoes warmth, no network, no model."""
    lowered = text.lower()
    if any(g in lowered for g in ("good morning", "morning")):
        return "Good morning! It's lovely to hear your voice. How did you sleep?"
    if any(g in lowered for g in ("hello", "hi ", "hey")):
        return "Hello there! I'm happy you're here. How are you feeling today?"
    if "how are you" in lowered:
        return "I'm doing just fine, thank you for asking. How about you?"
    return f"I heard you say: {text}. Tell me more about that."


class VoicePipeline:
    """Wires the stages together. Every stage is swappable via its interface."""

    def __init__(
        self,
        bus: EventBus,
        *,
        source: AudioSource,
        sink: AudioSink,
        stt: STT | None,
        tts: TTS,
        vad: VAD,
        sessions: SessionManager,
        brain: Brain = templated_brain,
        voice_key: str = "elder_male",
        device_id: int = 1,
        endpointer: SilenceEndpointer | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._bus = bus
        self._source = source
        self._sink = sink
        self._stt = stt
        self._tts = tts
        self._vad = vad
        self._sessions = sessions
        self._brain = brain
        self.voice_key = voice_key
        self._device_id = device_id
        self._endpointer = endpointer or SilenceEndpointer()
        self._clock = clock or time.monotonic
        self._distress = DistressDetector()
        self._stop = StopDetector()
        self._crisis = CrisisDetector()
        self._realness = RealnessDetector()
        self._speaking = False
        self._stop_speaking = False
        self._utterance = bytearray()
        self.last_ttfa_ms: float | None = None  # gate metric, logged every reply

    # ---------------------------------------------------------------- audio in
    async def run(self) -> None:
        """Consume the source until it ends. Cancel-safe."""
        while True:
            chunk = await self._source.read()
            if chunk is None:
                return
            await self._handle_chunk(chunk.pcm)

    async def _handle_chunk(self, pcm: bytes) -> None:
        event = self._endpointer.feed(self._vad.is_speech(pcm))
        if self._endpointer.in_utterance or event.ended:
            self._utterance.extend(pcm)
        if event.ended:
            await self._finish_utterance()

    async def _finish_utterance(self) -> None:
        pcm = bytes(self._utterance)
        # Art. V §2: raw audio is discarded the moment STT has it. Text only.
        self._utterance.clear()
        if self._stt is None:
            logger.info("utterance heard but no STT engine; dropped audio",
                        extra={"fields": {"bytes": len(pcm)}})
            return
        text = self._stt.transcribe(pcm)
        logger.info(
            "raw audio discarded post-transcription",
            extra={"fields": {"bytes_discarded": len(pcm), "chars": len(text)}},
        )
        if text:
            await self.handle_text(text)

    # ----------------------------------------------------------- text handling
    async def handle_text(self, text: str) -> None:
        """Safety-ordered processing of one final transcript (also demo entry)."""
        heard_at = self._clock()

        # 1. barge-in: while speaking, "stop" halts playback and nothing else.
        if self._speaking and self._stop.check(text) is not None:
            self._stop_speaking = True
            self._sink.stop()
            await self._bus.publish(topics.STOP_HEARD, {"transcript": text})
            logger.info("stop heard — playback halted", extra={"fields": {"text": text}})
            return

        session = self._sessions.active
        if session is None:
            session, disclosure = await self._sessions.open(self._device_id, trigger="ptt")
            await self._speak(disclosure, heard_at)
        self._sessions.add_user(text)
        conversation_id = session.conversation_row_id

        # 2. THE DISTRESS BYPASS — before any brain, deterministic ack after.
        distress = self._distress.check(text)
        if distress is not None:
            await publish_distress(
                self._bus, distress, transcript=text,
                device_id=self._device_id, conversation_id=conversation_id,
            )
            self._sessions.add_assistant(DISTRESS_ACK)
            await self._speak(DISTRESS_ACK, heard_at)
            return

        # 3. 988 crisis protocol — deterministic template, no LLM.
        crisis = self._crisis.check(text)
        if crisis is not None:
            await publish_crisis(
                self._bus, crisis, transcript=text,
                device_id=self._device_id, conversation_id=conversation_id,
            )
            self._sessions.add_assistant(CRISIS_RESPONSE)
            await self._speak(CRISIS_RESPONSE, heard_at)
            return

        await self._bus.publish(
            topics.UTTERANCE_HEARD,
            {"transcript": text, "device_id": self._device_id,
             "conversation_id": conversation_id},
        )

        # 4. "are you real?" — identical honest answer every time (Art. V §5).
        if self._realness.check(text):
            self._sessions.add_assistant(REALNESS_ANSWER)
            await self._speak(REALNESS_ANSWER, heard_at)
            return

        # 5. the brain (ConversationBrain when wired; templated default).
        reply = self._brain(text)
        self._sessions.add_assistant(reply)
        await self._speak(reply, heard_at)

    # ---------------------------------------------------------------- speaking
    @property
    def sessions(self) -> SessionManager:
        return self._sessions

    async def speak(self, text: str) -> None:
        """Speak an unprompted line (re-disclosure, check-in greeting)."""
        await self._speak(text, heard_at=self._clock())

    async def _speak(self, text: str, heard_at: float) -> None:
        """Stream TTS to the sink; measure time-to-first-audio; duck the mic."""
        self._speaking = True
        self._stop_speaking = False
        self._source.set_ducked(True)
        await self._bus.publish(topics.VOICE_SPEAKING, {"on": True})
        first_chunk = True
        try:
            for chunk in self._tts.synthesize(text, self.voice_key):
                if self._stop_speaking:
                    break
                if first_chunk:
                    self.last_ttfa_ms = (self._clock() - heard_at) * 1000.0
                    logger.info(
                        "time to first audio",
                        extra={"fields": {"ttfa_ms": round(self.last_ttfa_ms, 1),
                                          "voice": self.voice_key,
                                          "engine": self._tts.name}},
                    )
                    first_chunk = False
                await self._sink.play(chunk, self._tts.sample_rate)
        finally:
            self._speaking = False
            self._stop_speaking = False
            self._source.set_ducked(False)
            await self._bus.publish(topics.VOICE_SPEAKING, {"on": False})
