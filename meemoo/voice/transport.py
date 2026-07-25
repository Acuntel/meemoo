"""MST/1 — the Meemoo Satellite Transport (own framed protocol, ~200 lines).

Constitution Art. III §4: we own the satellite transport; we do NOT build on
Wyoming (deprecated) or LVA (unfinished). This module is the later swap point:
today the pipeline reads the laptop mic directly; when the blimp payload
exists, the ESP32-S3 speaks MST over TCP/WiFi and the base station wraps a
socket in :class:`FrameDecoder` + :func:`encode_frame` behind the same
``AudioSource``/``AudioSink`` interfaces.

Wire format (all integers big-endian)::

    +-------+---------+------+-------+----------+-----------+---------+
    | magic | version | type |  seq  |  length  |  payload  |  crc32  |
    |  2 B  |   1 B   | 1 B  |  2 B  |   4 B    | length B  |   4 B   |
    | "MO"  |  0x01   |      |       |          |           |         |
    +-------+---------+------+-------+----------+-----------+---------+

- ``seq`` wraps at 65536; receivers use it to spot drops (audio is fire-and-
  forget — no retransmit; a lost 32 ms frame is a lost 32 ms frame).
- ``crc32`` covers header + payload. Bad CRC ⇒ frame dropped, decoder resyncs
  on the next magic. A satellite must never be able to crash the base station
  with garbage bytes.
- AUDIO payloads are PCM16 mono @ 16 kHz, prefixed with a 4-byte capture
  timestamp in milliseconds (satellite-monotonic; base maps to its own clock).
- HELLO/EVENT payloads are UTF-8 JSON (tiny, infrequent — fine on ESP32).

Frame types:

====== ============ ========= =======================================
value  name         direction payload
====== ============ ========= =======================================
0x01   HELLO        sat→base  JSON: device, rates, capabilities
0x02   HELLO_ACK    base→sat  JSON: accepted config
0x03   PING         either    empty
0x04   PONG         either    empty
0x05   AUDIO_IN     sat→base  u32 ts_ms + PCM16 mic frame
0x06   AUDIO_OUT    base→sat  u32 ts_ms + PCM16 TTS frame
0x07   AUDIO_STOP   base→sat  empty — abort playback (barge-in)
0x08   EVENT        sat→base  JSON: {"event": "wake"|"stop"|"button"}
0x09   DUCK         base→sat  u8 on(1)/off(0) — mic ducking hint
0x0F   ERROR        either    JSON: {"error": str}
====== ============ ========= =======================================
"""

from __future__ import annotations

import enum
import json
import struct
import zlib
from dataclasses import dataclass

MAGIC = b"MO"
VERSION = 1
_HEADER = struct.Struct(">2sBBHI")  # magic, version, type, seq, length
_CRC = struct.Struct(">I")
HEADER_SIZE = _HEADER.size
MAX_PAYLOAD = 64 * 1024  # a satellite frame is ~1 KB of audio; 64 KB is hostile


class FrameType(enum.IntEnum):
    HELLO = 0x01
    HELLO_ACK = 0x02
    PING = 0x03
    PONG = 0x04
    AUDIO_IN = 0x05
    AUDIO_OUT = 0x06
    AUDIO_STOP = 0x07
    EVENT = 0x08
    DUCK = 0x09
    ERROR = 0x0F


_VALID_TYPES = frozenset(int(t) for t in FrameType)


@dataclass(frozen=True, slots=True)
class Frame:
    """One decoded MST frame."""

    type: FrameType
    seq: int
    payload: bytes

    def json(self) -> dict[str, object]:
        """Decode a JSON payload (HELLO/EVENT/ERROR frames)."""
        loaded = json.loads(self.payload.decode("utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("MST JSON payload must be an object")
        return loaded

    def audio(self) -> tuple[int, bytes]:
        """Decode an AUDIO_* payload → (ts_ms, pcm16)."""
        if len(self.payload) < 4:
            raise ValueError("audio payload shorter than its timestamp prefix")
        (ts_ms,) = struct.unpack_from(">I", self.payload, 0)
        return int(ts_ms), self.payload[4:]


def encode_frame(type_: FrameType, payload: bytes = b"", seq: int = 0) -> bytes:
    """Encode one frame; ``seq`` wraps at 16 bits."""
    if len(payload) > MAX_PAYLOAD:
        raise ValueError(f"payload {len(payload)} exceeds MAX_PAYLOAD {MAX_PAYLOAD}")
    header = _HEADER.pack(MAGIC, VERSION, int(type_), seq & 0xFFFF, len(payload))
    crc = zlib.crc32(header + payload) & 0xFFFFFFFF
    return header + payload + _CRC.pack(crc)


def encode_audio(type_: FrameType, ts_ms: int, pcm: bytes, seq: int = 0) -> bytes:
    """Convenience: AUDIO_IN / AUDIO_OUT with the u32 timestamp prefix."""
    return encode_frame(type_, struct.pack(">I", ts_ms & 0xFFFFFFFF) + pcm, seq)


def encode_json(type_: FrameType, obj: dict[str, object], seq: int = 0) -> bytes:
    """Convenience: HELLO / EVENT / ERROR with a JSON payload."""
    return encode_frame(type_, json.dumps(obj, separators=(",", ":")).encode(), seq)


class FrameDecoder:
    """Incremental decoder: feed arbitrary byte slices, get complete frames.

    Robustness rules (a dumb aircraft on flaky WiFi is the peer):
    - partial frames wait in the buffer until the rest arrives;
    - a bad magic, unknown version, oversized length, or CRC mismatch drops
      bytes up to the next candidate magic and counts an error — never raises.
    """

    def __init__(self) -> None:
        self._buf = bytearray()
        self.errors = 0  # resyncs since construction (telemetry)

    def feed(self, data: bytes) -> list[Frame]:
        """Consume ``data``; return every complete, valid frame found."""
        self._buf.extend(data)
        frames: list[Frame] = []
        while True:
            frame = self._next_frame()
            if frame is None:
                return frames
            frames.append(frame)

    def _next_frame(self) -> Frame | None:
        while True:
            if not self._sync():
                return None
            if len(self._buf) < HEADER_SIZE:
                return None
            magic, version, ftype, seq, length = _HEADER.unpack_from(self._buf, 0)
            if version != VERSION or length > MAX_PAYLOAD or ftype not in _VALID_TYPES:
                self._resync()
                continue
            total = HEADER_SIZE + length + _CRC.size
            if len(self._buf) < total:
                return None  # wait for more bytes
            body = bytes(self._buf[: HEADER_SIZE + length])
            (crc,) = _CRC.unpack_from(self._buf, HEADER_SIZE + length)
            if zlib.crc32(body) & 0xFFFFFFFF != crc:
                self._resync()
                continue
            del self._buf[:total]
            return Frame(type=FrameType(ftype), seq=seq, payload=body[HEADER_SIZE:])

    def _sync(self) -> bool:
        """Drop garbage until the buffer starts with MAGIC. True if it does."""
        idx = self._buf.find(MAGIC)
        if idx == -1:
            # everything is garbage except a possible split-magic trailing "M"
            keep = 1 if self._buf.endswith(MAGIC[:1]) else 0
            dropped = len(self._buf) - keep
            if dropped:
                self.errors += 1
                del self._buf[:dropped]
            return False
        if idx > 0:
            self.errors += 1
            del self._buf[:idx]
        return True

    def _resync(self) -> None:
        """Corrupt frame at buffer start: skip one byte and re-search magic."""
        self.errors += 1
        del self._buf[:1]
