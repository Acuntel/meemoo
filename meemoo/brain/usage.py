"""Per-request + daily usage recording → the dashboard cost meter.

Every LLM call writes one ``usage`` row (tokens + estimated USD). Pricing is a
versioned in-code table; unknown models record cost 0.0 and are flagged in the
log so the owner knows the meter is undercounting for that model.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from meemoo.core.models import Usage

logger = logging.getLogger(__name__)

PRICING_VERSION = "pricing-2026-06"

#: model → (USD per 1M input tokens, USD per 1M output tokens).
#: Anthropic rows are first-party API rates (skill cache 2026-06-24).
#: OpenAI/Google rows are OWNER-EDITABLE ESTIMATES — verify before relying on
#: the meter for billing. Longest-prefix match so dated/suffixed IDs resolve.
PRICING: dict[str, tuple[float, float]] = {
    "claude-fable-5": (10.0, 50.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-opus-4-6": (5.0, 25.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    # estimates ↓
    "gpt-4o-mini": (0.15, 0.6),
    "gpt-4o": (2.5, 10.0),
    "gemini-2.0-flash": (0.10, 0.40),
}


def price_for(model: str) -> tuple[float, float] | None:
    """Longest-prefix pricing lookup (``claude-opus-5-foo`` → ``claude-opus-5``)."""
    best: str | None = None
    for known in PRICING:
        if model.startswith(known) and (best is None or len(known) > len(best)):
            best = known
    return PRICING[best] if best is not None else None


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    prices = price_for(model)
    if prices is None:
        logger.info(
            "no pricing for model — cost meter records $0 for this call",
            extra={"fields": {"model": model}},
        )
        return 0.0
    per_in, per_out = prices
    return (input_tokens * per_in + output_tokens * per_out) / 1_000_000


def record_usage(
    db_factory: sessionmaker[DbSession] | None,
    *,
    device_id: int,
    provider: str,
    model: str,
    tier: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Persist one usage row; returns the estimated cost (always computed)."""
    cost = estimate_cost(model, input_tokens, output_tokens)
    logger.info(
        "llm usage",
        extra={"fields": {
            "provider": provider, "model": model, "tier": tier,
            "input_tokens": input_tokens, "output_tokens": output_tokens,
            "cost_usd": round(cost, 6), "pricing_version": PRICING_VERSION,
        }},
    )
    if db_factory is not None:
        with db_factory() as db:
            db.add(Usage(
                device_id=device_id, provider=provider, model=model, tier=tier,
                input_tokens=input_tokens, output_tokens=output_tokens, cost_usd=cost,
            ))
            db.commit()
    return cost


@dataclass(frozen=True, slots=True)
class DailyUsage:
    """One day's totals for the cost meter."""

    requests: int
    input_tokens: int
    output_tokens: int
    cost_usd: float


def usage_today(
    db_factory: sessionmaker[DbSession], device_id: int, now: datetime | None = None
) -> DailyUsage:
    """Aggregate today's (UTC) usage for one device."""
    moment = now or datetime.now(UTC).replace(tzinfo=None)
    midnight = datetime.combine(moment.date(), time.min)
    next_midnight = midnight + timedelta(days=1)
    with db_factory() as db:
        row = (
            db.query(
                func.count(Usage.id),
                func.coalesce(func.sum(Usage.input_tokens), 0),
                func.coalesce(func.sum(Usage.output_tokens), 0),
                func.coalesce(func.sum(Usage.cost_usd), 0.0),
            )
            .filter(
                Usage.device_id == device_id,
                Usage.ts >= midnight,
                Usage.ts < next_midnight,
            )
            .one()
        )
    return DailyUsage(
        requests=int(row[0]), input_tokens=int(row[1]),
        output_tokens=int(row[2]), cost_usd=float(row[3]),
    )
