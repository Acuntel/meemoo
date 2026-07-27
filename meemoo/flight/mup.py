"""MUP/1 — the Meemoo UDP Protocol, base-station side (bench radio link).

The bench firmware (``firmware/``, XIAO ESP32S3 Sense) carries motor
commands and telemetry as tiny binary UDP packets. Field SEMANTICS are
identical to the MQTT protocol spec in :mod:`meemoo.flight.mqtt_blimp`
(``cmd/thrust`` / ``cmd/mode`` / the telemetry streams) — MQTT stays the
production target; MUP/1 is the v1 bench transport, and the future UDP
bridge maps :class:`~meemoo.flight.types.ThrustCommand` straight through
:func:`pack_thrust`. This module is the CANONICAL byte-layout reference;
``firmware/include/mup1.h`` mirrors it and firmware/README.md documents it.

Wire format (little-endian, no padding):

THRUST  base → aircraft, UDP port 4210, 16 bytes
  0  u16  magic 0x4D55 ("MU")
  2  u8   version = 1
  3  u8   type = 0x01
  4  u32  seq (monotonic; the aircraft drops older-than-last, wrap-aware)
  8  i16  forward_gf x100
  10 i16  vertical_gf x100
  12 i16  yaw_gf x100 (differential, right minus left, per mqtt spec)
  14 u16  ttl_ms — the command EXPIRES this long after receipt; on expiry
          the aircraft zeroes thrust (stale-command guard, dumb aircraft)

MODE  base → aircraft, UDP port 4210, 16 bytes
  0..7 as THRUST but type = 0x02
  8  u8   mode: 0 = idle, 1 = fly, 2 = land_now
  9..15   zero padding (reserved)

TELEMETRY  aircraft → base (replies to the last commander), 28 bytes
  0  u16  magic 0x4D55
  2  u8   version = 1
  3  u8   type = 0x81
  4  u32  t_ms (aircraft millis)
  8  u16  agl_mm (VL53L1X height above floor; 0xFFFF = sensor absent)
  10 i16  pitch_centirad (MPU6050)
  12 i16  roll_centirad
  14 i16  yaw_rate_centirad_s
  16 i16  az_cm_s2 (vertical accel, gravity removed)
  18 u8   batt_pct (0xFF = no battery sense fitted on the bench BOM)
  19 u8   flags: bit0 failsafe active, bit1 tof ok, bit2 imu ok
  20 4×u8 duty m1..m4 (0..255 = 0..100%, sign dropped — duty magnitude)
  24 u16  batt_mv (0 = not fitted)
  26 u16  seq_ack (low 16 bits of the last accepted command seq)
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

MAGIC = 0x4D55
VERSION = 1
TYPE_THRUST = 0x01
TYPE_MODE = 0x02
TYPE_TELEMETRY = 0x81
COMMAND_PORT = 4210
DEFAULT_TTL_MS = 250
LINK_LOSS_FAILSAFE_MS = 3000  # no fresh command for 3 s → motors zero

MODE_IDLE = 0
MODE_FLY = 1
MODE_LAND_NOW = 2

_HEADER = struct.Struct("<HBBI")
_THRUST_BODY = struct.Struct("<hhhH")
_MODE_BODY = struct.Struct("<B7x")
_TELE = struct.Struct("<HBBIHhhhhBB4BHH")

THRUST_SIZE = _HEADER.size + _THRUST_BODY.size  # 16
MODE_SIZE = _HEADER.size + _MODE_BODY.size  # 16
TELEMETRY_SIZE = _TELE.size  # 28

FLAG_FAILSAFE = 0x01
FLAG_TOF_OK = 0x02
FLAG_IMU_OK = 0x04


def _clamp_i16_x100(value: float) -> int:
    return max(-32768, min(32767, round(value * 100.0)))


def pack_thrust(
    seq: int,
    forward_gf: float,
    vertical_gf: float,
    yaw_gf: float,
    *,
    ttl_ms: int = DEFAULT_TTL_MS,
) -> bytes:
    """Encode a THRUST packet (the ThrustCommand shape, mqtt cmd/thrust)."""
    return _HEADER.pack(MAGIC, VERSION, TYPE_THRUST, seq & 0xFFFFFFFF) + _THRUST_BODY.pack(
        _clamp_i16_x100(forward_gf),
        _clamp_i16_x100(vertical_gf),
        _clamp_i16_x100(yaw_gf),
        max(0, min(0xFFFF, ttl_ms)),
    )


def pack_mode(seq: int, mode: int) -> bytes:
    """Encode a MODE packet (mqtt cmd/mode: idle | fly | land_now)."""
    if mode not in (MODE_IDLE, MODE_FLY, MODE_LAND_NOW):
        raise ValueError(f"unknown mode {mode}")
    return _HEADER.pack(MAGIC, VERSION, TYPE_MODE, seq & 0xFFFFFFFF) + _MODE_BODY.pack(mode)


@dataclass(frozen=True, slots=True)
class Telemetry:
    """One decoded aircraft telemetry packet (see module docstring)."""

    t_ms: int
    agl_mm: int | None  # None = ToF absent
    pitch_rad: float
    roll_rad: float
    yaw_rate_rad_s: float
    az_m_s2: float
    batt_pct: int | None  # None = no battery sense fitted
    failsafe: bool
    tof_ok: bool
    imu_ok: bool
    duty: tuple[float, float, float, float]  # 0..1 magnitudes, m1..m4
    batt_mv: int
    seq_ack: int


def unpack_telemetry(data: bytes) -> Telemetry | None:
    """Decode a TELEMETRY packet; None for anything that is not one."""
    if len(data) != TELEMETRY_SIZE:
        return None
    (
        magic, version, ptype, t_ms, agl_mm, pitch_c, roll_c, yaw_rate_c,
        az_cm, batt_pct, flags, d1, d2, d3, d4, batt_mv, seq_ack,
    ) = _TELE.unpack(data)
    if magic != MAGIC or version != VERSION or ptype != TYPE_TELEMETRY:
        return None
    return Telemetry(
        t_ms=t_ms,
        agl_mm=None if agl_mm == 0xFFFF else agl_mm,
        pitch_rad=pitch_c / 100.0,
        roll_rad=roll_c / 100.0,
        yaw_rate_rad_s=yaw_rate_c / 100.0,
        az_m_s2=az_cm / 100.0,
        batt_pct=None if batt_pct == 0xFF else batt_pct,
        failsafe=bool(flags & FLAG_FAILSAFE),
        tof_ok=bool(flags & FLAG_TOF_OK),
        imu_ok=bool(flags & FLAG_IMU_OK),
        duty=(d1 / 255.0, d2 / 255.0, d3 / 255.0, d4 / 255.0),
        batt_mv=batt_mv,
        seq_ack=seq_ack,
    )


def unpack_command(data: bytes) -> tuple[str, dict[str, float | int]] | None:
    """Decode a base→aircraft packet (reference decoder, mirrors firmware).

    Returns ``("thrust", {...})`` / ``("mode", {...})`` or None. The
    firmware implements the same logic in C++ (mup1.h); this Python twin
    keeps the byte layout pinned by tests.
    """
    if len(data) < _HEADER.size:
        return None
    magic, version, ptype, seq = _HEADER.unpack_from(data)
    if magic != MAGIC or version != VERSION:
        return None
    if ptype == TYPE_THRUST and len(data) == THRUST_SIZE:
        fwd, vert, yaw, ttl = _THRUST_BODY.unpack_from(data, _HEADER.size)
        return ("thrust", {
            "seq": seq, "forward_gf": fwd / 100.0, "vertical_gf": vert / 100.0,
            "yaw_gf": yaw / 100.0, "ttl_ms": ttl,
        })
    if ptype == TYPE_MODE and len(data) == MODE_SIZE:
        (mode,) = _MODE_BODY.unpack_from(data, _HEADER.size)
        return ("mode", {"seq": seq, "mode": mode})
    return None
