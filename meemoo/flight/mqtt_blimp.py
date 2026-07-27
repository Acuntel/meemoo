"""MqttBlimp — hardware stub carrying the FULL radio protocol spec.

TARGET AIRCRAFT (research/04, Constitution Art. I §2)
=====================================================
- Envelope: ~120 L metallized-film SPHERE, 0.61 m diameter, latex-free.
- Trim: 2–4 g NEGATIVELY buoyant — power loss = slow gentle descent.
- Payload budget: **65 g** (~50 g BOM + 30% margin).
- Compute: **ESP32-S3 (Seeed XIAO ESP32S3 Sense)** — camera + PDM mic on
  board, WiFi radio, ~8.6 g with antenna. The aircraft is DUMB (Art. II §1):
  it streams sensors and obeys thrust setpoints; nothing decides on board
  except the reflex battery-failsafe and the wake/help keyword front-end.
- Actuators (BUILD_PLAN §2 — props fly it, fins damp it):
  4× coreless motors with 45 mm props — M1/M2 forward pair (differential =
  yaw), M3/M4 vertical pair; soft wing-fins are PASSIVE dampers (a future
  servo may flap them for character, never for control authority).
- Sensors: IMU (LSM6DS3), downward ToF (VL53L1X), OV2640 camera, PDM mic.

MQTT PROTOCOL v1 (all topics under ``meemoo/<device_id>/``)
===========================================================
The base station runs the broker (Mosquitto on the base station host).
QoS 0 for streams, QoS 1 for commands/events. Rates are ceilings — the
aircraft may thin streams under RSSI pressure, never commands.

BENCH TRANSPORT (v1 hardware, firmware/ in this repo): the bench firmware
carries ``cmd/thrust`` + ``cmd/mode`` and the telemetry streams as tiny
binary UDP packets instead of MQTT — protocol "MUP/1", byte layout pinned
in :mod:`meemoo.flight.mup` (canonical, unit-tested) and documented in
firmware/README.md. Field SEMANTICS are identical to the topics below
(same gf units, same ttl stale-command guard, same 3 s link-loss
failsafe); MQTT remains the production target and the video/audio
announce handoff is unchanged (MJPEG on :81 either way).

Aircraft → base (telemetry)
---------------------------
- ``tele/imu``      20 Hz, QoS 0: ``{"t": ms, "pitch": rad, "roll": rad,
  "yaw_rate": rad_s, "pitch_rate": rad_s, "az": m_s2}`` — pitch_rate feeds
  the base-side swing-reducer (research/04 §F).
- ``tele/battery``  1 Hz, QoS 0: ``{"mv": int, "pct": float,
  "charging": bool}``.
- ``tele/tof``      10 Hz, QoS 0: ``{"agl_mm": int}`` (height above floor).
- ``tele/duty``     2 Hz, QoS 0: ``{"m1": 0..1, "m2": 0..1, "m3": 0..1,
  "m4": 0..1}`` — hover-duty history feeds ``netBuoyancy_gf`` estimation
  (research/06 §G): the LTA number nobody thinks to add.
- ``tele/rssi``     1 Hz, QoS 0: ``{"dbm": int}`` — link health.
- ``evt/failsafe``  QoS 1, retained: ``{"kind": "low_batt"|"link_loss"|
  "motor_fault", "t": ms}`` — the ONLY autonomous behavior on the aircraft:
  on link loss > 3 s or pack < 3.3 V it zeroes thrust and descends on its
  negative trim (Art. IV §6). No other intelligence on board, ever.

Base → aircraft (commands)
--------------------------
- ``cmd/thrust``    20 Hz max, QoS 0: ``{"seq": int, "fwd_gf": float,
  "vert_gf": float, "yaw_gf": float, "ttl_ms": 250}`` — the SAME
  :class:`~meemoo.flight.types.ThrustCommand` shape the sim flies; the
  aircraft clamps to its measured per-motor saturation (~10 gf) and IGNORES
  any frame older than ``ttl_ms`` (stale-command guard). Mixer on board is
  a dumb table: fwd/yaw → M1/M2, vert → M3/M4.
- ``cmd/mode``      QoS 1: ``{"mode": "fly"|"idle"|"land_now"}`` —
  ``land_now`` = thrust zero, descend on trim (geofence egress, Art. IV §7).
- ``cmd/led``       QoS 1: expression channel (recording indicator is
  hardware-wired, NOT software — Art. V §4).

Video/audio handoff (streams do NOT ride MQTT)
----------------------------------------------
- ``video/announce`` QoS 1, retained: ``{"mjpeg_url":
  "http://<aircraft-ip>:81/stream", "w": 800, "h": 600, "fps": 12}`` —
  perception's ``VideoSource(mjpeg_url=...)`` consumes it unchanged (the
  step-02 swap point). Re-announced on IP change.
- ``audio/announce`` QoS 1, retained: ``{"proto": "mst1", "host":
  "<aircraft-ip>", "port": 9500}`` — the MST/1 framed satellite transport
  (voice/transport.py) carries mic up / TTS down; wake + "help" keyword
  hits ride MST/1 EVENT frames, never MQTT (latency).

Dock (its own device — Art. II §3; wired serial/USB to the base station)
-----------------------------------------------------------------------
The dock does NOT speak MQTT: guidance camera, electromagnet, ring charger,
load cell, and the hall/reed capture switch arrive over its wired link (see
``DockController``). Capture confirmation stays two-signal and local.

Bring-up checklist (hardware phase)
-----------------------------------
1. Bench-measure per-motor thrust curve → replace the sim's 10 gf constant.
2. Measure command latency distribution → replace the sim's 100 ms.
3. Fly the sim controller against the real airframe on a tether; retune
   gains ONLY (the interfaces must not change — that is the whole bet).
"""

from __future__ import annotations

from meemoo.flight.controller import FlightController
from meemoo.flight.types import BatteryStatus, Pose

_SPEC = (
    "MqttBlimp is a stub until the ESP32-S3 payload exists; the full MQTT "
    "protocol spec lives in meemoo/flight/mqtt_blimp.py's module docstring."
)


class MqttBlimp(FlightController):
    """Future hardware aircraft. Every method raises with the spec attached."""

    def __init__(self, device_id: str = "blimp-01", broker_url: str = "mqtt://localhost") -> None:
        self.device_id = device_id
        self.broker_url = broker_url

    def takeoff(self) -> None:
        raise NotImplementedError(_SPEC)

    def land(self) -> None:
        raise NotImplementedError(_SPEC)

    def goto(self, x: float, y: float, *, label: str | None = None) -> bool:
        raise NotImplementedError(_SPEC)

    def patrol(self, waypoints: list[tuple[str, str, float, float]]) -> None:
        raise NotImplementedError(_SPEC)

    def hold(self) -> None:
        raise NotImplementedError(_SPEC)

    def return_to_dock(self) -> None:
        raise NotImplementedError(_SPEC)

    def request_dock(self) -> None:
        raise NotImplementedError(_SPEC)

    def abort_dock(self) -> None:
        raise NotImplementedError(_SPEC)

    def request_undock(self) -> None:
        raise NotImplementedError(_SPEC)

    def battery_status(self) -> BatteryStatus:
        raise NotImplementedError(_SPEC)

    def position(self) -> Pose:
        raise NotImplementedError(_SPEC)

    def net_buoyancy_gf(self) -> float:
        raise NotImplementedError(_SPEC)
