"""Preset library loader — the Setup Studio's role picker backend (Art. VII §3).

Roles (Companion · Personal Trainer · Hospital Check-in · Tour Guide · Tutor)
live as versioned YAML in ``meemoo/brain/presets/``. Each role has personality
sub-presets; each role+sub combination resolves to a tuned base context that
:mod:`meemoo.brain.personality` folds into the system prompt. Power users edit
the raw YAML (or the raw context via the Studio, Phase 7); everyone else picks
from the menu and never sees a prompt.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

PRESETS_DIR = Path(__file__).parent


@dataclass(frozen=True, slots=True)
class SubPreset:
    """One personality flavor of a role."""

    key: str
    title: str
    context: str


@dataclass(frozen=True, slots=True)
class Preset:
    """One role preset: base context + its personality sub-presets."""

    role: str
    title: str
    version: int
    context: str
    default_sub: str
    sub_presets: dict[str, SubPreset] = field(default_factory=dict)

    def resolve(self, sub: str | None = None) -> str:
        """Role context + chosen (or default) personality context, combined."""
        chosen = self.sub_presets.get(sub or self.default_sub)
        if chosen is None:
            logger.warning(
                "unknown sub-preset — using role default",
                extra={"fields": {"role": self.role, "sub": sub}},
            )
            chosen = self.sub_presets.get(self.default_sub)
        parts = [self.context.strip()]
        if chosen is not None:
            parts.append(chosen.context.strip())
        return "\n\n".join(parts)

    @property
    def stamp(self) -> str:
        """Version stamp for escalation-relevant logging (e.g. companion-v1)."""
        return f"{self.role}-v{self.version}"


def _parse(path: Path) -> Preset | None:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        logger.warning("preset file is not a mapping", extra={"fields": {"path": str(path)}})
        return None
    try:
        subs = {
            str(key): SubPreset(
                key=str(key),
                title=str(value.get("title", key)),
                context=str(value.get("context", "")),
            )
            for key, value in dict(raw.get("sub_presets") or {}).items()
        }
        return Preset(
            role=str(raw["role"]),
            title=str(raw.get("title", raw["role"])),
            version=int(raw.get("version", 1)),
            context=str(raw.get("context", "")),
            default_sub=str(raw.get("default_sub", next(iter(subs), ""))),
            sub_presets=subs,
        )
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning(
            "preset file failed to parse — skipped",
            extra={"fields": {"path": str(path), "error": type(exc).__name__}},
        )
        return None


def load_presets(directory: Path | None = None) -> dict[str, Preset]:
    """All presets in ``directory`` (default: the shipped library), by role."""
    presets: dict[str, Preset] = {}
    for path in sorted((directory or PRESETS_DIR).glob("*.yaml")):
        preset = _parse(path)
        if preset is not None:
            presets[preset.role] = preset
    return presets
