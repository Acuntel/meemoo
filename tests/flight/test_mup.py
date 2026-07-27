"""MUP/1 codec: the byte layout the firmware mirrors, pinned by tests."""

from __future__ import annotations

import pytest

from meemoo.flight import mup


class TestThrust:
    def test_size_and_header(self) -> None:
        pkt = mup.pack_thrust(7, 4.0, -2.5, 1.25)
        assert len(pkt) == mup.THRUST_SIZE == 16
        assert pkt[0:2] == b"UM"  # magic 0x4D55 little-endian
        assert pkt[2] == mup.VERSION
        assert pkt[3] == mup.TYPE_THRUST

    def test_round_trip(self) -> None:
        pkt = mup.pack_thrust(123456, 4.0, -2.5, 1.25, ttl_ms=300)
        decoded = mup.unpack_command(pkt)
        assert decoded is not None
        kind, fields = decoded
        assert kind == "thrust"
        assert fields["seq"] == 123456
        assert fields["forward_gf"] == pytest.approx(4.0)
        assert fields["vertical_gf"] == pytest.approx(-2.5)
        assert fields["yaw_gf"] == pytest.approx(1.25)
        assert fields["ttl_ms"] == 300

    def test_extreme_values_clamp_not_wrap(self) -> None:
        pkt = mup.pack_thrust(1, 9999.0, -9999.0, 0.0)
        decoded = mup.unpack_command(pkt)
        assert decoded is not None
        _, fields = decoded
        assert fields["forward_gf"] == pytest.approx(327.67)
        assert fields["vertical_gf"] == pytest.approx(-327.68)

    def test_seq_wraps_at_32_bits(self) -> None:
        pkt = mup.pack_thrust(2**32 + 5, 0.0, 0.0, 0.0)
        decoded = mup.unpack_command(pkt)
        assert decoded is not None
        assert decoded[1]["seq"] == 5


class TestMode:
    def test_round_trip(self) -> None:
        pkt = mup.pack_mode(9, mup.MODE_LAND_NOW)
        assert len(pkt) == mup.MODE_SIZE == 16
        decoded = mup.unpack_command(pkt)
        assert decoded == ("mode", {"seq": 9, "mode": mup.MODE_LAND_NOW})

    def test_unknown_mode_raises(self) -> None:
        with pytest.raises(ValueError):
            mup.pack_mode(1, 7)


class TestTelemetry:
    def _packet(self, **overrides: int) -> bytes:
        import struct

        fields = {
            "t_ms": 5000, "agl_mm": 850, "pitch_c": 12, "roll_c": -8,
            "yaw_rate_c": 30, "az_cm": -15, "batt_pct": 87,
            "flags": mup.FLAG_TOF_OK | mup.FLAG_IMU_OK,
            "d1": 128, "d2": 128, "d3": 64, "d4": 64,
            "batt_mv": 3900, "seq_ack": 42,
        }
        fields.update(overrides)
        return struct.pack(
            "<HBBIHhhhhBB4BHH",
            mup.MAGIC, mup.VERSION, mup.TYPE_TELEMETRY,
            fields["t_ms"], fields["agl_mm"], fields["pitch_c"],
            fields["roll_c"], fields["yaw_rate_c"], fields["az_cm"],
            fields["batt_pct"], fields["flags"],
            fields["d1"], fields["d2"], fields["d3"], fields["d4"],
            fields["batt_mv"], fields["seq_ack"],
        )

    def test_decode(self) -> None:
        tele = mup.unpack_telemetry(self._packet())
        assert tele is not None
        assert tele.t_ms == 5000
        assert tele.agl_mm == 850
        assert tele.pitch_rad == pytest.approx(0.12)
        assert tele.roll_rad == pytest.approx(-0.08)
        assert tele.yaw_rate_rad_s == pytest.approx(0.30)
        assert tele.az_m_s2 == pytest.approx(-0.15)
        assert tele.batt_pct == 87
        assert tele.failsafe is False and tele.tof_ok and tele.imu_ok
        assert tele.duty[0] == pytest.approx(128 / 255)
        assert tele.batt_mv == 3900 and tele.seq_ack == 42

    def test_absent_sensors_decode_to_none(self) -> None:
        """The bench BOM has no battery divider; honesty is a None, not a 0%."""
        tele = mup.unpack_telemetry(self._packet(agl_mm=0xFFFF, batt_pct=0xFF, flags=0))
        assert tele is not None
        assert tele.agl_mm is None
        assert tele.batt_pct is None
        assert tele.tof_ok is False and tele.imu_ok is False

    def test_failsafe_flag(self) -> None:
        tele = mup.unpack_telemetry(self._packet(flags=mup.FLAG_FAILSAFE))
        assert tele is not None and tele.failsafe is True

    def test_size_is_pinned(self) -> None:
        assert mup.TELEMETRY_SIZE == 28
        assert len(self._packet()) == 28


class TestGarbage:
    @pytest.mark.parametrize(
        "blob",
        [b"", b"\x00", b"nonsense-not-a-packet!!", b"\x55\x4d\x01\x01" + b"\x00" * 24],
    )
    def test_garbage_never_raises(self, blob: bytes) -> None:
        assert mup.unpack_telemetry(blob) is None
        assert mup.unpack_command(blob) is None

    def test_wrong_magic_is_rejected(self) -> None:
        pkt = bytearray(mup.pack_thrust(1, 1.0, 1.0, 1.0))
        pkt[0] = 0x00
        assert mup.unpack_command(bytes(pkt)) is None

    def test_telemetry_type_is_not_a_command(self) -> None:
        pkt = bytearray(mup.pack_thrust(1, 1.0, 1.0, 1.0))
        pkt[3] = mup.TYPE_TELEMETRY
        assert mup.unpack_command(bytes(pkt)) is None
