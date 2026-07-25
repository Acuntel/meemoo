"""Post-conversation memory: extraction, biometric refusal, mood note."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from meemoo.brain.memory import (
    facts_for_prompt,
    parse_extraction,
    run_post_conversation,
)
from meemoo.brain.types import CompletionResponse, Messages, Provider
from meemoo.core.models import Conversation, MemoryFact, Message


class CannedProvider(Provider):
    """Returns a fixed payload — stands in for the reflex-tier model."""

    name = "canned"
    requires_key = False

    def __init__(self, payload: str) -> None:
        super().__init__()
        self._payload = payload

    def complete(
        self, messages: Messages, model: str, max_tokens: int, *, system: str | None = None
    ) -> CompletionResponse:
        return CompletionResponse(text=self._payload, provider=self.name, model=model)


GOOD_PAYLOAD = json.dumps({
    "facts": [
        {"category": "preference", "key": "favorite flower", "value": "roses"},
        {"category": "workout", "key": "last walk", "value": "20 minutes on Tuesday"},
        {"category": "biometric", "key": "face", "value": "template"},  # refused: category
        {"category": "context", "key": "voiceprint sample", "value": "x"},  # refused: key
        {"category": "diagnosis", "key": "health", "value": "y"},  # refused: category
    ],
    "mood_note": "Ruth seemed cheerful and talked about her garden.",
})


def test_parse_extraction_validates_and_drops_biometrics() -> None:
    facts, mood = parse_extraction(f"Sure! Here you go: {GOOD_PAYLOAD}")
    assert [(f.category, f.key) for f in facts] == [
        ("preference", "favorite flower"), ("workout", "last walk"),
    ]
    assert mood is not None and "cheerful" in mood


def test_parse_extraction_garbage_is_empty_not_crash() -> None:
    assert parse_extraction("I couldn't do that") == ([], None)
    assert parse_extraction("{not json") == ([], None)
    assert parse_extraction("[]") == ([], None)


def _make_conversation(
    db_factory: sessionmaker[DbSession], device_id: int, person_id: int | None
) -> int:
    with db_factory() as db:
        conversation = Conversation(device_id=device_id, person_id=person_id)
        db.add(conversation)
        db.flush()
        db.add(Message(conversation_id=conversation.id, role="user",
                       content="I love roses and I walked twenty minutes"))
        db.add(Message(conversation_id=conversation.id, role="assistant",
                       content="That sounds lovely, Ruth."))
        db.commit()
        return int(conversation.id)


def test_run_post_conversation_persists_facts_and_mood(
    db_factory: sessionmaker[DbSession], seeded: tuple[int, int]
) -> None:
    device_id, person_id = seeded
    conversation_id = _make_conversation(db_factory, device_id, person_id)
    written = run_post_conversation(
        db_factory, conversation_id, CannedProvider(GOOD_PAYLOAD), "fake-model"
    )
    assert written == 2
    with db_factory() as db:
        facts = db.query(MemoryFact).all()
        assert {f.category for f in facts} == {"preference", "workout"}
        assert all(f.source_conversation_id == conversation_id for f in facts)
        conversation = db.get(Conversation, conversation_id)
        assert conversation is not None and conversation.mood_note is not None
    # facts_for_prompt returns them for the next system prompt
    triples = facts_for_prompt(db_factory, person_id)
    assert ("preference", "favorite flower", "roses") in triples


def test_run_post_conversation_without_provider_skips_gracefully(
    db_factory: sessionmaker[DbSession], seeded: tuple[int, int]
) -> None:
    device_id, person_id = seeded
    conversation_id = _make_conversation(db_factory, device_id, person_id)
    assert run_post_conversation(db_factory, conversation_id, None, "any") == 0
    with db_factory() as db:
        assert db.query(MemoryFact).count() == 0


def test_no_person_id_stores_mood_but_no_facts(
    db_factory: sessionmaker[DbSession], seeded: tuple[int, int]
) -> None:
    device_id, _ = seeded
    conversation_id = _make_conversation(db_factory, device_id, None)
    written = run_post_conversation(
        db_factory, conversation_id, CannedProvider(GOOD_PAYLOAD), "fake-model"
    )
    assert written == 0
    with db_factory() as db:
        conversation = db.get(Conversation, conversation_id)
        assert conversation is not None and conversation.mood_note is not None


def test_deleted_facts_never_reach_the_prompt(
    db_factory: sessionmaker[DbSession], seeded: tuple[int, int]
) -> None:
    from datetime import UTC, datetime

    device_id, person_id = seeded
    with db_factory() as db:
        db.add(MemoryFact(device_id=device_id, person_id=person_id,
                          category="preference", key="kept", value="v"))
        db.add(MemoryFact(device_id=device_id, person_id=person_id,
                          category="preference", key="forgotten", value="v",
                          deleted_at=datetime.now(UTC).replace(tzinfo=None)))
        db.commit()
    keys = [key for _, key, _ in facts_for_prompt(db_factory, person_id)]
    assert "kept" in keys and "forgotten" not in keys
