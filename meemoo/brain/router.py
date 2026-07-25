"""Tier routing: task type → reflex / conversation / reasoning → provider+model.

The spec's cost tiers (MASTER_PROMPT §3): ``reflex`` = cheap/fast for routine
check-ins and reminders, ``conversation`` = mid for open companionship,
``reasoning`` = strong for ambiguous non-safety judgments. Per-device rows in
``model_config`` override the defaults; the router never burns strong-model
tokens on a simple job.

CONSTITUTION Art. IV §4 (binding): the reasoning tier may ADVISE on ambiguous
non-safety judgments, but escalation decisions remain the guardian's
deterministic state machine — nothing routed here can gate, trigger, or
suppress an escalation. The brain package publishes no escalation topics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from meemoo.core.models import ModelConfig

logger = logging.getLogger(__name__)

REFLEX = "reflex"
CONVERSATION = "conversation"
REASONING = "reasoning"

#: task type → tier. Unknown task types land on the conversation tier.
TASK_TIERS: dict[str, str] = {
    "checkin": REFLEX,
    "reminder": REFLEX,
    "smalltalk": REFLEX,
    "memory_extraction": REFLEX,
    "chat": CONVERSATION,
    "companionship": CONVERSATION,
    "coaching": CONVERSATION,
    "scene_review": REASONING,  # advisory only — never gates escalation
    "ambiguous": REASONING,
}

#: Spec-mandated cheap/mid/strong defaults (owner-overridable per device via
#: model_config). Anthropic lineup: Haiku 4.5 ($1/$5 per MTok) / Sonnet 5
#: ($3/$15) / Opus 5 ($5/$25) — see usage.PRICING for the cost meter.
DEFAULT_ROUTES: dict[str, tuple[str, str, int]] = {
    REFLEX: ("anthropic", "claude-haiku-4-5", 300),
    CONVERSATION: ("anthropic", "claude-sonnet-5", 400),
    REASONING: ("anthropic", "claude-opus-5", 1024),
}


@dataclass(frozen=True, slots=True)
class Route:
    """Where one request goes: provider + model + output budget + tier."""

    provider: str
    model: str
    max_tokens: int
    tier: str


class TierRouter:
    """Maps a task type to a :class:`Route`, honoring per-device model_config."""

    def __init__(self, db_factory: sessionmaker[DbSession] | None = None) -> None:
        self._db_factory = db_factory

    def tier_for(self, task_type: str) -> str:
        return TASK_TIERS.get(task_type, CONVERSATION)

    def route(self, task_type: str, device_id: int = 1) -> Route:
        tier = self.tier_for(task_type)
        configured = self._configured(tier, device_id)
        if configured is not None:
            return configured
        provider, model, max_tokens = DEFAULT_ROUTES[tier]
        return Route(provider=provider, model=model, max_tokens=max_tokens, tier=tier)

    def _configured(self, tier: str, device_id: int) -> Route | None:
        if self._db_factory is None:
            return None
        with self._db_factory() as db:
            row = (
                db.query(ModelConfig)
                .filter(ModelConfig.device_id == device_id, ModelConfig.tier == tier)
                .one_or_none()
            )
            if row is None:
                return None
            return Route(
                provider=row.provider, model=row.model,
                max_tokens=int(row.max_tokens), tier=tier,
            )
