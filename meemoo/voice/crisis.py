"""988 crisis protocol — deterministic, logged, no LLM (Constitution Art. V §5).

NY/CA AI-companion law (and our own constitution) requires a published crisis
protocol: when a user expresses self-harm intent, Meemoo responds with a fixed,
reviewed template that points to the 988 Suicide & Crisis Lifeline — never a
generated reply — and the event is logged and published for Guardian.

Detection is the same pure phrase matcher as the distress bypass: local,
offline, inspectable. Recall over precision — a gentle unnecessary check-in
costs little; a miss is unacceptable.
"""

from __future__ import annotations

import logging

from meemoo.core import topics
from meemoo.core.bus import EventBus
from meemoo.core.logging import escalation_extra
from meemoo.voice.phrases import PhraseMatch, PhraseMatcher

logger = logging.getLogger(__name__)

CRISIS_PHRASES: tuple[str, ...] = (
    "kill myself",
    "killing myself",
    "want to die",
    "i want to die",
    "wish i was dead",
    "wish i were dead",
    "end my life",
    "end it all",
    "hurt myself",
    "harm myself",
    "suicide",
    "suicidal",
    "no reason to live",
    "better off dead",
    "don't want to be here anymore",
    "dont want to be here anymore",
)

# The reviewed, fixed response. Same words every time — deterministic by design.
CRISIS_RESPONSE = (
    "I'm really glad you told me, and I'm taking it seriously. "
    "You matter, and you don't have to carry this alone. "
    "You can call or text 9 8 8, the Suicide and Crisis Lifeline, any time, "
    "day or night, and talk with a real person who wants to help. "
    "Would you like me to let one of your people know you could use some company?"
)


class CrisisDetector:
    """Local self-harm phrase detector. No network, no model, no API key."""

    def __init__(self) -> None:
        self._matcher = PhraseMatcher(CRISIS_PHRASES)

    def check(self, text: str) -> PhraseMatch | None:
        return self._matcher.match(text)


async def publish_crisis(
    bus: EventBus,
    match: PhraseMatch,
    *,
    transcript: str,
    device_id: int | None = None,
    conversation_id: int | None = None,
) -> None:
    """Publish ``utterance.crisis`` and log with escalation version stamps."""
    payload: dict[str, object] = {
        "phrase": match.phrase,
        "matched_text": match.matched_text,
        "transcript": transcript,
        "device_id": device_id,
        "conversation_id": conversation_id,
        "source": "voice.crisis",
        "protocol": "988",
    }
    logger.warning(
        "CRISIS phrase detected — 988 protocol response",
        extra=escalation_extra(**payload),
    )
    await bus.publish(topics.CRISIS_HEARD, payload)
