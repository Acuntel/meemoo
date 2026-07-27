"""``/ws/voice`` — browser push-to-talk, both directions (step-07 §2).

Protocol (JSON text frames + binary):
- server hello: ``{"type":"ready","stt":bool,"tts":str,"voice":str}``
- client → ``{"type":"text","text":…}`` — typed utterance (always works)
- client → binary PCM16 mono 16 kHz chunks, then ``{"type":"end"}`` — spoken
  utterance; transcribed when an STT engine exists, honest error when not
- server → ``{"type":"transcript"|"reply"|"audio"|"error", …}``; replies with
  a real TTS engine are followed by one binary WAV message

Every final transcript goes through the REAL VoicePipeline — the same
safety-ordered path (stop → distress bypass → 988 → realness → brain) as the
server mic (Art. IV §4). Raw audio is discarded after transcription
(Art. V §2). The distress bypass publishes on the LIVE bus, so the guardian
escalates exactly as if the words were spoken in the room.
"""

from __future__ import annotations

import io
import json
import logging
import wave

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from meemoo.api.profile import build_brain, db_factory_or_none, load_profile
from meemoo.core.bus import EventBus
from meemoo.core.bus_registry import get_active_bus
from meemoo.voice.audio_io import BufferSource, CollectSink
from meemoo.voice.crisis import CrisisDetector
from meemoo.voice.distress import DistressDetector
from meemoo.voice.pipeline import VoicePipeline
from meemoo.voice.session import SessionManager
from meemoo.voice.stt import create_stt
from meemoo.voice.tts import create_tts
from meemoo.voice.types import STT, TTS
from meemoo.voice.vad import create_vad

logger = logging.getLogger(__name__)

router = APIRouter(tags=["voice"])

_stt_cache: list[STT | None] | None = None
_tts_cache: TTS | None = None


def _shared_stt() -> STT | None:
    global _stt_cache
    if _stt_cache is None:
        _stt_cache = [create_stt()]
    return _stt_cache[0]


def _shared_tts() -> TTS:
    global _tts_cache
    if _tts_cache is None:
        _tts_cache = create_tts()
    return _tts_cache


def pcm_to_wav(pcm: bytes, rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm)
    return buf.getvalue()


@router.websocket("/ws/voice")
async def ws_voice(ws: WebSocket) -> None:  # noqa: C901 — protocol dispatch
    await ws.accept()
    bus = get_active_bus() or EventBus()
    factory = db_factory_or_none()
    profile = load_profile(factory, 1)
    stt = _shared_stt()
    tts = _shared_tts()
    sink = CollectSink()
    pipeline = VoicePipeline(
        bus,
        source=BufferSource(),
        sink=sink,
        stt=stt,
        tts=tts,
        vad=create_vad(),
        sessions=SessionManager(bus, factory),
        brain=build_brain(factory, 1),
        voice_key=profile.voice,
        device_id=1,
    )
    distress = DistressDetector()
    crisis = CrisisDetector()
    await ws.send_json({
        "type": "ready",
        "stt": stt is not None,
        "tts": tts.name,
        "voice": profile.voice,
    })

    audio_buffer = bytearray()

    async def process(text: str) -> None:
        chunk_start = len(sink.chunks)
        await pipeline.handle_text(text)
        session = pipeline.sessions.active
        reply = ""
        if session is not None and session.context:
            last = session.context[-1]
            if last.get("role") == "assistant":
                reply = last.get("content", "")
        await ws.send_json({
            "type": "reply",
            "text": reply,
            "distress": distress.check(text) is not None,
            "crisis": crisis.check(text) is not None,
        })
        new_chunks = [pcm for pcm, _rate in sink.chunks[chunk_start:]]
        if tts.name != "null" and new_chunks:
            await ws.send_json({"type": "audio", "available": True, "rate": tts.sample_rate})
            await ws.send_bytes(pcm_to_wav(b"".join(new_chunks), tts.sample_rate))
        else:
            await ws.send_json({"type": "audio", "available": False, "engine": tts.name})

    try:
        while True:
            message = await ws.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if (data := message.get("bytes")) is not None:
                audio_buffer.extend(data)
                continue
            raw = message.get("text")
            if raw is None:
                continue
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "reason": "bad json"})
                continue
            kind = parsed.get("type")
            if kind == "text":
                text = str(parsed.get("text", "")).strip()
                if text:
                    await process(text)
            elif kind == "end":
                pcm = bytes(audio_buffer)
                audio_buffer.clear()  # raw audio never outlives the utterance
                if stt is None:
                    await ws.send_json({
                        "type": "error",
                        "reason": "no_stt",
                        "detail": "no STT engine installed; type instead "
                                  "(uv sync --group voice)",
                    })
                    continue
                text = stt.transcribe(pcm)
                logger.info(
                    "browser utterance transcribed; raw audio discarded",
                    extra={"fields": {"bytes": len(pcm), "chars": len(text)}},
                )
                await ws.send_json({"type": "transcript", "text": text})
                if text.strip():
                    await process(text.strip())
            else:
                await ws.send_json({"type": "error", "reason": f"unknown type {kind!r}"})
    except WebSocketDisconnect:
        logger.debug("/ws/voice client disconnected")
    finally:
        await pipeline.sessions.close(reason="ws_closed")
