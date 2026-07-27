"""LABELED synthetic demo data for the research dashboard (research 07 §F.15).

Every payload from this module carries ``synthetic: True`` and a human label —
the demo mode is a presentation harness, never a stand-in for evidence
(research 07: never bring simulated results as evidence). Deterministic
(seeded) so demos are repeatable.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

SYNTHETIC_LABEL = "SYNTHETIC DEMO DATA, not a real resident"


def _dates(days: int) -> list[str]:
    today = datetime.now(UTC).date()
    return [str(today - timedelta(days=offset)) for offset in range(days - 1, -1, -1)]


def demo_engagement(days: int = 42, seed: int = 7) -> dict[str, object]:
    """8-ish weeks: novelty spike → dip → habitual rise (the Kian shape)."""
    rng = random.Random(seed)
    series: list[dict[str, object]] = []
    for index, date in enumerate(_dates(days)):
        week = index / 7.0
        base = 2.2 + 1.5 * min(week / 2.0, 1.0) - 0.9 * (1.0 if 2.0 < week < 3.5 else 0.0)
        sessions = max(0, round(rng.gauss(base + 1.5, 0.9)))
        user_share = min(1.0, max(0.0, 0.25 + 0.09 * week + rng.gauss(0, 0.06)))
        user_initiated = min(sessions, round(sessions * user_share))
        series.append({
            "date": date,
            "sessions": sessions,
            "user_initiated": user_initiated,
            "minutes": round(max(0.0, rng.gauss(4.0 + 0.4 * week, 1.2)) * sessions, 1),
            "turns": sessions * max(1, round(rng.gauss(6, 2))),
        })
    return {"synthetic": True, "label": SYNTHETIC_LABEL, "days": days, "series": series}


def demo_adherence(seed: int = 11) -> dict[str, object]:
    rng = random.Random(seed)
    delivered = 56
    completed = round(delivered * rng.uniform(0.82, 0.9))
    return {
        "synthetic": True,
        "label": SYNTHETIC_LABEL,
        "window_days": 28,
        "delivered": delivered,
        "acknowledged": delivered - 3,
        "completed": completed,
        "missed": delivered - completed,
        "completion_rate": round(completed / delivered, 3),
        "avg_prompts_required": round(rng.uniform(1.1, 1.6), 2),
        "has_data": True,
    }


def demo_human_contact(seed: int = 13) -> dict[str, object]:
    rng = random.Random(seed)
    weeks = 4
    counts = [max(1, round(rng.gauss(4, 1.2))) for _ in range(weeks)]
    weekly: list[dict[str, object]] = [
        {"week": f"demo-w{i + 1}", "count": count} for i, count in enumerate(counts)
    ]
    total = sum(counts)
    return {
        "synthetic": True,
        "label": SYNTHETIC_LABEL,
        "window_days": 28,
        "total": total,
        "by_kind": {"call": total - 3, "visit": 2, "video": 1},
        "weekly": weekly,
    }


def demo_abandonment() -> dict[str, object]:
    return {
        "synthetic": True,
        "label": SYNTHETIC_LABEL,
        "risk": 18,
        "signals": [],
        "has_data": True,
    }


def demo_false_alarms() -> dict[str, object]:
    return {
        "synthetic": True,
        "label": SYNTHETIC_LABEL,
        "false_alarms_last_7_days": 1,
        "window_days": 7,
    }
