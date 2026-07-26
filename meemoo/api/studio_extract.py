"""Studio config extraction: plain language → structured config.

Two paths, same output shape:
- **model**: the configured LLM turns the owner's paragraph into strict JSON
  (this is config-time convenience, NOT the safety path — Art. IV §4 intact).
- **deterministic**: a pure-regex fallback so the Studio works with zero keys
  and zero network (Art. IX §3). It is deliberately conservative — whatever
  it misses stays in the raw custom context, which is always stored verbatim.
"""

from __future__ import annotations

import json
import logging
import re

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from meemoo.brain.providers import first_available
from meemoo.brain.types import ProviderError

logger = logging.getLogger(__name__)

DbFactory = sessionmaker[DbSession]


class Reminder(BaseModel):
    time: str = Field(pattern=r"^([01]?\d|2[0-3]):[0-5]\d$")
    label: str = "reminder"


class StudioConfig(BaseModel):
    """The reviewable config the Studio shows before saving."""

    person_name: str = "friend"
    relationship: str | None = None
    reminders: list[Reminder] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    tone: list[str] = Field(default_factory=list)
    escalation_note: str | None = None


_RELATIONS = (
    "mom|mother|dad|father|grandma|grandmother|grandpa|grandfather"
    "|aunt|uncle|wife|husband|sister|brother|friend|neighbor|patient"
)
_NAME_PATTERNS = (
    re.compile(rf"\bmy ({_RELATIONS}),? (?:named )?([A-Z][a-z]+)"),
    re.compile(r"\b(?:checking (?:in )?on|check on|care for|caring for) ([A-Z][a-z]+)\b"),
    re.compile(r"\b(?:her|his|their) name is ([A-Z][a-z]+)\b"),
)
_TIME_RE = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?\b", re.IGNORECASE)
_MED_RE = re.compile(
    r"\b(?:takes?|taking|needs?|gets?)\s+(?:her|his|their)?\s*"
    r"([\w -]{0,24}?(?:medications?|medicines?|pills?|meds|insulin|vitamins?))",
    re.IGNORECASE,
)
_INTEREST_RE = re.compile(r"\b(?:loves|likes|enjoys)\s+([^,.;]+(?:,[^,.;]+)*)", re.IGNORECASE)
_TONE_WORDS = (
    "gentle", "patient", "playful", "calm", "cheerful", "firm",
    "encouraging", "upbeat", "kind", "warm", "quiet", "slow",
)
_ESCALATION_RE = re.compile(r"\b(call|text|contact)\s+(me|my \w+|us)\s+first[^,.;]*", re.IGNORECASE)


def _to_hhmm(hour: str, minute: str | None, half: str) -> str:
    h = int(hour) % 12
    if half.lower() == "p":
        h += 12
    return f"{h:02d}:{int(minute or 0):02d}"


def extract_deterministic(text: str) -> StudioConfig:
    """Pure-regex extraction — always works, no key, no network."""
    config = StudioConfig()
    for pattern in _NAME_PATTERNS:
        match = pattern.search(text)
        if match:
            groups = match.groups()
            config.person_name = groups[-1]
            if len(groups) == 2:
                config.relationship = groups[0].lower()
            break
    med = _MED_RE.search(text)
    label = med.group(1).strip().lower() if med else "reminder"
    for time_match in _TIME_RE.finditer(text):
        config.reminders.append(
            Reminder(time=_to_hhmm(*time_match.groups()), label=label)
        )
    interest_match = _INTEREST_RE.search(text)
    if interest_match:
        chunks = re.split(r",| and ", interest_match.group(1))
        config.interests = [c.strip() for c in chunks if c.strip()][:6]
    lowered = text.lower()
    config.tone = [w for w in _TONE_WORDS if re.search(rf"\b{w}\b", lowered)]
    escalation = _ESCALATION_RE.search(text)
    if escalation:
        config.escalation_note = escalation.group(0).strip()
    return config


_EXTRACT_PROMPT = """\
Extract configuration for a companion robot from the owner's instructions.
Respond with ONLY a JSON object, no prose, matching exactly this schema:
{"person_name": str, "relationship": str|null,
 "reminders": [{"time": "HH:MM 24h", "label": str}],
 "interests": [str], "tone": [str], "escalation_note": str|null}
Use "friend" for person_name if no name is given. Omit nothing; use [] / null.
"""


def extract_with_model(
    text: str, db_factory: DbFactory | None, device_id: int = 1
) -> StudioConfig | None:
    """LLM extraction; None on any failure (caller falls back)."""
    provider = first_available(device_id=device_id, db_factory=db_factory)
    if provider is None:
        return None
    try:
        response = provider.complete(
            [{"role": "user", "content": text}],
            "claude-haiku-4-5", 500, system=_EXTRACT_PROMPT,
        )
    except ProviderError as exc:
        logger.warning(
            "studio extraction provider failed — deterministic fallback",
            extra={"fields": {"reason": exc.reason}},
        )
        return None
    raw = response.text.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    try:
        return StudioConfig.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning(
            "studio extraction returned invalid JSON — deterministic fallback",
            extra={"fields": {"error": type(exc).__name__}},
        )
        return None


def extract(
    text: str, db_factory: DbFactory | None, device_id: int = 1
) -> tuple[StudioConfig, str]:
    """Best extraction available; returns (config, source)."""
    config = extract_with_model(text, db_factory, device_id)
    if config is not None:
        return config, "model"
    return extract_deterministic(text), "deterministic"
