"""FlightController + DockController interfaces (research/06 §G).

The dock is its own device beside the aircraft (Constitution Art. II §3):
in the real system the dock is WIRED to the base station while the aircraft
is on radio. Conflating them would hurt at hardware time, so the retention
magnet and charger live on ``DockController``, never on the flight side.

Implementations:
- :class:`meemoo.flight.sim_blimp.SimulatedBlimp` — v1, the 2D honest sim.
- :class:`meemoo.flight.mqtt_blimp.MqttBlimp` — hardware stub carrying the
  full MQTT protocol spec for the future ESP32-S3 payload.
- :class:`meemoo.flight.sim_dock.SimulatedDock` — v1 dock device.

Swapping sim for hardware must change NOTHING above this interface
(MASTER_PROMPT: the aircraft is dumb, the ground is smart).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from meemoo.flight.types import (
    BatteryStatus,
    CaptureTelemetry,
    ChargeTelemetry,
    Pose,
)


class FlightController(ABC):
    """Base-station-side flight commands + telemetry for one aircraft."""

    # ------------------------------------------------------------- commands
    @abstractmethod
    def takeoff(self) -> None:
        """Leave the dock (release + depart) or rise from the floor."""

    @abstractmethod
    def land(self) -> None:
        """Descend gently and stop motors where the aircraft is."""

    @abstractmethod
    def goto(self, x: float, y: float, *, label: str | None = None) -> None:
        """Fly to a floor-plan point with floaty easing."""

    @abstractmethod
    def patrol(self, waypoints: list[tuple[str, str, float, float]]) -> None:
        """Fly a round: ordered (label, kind, x, y) stops; ``kind='person'``
        stops hold while the Guardian runs the REAL voice check-in."""

    @abstractmethod
    def hold(self) -> None:
        """Hold the current position (station-keep against drafts)."""

    @abstractmethod
    def return_to_dock(self) -> None:
        """Fly home and run the full docking sequence."""

    @abstractmethod
    def request_dock(self) -> None:
        """Begin docking from wherever the aircraft is (research/06 §G)."""

    @abstractmethod
    def abort_dock(self) -> None:
        """Abort an approach back to standoff (counts a retry)."""

    @abstractmethod
    def request_undock(self) -> None:
        """Release retention and depart the dock."""

    # ------------------------------------------------------------ telemetry
    @abstractmethod
    def battery_status(self) -> BatteryStatus: ...

    @abstractmethod
    def position(self) -> Pose:
        """World-frame pose incl. attitude (heading, pendulum swing)."""

    @abstractmethod
    def net_buoyancy_gf(self) -> float:
        """LTA-specific: net buoyancy estimated from hover-thrust duty —
        drives the approach controller AND helium top-up prediction."""


class DockController(ABC):
    """Dock-side device: retention magnet, charger, capture telemetry."""

    @abstractmethod
    def set_retention(self, on: bool) -> None:
        """Electromagnet on/off (off runs the demagnetising reverse pulse)."""

    @abstractmethod
    def set_charge_enabled(self, on: bool) -> None: ...

    @abstractmethod
    def capture(self) -> CaptureTelemetry:
        """Two independent capture channels. Confirmation REQUIRES both
        contact continuity and the hall/reed switch (Art. II §3) — never
        vision, never a single electrical signal."""

    @abstractmethod
    def charge_telemetry(self) -> ChargeTelemetry: ...
