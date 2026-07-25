"""MST/1 framed-transport tests: round-trip, partials, garbage resilience."""

from __future__ import annotations

import pytest

from meemoo.voice.transport import (
    MAX_PAYLOAD,
    Frame,
    FrameDecoder,
    FrameType,
    encode_audio,
    encode_frame,
    encode_json,
)


def test_round_trip_every_frame_type() -> None:
    decoder = FrameDecoder()
    wire = b"".join(
        encode_frame(t, payload=bytes([i]) * 5, seq=i) for i, t in enumerate(FrameType)
    )
    frames = decoder.feed(wire)
    assert [f.type for f in frames] == list(FrameType)
    assert [f.seq for f in frames] == list(range(len(FrameType)))
    assert decoder.errors == 0


def test_partial_feed_byte_by_byte() -> None:
    wire = encode_json(FrameType.HELLO, {"device": "blimp-1", "rate": 16000}, seq=7)
    decoder = FrameDecoder()
    frames: list[Frame] = []
    for i in range(len(wire)):
        frames.extend(decoder.feed(wire[i : i + 1]))
    assert len(frames) == 1
    assert frames[0].json() == {"device": "blimp-1", "rate": 16000}
    assert frames[0].seq == 7


def test_audio_frame_round_trip() -> None:
    pcm = b"\x01\x02" * 512
    wire = encode_audio(FrameType.AUDIO_IN, ts_ms=123456, pcm=pcm, seq=42)
    (frame,) = FrameDecoder().feed(wire)
    ts_ms, out = frame.audio()
    assert ts_ms == 123456
    assert out == pcm


def test_garbage_before_frame_resyncs() -> None:
    decoder = FrameDecoder()
    good = encode_frame(FrameType.PING)
    frames = decoder.feed(b"\xde\xad\xbe\xef" + good)
    assert [f.type for f in frames] == [FrameType.PING]
    assert decoder.errors >= 1


def test_corrupted_crc_frame_dropped_next_frame_survives() -> None:
    decoder = FrameDecoder()
    bad = bytearray(encode_frame(FrameType.EVENT, b'{"event":"wake"}'))
    bad[-1] ^= 0xFF  # flip a CRC byte
    good = encode_frame(FrameType.PONG)
    frames = decoder.feed(bytes(bad) + good)
    assert [f.type for f in frames] == [FrameType.PONG]
    assert decoder.errors >= 1


def test_unknown_type_and_bad_version_dropped() -> None:
    decoder = FrameDecoder()
    wire = bytearray(encode_frame(FrameType.PING))
    wire[2] = 99  # bogus version byte
    good = encode_frame(FrameType.PING)
    frames = decoder.feed(bytes(wire) + good)
    assert len(frames) == 1
    assert decoder.errors >= 1


def test_oversize_payload_rejected_on_encode() -> None:
    with pytest.raises(ValueError):
        encode_frame(FrameType.AUDIO_IN, b"\x00" * (MAX_PAYLOAD + 1))


def test_hostile_length_field_never_blows_up() -> None:
    # header claiming a 4 GB payload must be dropped, not buffered forever
    decoder = FrameDecoder()
    hostile = bytearray(encode_frame(FrameType.PING))
    hostile[6:10] = (2**32 - 1).to_bytes(4, "big")
    good = encode_frame(FrameType.PONG)
    frames = decoder.feed(bytes(hostile) + good)
    assert [f.type for f in frames] == [FrameType.PONG]


def test_split_magic_across_feeds() -> None:
    wire = encode_frame(FrameType.PING, seq=9)
    decoder = FrameDecoder()
    assert decoder.feed(b"\x00" + wire[:1]) == []  # garbage + first magic byte
    frames = decoder.feed(wire[1:])
    assert [f.seq for f in frames] == [9]


def test_seq_wraps_at_16_bits() -> None:
    (frame,) = FrameDecoder().feed(encode_frame(FrameType.PING, seq=65536 + 5))
    assert frame.seq == 5
