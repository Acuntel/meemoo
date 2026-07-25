"""Tier routing + cost meter."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from meemoo.brain.router import CONVERSATION, REASONING, REFLEX, TierRouter
from meemoo.brain.usage import estimate_cost, price_for, record_usage, usage_today
from meemoo.core.models import ModelConfig, Usage


# ------------------------------------------------------------------- routing
def test_task_types_map_to_spec_tiers() -> None:
    router = TierRouter()
    assert router.tier_for("checkin") == REFLEX
    assert router.tier_for("reminder") == REFLEX
    assert router.tier_for("chat") == CONVERSATION
    assert router.tier_for("scene_review") == REASONING
    assert router.tier_for("totally-unknown") == CONVERSATION  # safe default


def test_default_routes_are_cheap_mid_strong() -> None:
    router = TierRouter()
    reflex = router.route("checkin")
    strong = router.route("ambiguous")
    assert reflex.model == "claude-haiku-4-5"  # cheap tier never burns opus
    assert strong.model == "claude-opus-5"
    assert reflex.max_tokens < strong.max_tokens


def test_model_config_row_overrides_default(
    db_factory: sessionmaker[DbSession], seeded: tuple[int, int]
) -> None:
    device_id, _ = seeded
    with db_factory() as db:
        db.add(ModelConfig(
            device_id=device_id, tier=CONVERSATION,
            provider="ollama", model="llama3.2", max_tokens=256,
        ))
        db.commit()
    router = TierRouter(db_factory)
    route = router.route("chat", device_id)
    assert (route.provider, route.model, route.max_tokens) == ("ollama", "llama3.2", 256)
    # other tiers keep defaults
    assert router.route("checkin", device_id).provider == "anthropic"


# ---------------------------------------------------------------- cost meter
def test_pricing_longest_prefix_and_unknown() -> None:
    assert price_for("claude-haiku-4-5") == (1.0, 5.0)
    assert price_for("claude-opus-5") == (5.0, 25.0)
    assert price_for("llama3.2") is None
    assert estimate_cost("llama3.2", 1000, 1000) == 0.0
    # 1M in + 1M out on haiku = $1 + $5
    assert estimate_cost("claude-haiku-4-5", 1_000_000, 1_000_000) == 6.0


def test_record_usage_writes_row_and_daily_aggregates(
    db_factory: sessionmaker[DbSession], seeded: tuple[int, int]
) -> None:
    device_id, _ = seeded
    cost1 = record_usage(
        db_factory, device_id=device_id, provider="anthropic",
        model="claude-haiku-4-5", tier=REFLEX, input_tokens=1000, output_tokens=500,
    )
    cost2 = record_usage(
        db_factory, device_id=device_id, provider="anthropic",
        model="claude-opus-5", tier=REASONING, input_tokens=2000, output_tokens=100,
    )
    assert cost1 > 0 and cost2 > 0
    with db_factory() as db:
        rows = db.query(Usage).order_by(Usage.id).all()
        assert len(rows) == 2
        assert rows[0].tier == REFLEX and rows[0].cost_usd == cost1
    today = usage_today(db_factory, device_id)
    assert today.requests == 2
    assert today.input_tokens == 3000 and today.output_tokens == 600
    assert abs(today.cost_usd - (cost1 + cost2)) < 1e-9
    # a different day sees nothing
    other = usage_today(db_factory, device_id, now=datetime(2001, 1, 1))
    assert other.requests == 0 and other.cost_usd == 0.0


def test_record_usage_without_db_still_returns_cost() -> None:
    assert record_usage(
        None, device_id=1, provider="anthropic", model="claude-haiku-4-5",
        tier=REFLEX, input_tokens=1_000_000, output_tokens=0,
    ) == 1.0
