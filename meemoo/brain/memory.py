"""Post-conversation memory extraction + mood note (Art. V §1, step-04 §4).

After a conversation closes, a reflex-tier call turns the transcript into
structured ``memory_facts`` rows (names, preferences, workouts — explicit,
inspectable, deletable) and a one-line ``mood_note`` for the dashboard
timeline. Guard rails, enforced in CODE not prompt:

- categories restricted to :data:`ALLOWED_CATEGORIES`;
- any fact whose category/key/value smells biometric is dropped
  (:data:`FORBIDDEN_TOKENS`) — a reviewer must find no template store;
- no provider configured → extraction is skipped gracefully, never an error.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from meemoo.brain.types import Provider, ProviderError
from meemoo.core.models import Conversation, MemoryFact, Message

logger = logging.getLogger(__name__)

ALLOWED_CATEGORIES = frozenset({"name", "preference", "workout", "schedule", "context"})

#: Biometric-smelling tokens — facts containing these are refused (Art. V §1).
FORBIDDEN_TOKENS = frozenset(
    {"face", "facial", "voiceprint", "voice print", "biometric", "fingerprint",
     "retina", "iris scan", "embedding", "faceprint"}
)

EXTRACTION_PROMPT = """\
You extract structured memory from a conversation transcript for a companion
robot. Reply with ONLY a JSON object, no prose, shaped exactly like:
{"facts": [{"category": "...", "key": "...", "value": "..."}],
 "mood_note": "one warm sentence describing how the person seemed"}

Rules:
- category must be one of: name, preference, workout, schedule, context.
- Only include facts the person actually stated. No guesses, no inferences
  about health, and absolutely nothing about faces, voices, or biometrics.
- 0 to 6 facts. Empty list is fine."""


@dataclass(frozen=True, slots=True)
class ExtractedFact:
    category: str
    key: str
    value: str


def _clean_fact(raw: object) -> ExtractedFact | None:
    if not isinstance(raw, dict):
        return None
    category = str(raw.get("category", "")).strip().lower()
    key = str(raw.get("key", "")).strip()
    value = str(raw.get("value", "")).strip()
    if not (category and key and value) or category not in ALLOWED_CATEGORIES:
        return None
    haystack = f"{category} {key} {value}".lower()
    if any(token in haystack for token in FORBIDDEN_TOKENS):
        logger.warning("dropped biometric-smelling fact (Art. V §1)",
                       extra={"fields": {"key": key}})
        return None
    return ExtractedFact(category=category, key=key, value=value)


def parse_extraction(text: str) -> tuple[list[ExtractedFact], str | None]:
    """Parse the model's JSON; malformed output yields ([], None), never raises."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return [], None
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        logger.info("memory extraction returned non-JSON — skipped")
        return [], None
    if not isinstance(payload, dict):
        return [], None
    facts = [
        fact for fact in (_clean_fact(item) for item in payload.get("facts") or [])
        if fact is not None
    ]
    mood_raw = payload.get("mood_note")
    mood = str(mood_raw).strip() if isinstance(mood_raw, str) and mood_raw.strip() else None
    return facts, mood


def extract_from_transcript(
    provider: Provider, model: str, transcript: list[dict[str, str]]
) -> tuple[list[ExtractedFact], str | None]:
    """One reflex-tier call → validated facts + mood note. Errors → ([], None)."""
    convo = "\n".join(f"{m.get('role')}: {m.get('content')}" for m in transcript)
    try:
        response = provider.complete(
            [{"role": "user", "content": f"Transcript:\n{convo}"}],
            model, 512, system=EXTRACTION_PROMPT,
        )
    except ProviderError as exc:
        logger.info("memory extraction skipped (provider error)",
                    extra={"fields": {"reason": exc.reason}})
        return [], None
    if response.refused:
        return [], None
    return parse_extraction(response.text)


def run_post_conversation(
    db_factory: sessionmaker[DbSession],
    conversation_id: int,
    provider: Provider | None,
    model: str,
) -> int:
    """Extract + persist for one closed conversation. Returns facts written.

    No provider → 0 facts, no mood note, no error (scripted mode stays clean).
    Facts require a ``person_id`` on the conversation; without one only the
    mood note is stored (memory is person-scoped by schema).
    """
    if provider is None:
        logger.info("no provider — post-conversation extraction skipped")
        return 0
    with db_factory() as db:
        conversation = db.get(Conversation, conversation_id)
        if conversation is None:
            return 0
        rows = (
            db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.id)
            .all()
        )
        transcript = [{"role": r.role, "content": r.content} for r in rows]
    if not transcript:
        return 0
    facts, mood = extract_from_transcript(provider, model, transcript)
    with db_factory() as db:
        conversation = db.get(Conversation, conversation_id)
        if conversation is None:
            return 0
        if mood:
            conversation.mood_note = mood
        written = 0
        if conversation.person_id is not None:
            now = datetime.now(UTC).replace(tzinfo=None)
            for fact in facts:
                db.add(MemoryFact(
                    device_id=conversation.device_id,
                    person_id=conversation.person_id,
                    category=fact.category, key=fact.key, value=fact.value,
                    source_conversation_id=conversation_id, updated_at=now,
                ))
                written += 1
        db.commit()
    logger.info("post-conversation memory written",
                extra={"fields": {"conversation_id": conversation_id,
                                  "facts": written, "mood_note": bool(mood)}})
    return written


def facts_for_prompt(
    db_factory: sessionmaker[DbSession], person_id: int, limit: int = 20
) -> list[tuple[str, str, str]]:
    """Newest non-deleted facts as (category, key, value) for the system prompt."""
    with db_factory() as db:
        rows = (
            db.query(MemoryFact)
            .filter(MemoryFact.person_id == person_id, MemoryFact.deleted_at.is_(None))
            .order_by(MemoryFact.id.desc())
            .limit(limit)
            .all()
        )
    return [(r.category, r.key, r.value) for r in reversed(rows)]
