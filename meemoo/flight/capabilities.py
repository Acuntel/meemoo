"""The capability model + typed flight-command contract (Amendment A5).

Meemoo knows what it can and cannot do. This module is the PUBLIC contract
between the voice layer (which hears motion commands and publishes
``flight.command`` events) and the flight layer (which executes them) —
importing it is not importing another module's internals (Art. II §2); it is
shared vocabulary, like ``core/topics.py``.

Pure stdlib, no network, no model — the same discipline as the distress
detector. Every spoken string here is product copy: warm, plain, honest,
and free of em dashes (Amendment A7).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MotionKind(StrEnum):
    """What the person asked for. UNSUPPORTED never becomes a flight event."""

    STOP = "stop"
    MOVE = "move"  # drift left / right / up / down
    COME_HERE = "come_here"
    GOTO = "goto"  # fly to a named pin from onboarding
    SPIN = "spin"
    DOCK = "dock"  # go home to the dock
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class FlightCommand:
    """The typed ``flight.command`` bus payload. Voice publishes, sim executes."""

    command: str  # a MotionKind value, never UNSUPPORTED
    device_id: int = 1
    direction: str | None = None  # for MOVE: left | right | up | down
    label: str | None = None  # for GOTO: the pin's stored name
    x: float | None = None  # for GOTO: resolved pin coordinates
    y: float | None = None
    source: str = "voice"

    def payload(self) -> dict[str, object]:
        return {
            "command": self.command,
            "device_id": self.device_id,
            "direction": self.direction,
            "label": self.label,
            "x": self.x,
            "y": self.y,
            "source": self.source,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> FlightCommand | None:
        """Tolerant parse; malformed payloads return None, never raise."""
        command = payload.get("command")
        if not isinstance(command, str) or command not in _EXECUTABLE:
            return None
        x, y = payload.get("x"), payload.get("y")
        direction = payload.get("direction")
        label = payload.get("label")
        device = payload.get("device_id")
        return cls(
            command=command,
            device_id=device if isinstance(device, int) else 1,
            direction=str(direction) if isinstance(direction, str) else None,
            label=str(label) if isinstance(label, str) else None,
            x=float(x) if isinstance(x, int | float) else None,
            y=float(y) if isinstance(y, int | float) else None,
            source=str(payload.get("source", "voice")),
        )


_EXECUTABLE = frozenset(
    k.value for k in MotionKind if k is not MotionKind.UNSUPPORTED
)

#: What Meemoo CAN do — the registry a decline draws from (A5).
CAN_DO: dict[str, str] = {
    "hover": "hold still in the air",
    "drift": "drift left or right",
    "up and down": "float up a little or come down a little",
    "turn": "turn to face another way",
    "spin": "do a gentle spin",
    "come here": "come over to you",
    "go to a place": "fly to any place you have named for me",
    "stop": "stop right away when you say stop",
    "go home": "fly back to my dock",
}

#: What Meemoo CANNOT do: request key -> (spoken name, the CAN_DO alternative).
CANNOT_DO: dict[str, tuple[str, str]] = {
    "roll": ("a roll", "spin"),
    "flip": ("a flip", "spin"),
    "fast": ("going fast", "drift"),
}

#: The one-line honest summary every generic decline ends with.
CAPABILITY_SUMMARY = (
    "I can hover, drift left or right, go up and down, turn, spin, "
    "come to you, and fly to places you have named."
)


def can_do(name: str) -> bool:
    return name in CAN_DO


def decline_line(request: str) -> str:
    """A graceful spoken decline that names something Meemoo CAN do (A5)."""
    if request == "fast":
        return (
            "I can't go fast. I always fly at a gentle walking pace, "
            "because that keeps us both safe. I can spin, or come to you, "
            "if you like."
        )
    known = CANNOT_DO.get(request)
    if known is not None:
        spoken, alternative = known
        return f"I can't do {spoken}, but I can do a {alternative}."
    return f"That's not something I can do. {CAPABILITY_SUMMARY}"
