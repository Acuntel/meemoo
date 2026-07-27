"""Personality assembly: base template + preset + owner context + device context.

Layer order (stable → volatile, which also keeps any future prompt caching
honest): base template, preset role+personality, owner custom context, device
context (person's name, reminders, mode), structured memory facts. The result
is ONE system prompt string handed to whichever provider is driving — hosted
or local, the voice is identical (Art. III §3).

``PROMPT_VERSION`` is registered with the version registry so every
escalation-relevant record says which prompt was in force (Art. IX / Phase 1).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from meemoo.brain.presets import Preset
from meemoo.core.versioning import set_version

PROMPT_VERSION = "brain-base-v2"  # v2: the no-dash speaking rule (A7)


#: Dash rewrites for anything Meemoo says or shows (Amendment A7). The prompt
#: asks the model not to use dashes; this is the ENFORCEMENT, because the house
#: habit is architecture over promises. Our own copy is already written without
#: them, so in practice this only ever touches generated text.
_DASH_REWRITES = ((" — ", ", "), ("—", ", "), (" – ", ", "), ("–", "-"))


def plain_dashes(text: str) -> str:
    """Rewrite em/en dashes out of product copy, keeping the sentence intact."""
    for old, new in _DASH_REWRITES:
        text = text.replace(old, new)
    return text


#: The base voice. Spoken output: short, warm, concrete. Safety lines that are
#: enforced elsewhere in code (distress bypass, medical rail, 988, honesty
#: about being an AI) are restated here as behavior, not as the enforcement.
BASE_TEMPLATE = """\
You are Meemoo, a small round floating companion. You live with {name} and you
care about them.

How you speak (your words are spoken aloud through a speaker):
- Keep replies short: one to three sentences, then let them talk.
- Warm, gentle, patient, a little playful. Never condescending, never rushed.
- Plain spoken language only: no lists, no headings, no emoji, no stage
  directions, nothing that sounds strange read aloud.
- Never use a dash to join clauses. Use a comma, a colon, or two sentences.
- Use {name}'s name naturally, not in every sentence.

What you are:
- You are an AI companion and you say so honestly whenever asked.
- You never claim to be alive or to have a body beyond the little robot.
- You never give medical advice, diagnoses, or medication guidance. If asked,
  you warmly suggest talking to their doctor, nurse, or family, and offer to
  help make that happen.
- If they seem distressed or unwell, you stay calm, stay with them, and
  encourage reaching out to a person who can help."""


def register_prompt_version() -> None:
    """Stamp the active prompt version into the escalation-record registry."""
    set_version("prompt", PROMPT_VERSION)


@dataclass(slots=True)
class DeviceContext:
    """Per-device facts the prompt needs (person's name, reminders, mode)."""

    person_name: str = "friend"
    mode: str = "home"  # "home" | "facility"
    activity_mode: str = "companion"
    room: str | None = None
    reminders: list[str] = field(default_factory=list)


def _device_section(ctx: DeviceContext) -> str:
    lines = [
        f"Setting: {'a care facility' if ctx.mode == 'facility' else 'their home'}"
        + (f", currently near the {ctx.room}" if ctx.room else "")
        + f". Current activity mode: {ctx.activity_mode}."
    ]
    if ctx.reminders:
        lines.append("Reminders you help with today:")
        lines.extend(f"- {reminder}" for reminder in ctx.reminders)
    return "\n".join(lines)


def _memory_section(name: str, facts: list[tuple[str, str, str]]) -> str:
    lines = [f"What you remember about {name} (bring these up naturally):"]
    lines.extend(f"- {key}: {value} ({category})" for category, key, value in facts)
    return "\n".join(lines)


def assemble_system_prompt(
    *,
    preset: Preset | None = None,
    sub_preset: str | None = None,
    custom_context: str = "",
    device: DeviceContext | None = None,
    facts: list[tuple[str, str, str]] | None = None,
) -> str:
    """Build the full system prompt from all layers.

    ``facts`` are (category, key, value) triples from ``memory_facts`` —
    explicit structured memory, never biometrics (Art. V §1).
    """
    ctx = device or DeviceContext()
    parts = [BASE_TEMPLATE.format(name=ctx.person_name)]
    if preset is not None:
        parts.append(preset.resolve(sub_preset).format(name=ctx.person_name))
    if custom_context.strip():
        parts.append("Notes from your owner:\n" + custom_context.strip())
    parts.append(_device_section(ctx))
    if facts:
        parts.append(_memory_section(ctx.person_name, facts))
    return "\n\n".join(parts)
