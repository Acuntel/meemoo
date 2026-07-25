"""Voice demo — the step-03 gate. Talk to the laptop, hear Meemoo answer.

Live loop (needs ``uv sync --group voice`` + a mic; PTT is implicit — just
speak, VAD segments turns):

    uv run python -m meemoo.voice.demo

Headless / no-audio-deps modes (work anywhere, including CI/SSH):

    uv run python -m meemoo.voice.demo --say "good morning meemoo"
    uv run python -m meemoo.voice.demo --voices-check   # canned line, 3 voices
    uv run python -m meemoo.voice.demo --interactive    # type instead of talk

Every reply logs its measured time-to-first-audio (target < 2 s on the
MacBook). Saying "help me" (or typing it) demonstrates the distress bypass —
watch for the ``utterance.distress`` publish in the log.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from meemoo.core.bus import EventBus
from meemoo.core.config import get_settings
from meemoo.core.logging import setup_logging
from meemoo.voice.audio_io import BufferSource, create_mic, create_speaker
from meemoo.voice.pipeline import VoicePipeline
from meemoo.voice.session import SessionManager
from meemoo.voice.stt import create_stt
from meemoo.voice.tts import create_tts
from meemoo.voice.types import AudioSource
from meemoo.voice.vad import create_vad
from meemoo.voice.voices import VOICES

VOICES_CHECK_LINE = "Hello! I'm Meemoo. This is my {label} voice. It's lovely to meet you."


def build_pipeline(bus: EventBus, source: AudioSource, live: bool) -> VoicePipeline:
    settings = get_settings()
    sessions = SessionManager(
        bus,
        None,  # demo runs memory-only; the API app wires the real DB factory
        silence_close_s=settings.voice_silence_close_s,
    )
    return VoicePipeline(
        bus,
        source=source,
        sink=create_speaker(),
        stt=create_stt() if live else None,
        tts=create_tts(),
        vad=create_vad(),
        sessions=sessions,
        voice_key=settings.voice_character,
    )


async def voices_check(pipeline: VoicePipeline) -> None:
    """Speak a canned line in each of the three characters, log TTFA for each."""
    for key, spec in VOICES.items():
        pipeline.voice_key = key
        await pipeline.handle_text(f"please introduce your {spec.label} voice")
        # the reply itself is templated; what matters here is hearing each voice
        ttfa = pipeline.last_ttfa_ms
        print(f"voice={key:<11} label={spec.label!r} ttfa_ms={ttfa}")  # noqa: T201


async def run_text(pipeline: VoicePipeline, lines: list[str] | None) -> None:
    if lines:
        for line in lines:
            print(f"> {line}")  # noqa: T201
            await pipeline.handle_text(line)
        return
    print("type to talk to Meemoo (blank line or Ctrl-D to quit):")  # noqa: T201
    loop = asyncio.get_event_loop()
    while True:
        text = await loop.run_in_executor(None, sys.stdin.readline)
        if not text or not text.strip():
            return
        await pipeline.handle_text(text.strip())


async def run_live(pipeline: VoicePipeline, sessions_tick_s: float = 1.0) -> None:
    async def _ticker() -> None:
        while True:
            await asyncio.sleep(sessions_tick_s)
            line = await pipeline.sessions.tick()
            if line is not None:
                await pipeline.speak(line)

    ticker = asyncio.create_task(_ticker())
    try:
        await pipeline.run()
    finally:
        ticker.cancel()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Meemoo voice demo (step-03 gate)")
    parser.add_argument("--say", action="append", help="feed one utterance as text")
    parser.add_argument("--voices-check", action="store_true",
                        help="speak a canned line in all three voices")
    parser.add_argument("--interactive", action="store_true",
                        help="type utterances instead of using the mic")
    args = parser.parse_args(argv)

    settings = get_settings()
    setup_logging(json_output=settings.log_json, level=settings.log_level)
    bus = EventBus()

    if args.voices_check or args.say or args.interactive:
        pipeline = build_pipeline(bus, BufferSource(), live=False)
        if args.voices_check:
            asyncio.run(voices_check(pipeline))
        if args.say or args.interactive:
            asyncio.run(run_text(pipeline, args.say))
        return 0

    mic = create_mic()
    if mic is None:
        print("no mic available — falling back to --interactive")  # noqa: T201
        pipeline = build_pipeline(bus, BufferSource(), live=False)
        asyncio.run(run_text(pipeline, None))
        return 0
    pipeline = build_pipeline(bus, mic, live=True)
    print("listening — speak, then pause; say 'help me' to see the bypass; Ctrl-C to quit")  # noqa: T201
    try:
        asyncio.run(run_live(pipeline))
    except KeyboardInterrupt:
        pass
    finally:
        mic.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
