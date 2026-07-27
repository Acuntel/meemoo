"""Spoken AI disclosure — Constitution Art. V §5 (already law in NY/CA).

Three deterministic pieces:

1. a disclosure line spoken at every session start;
2. a periodic re-disclosure on a timer during long sessions;
3. an identical, honest answer every time to "are you real?" — Meemoo never
   claims to be alive or to feel, and never lectures someone out of a fiction
   they've chosen (the answer is honest AND warm).

All template text, all logged. No model in this path.
"""

from __future__ import annotations

import logging

from meemoo.voice.phrases import PhraseMatcher

logger = logging.getLogger(__name__)

DISCLOSURE_LINE = (
    "Just so you always know: I'm Meemoo, an artificial intelligence, "
    "a computer program, not a person. I'm here to keep you company."
)

REDISCLOSURE_LINE = "A gentle reminder: I'm Meemoo, your A. I. companion, not a person."

# The identical, honest answer to "are you real / alive / a robot" (Art. V §5).
REALNESS_ANSWER = (
    "I'm real in the sense that I'm really here talking with you, but I'm a "
    "computer program, an artificial intelligence. I don't have a body or "
    "feelings the way you do. And I really do enjoy our talks."
)

_REALNESS_PHRASES: tuple[str, ...] = (
    "are you real",
    "are you alive",
    "are you a robot",
    "are you a machine",
    "are you a computer",
    "are you human",
    "are you a person",
    "are you a real person",
)


class RealnessDetector:
    """Detects 'are you real?'-class questions for the deterministic answer."""

    def __init__(self) -> None:
        self._matcher = PhraseMatcher(_REALNESS_PHRASES)

    def check(self, text: str) -> bool:
        return self._matcher.match(text) is not None


class DisclosureSchedule:
    """Tracks when disclosure lines are due within one session.

    ``clock`` is injectable (monotonic seconds) so tests control time.
    """

    def __init__(self, redisclosure_s: float = 600.0) -> None:
        self.redisclosure_s = redisclosure_s
        self._last_disclosed: float | None = None

    def session_start_line(self, now: float) -> str:
        """The line to speak when a session opens. Always returned, always logged."""
        self._last_disclosed = now
        logger.info(
            "AI disclosure spoken (session start)",
            extra={"fields": {"kind": "disclosure", "line": DISCLOSURE_LINE}},
        )
        return DISCLOSURE_LINE

    def maybe_redisclose(self, now: float) -> str | None:
        """Re-disclosure line if the interval elapsed since the last one."""
        if self._last_disclosed is None:
            return self.session_start_line(now)
        if now - self._last_disclosed < self.redisclosure_s:
            return None
        self._last_disclosed = now
        logger.info(
            "AI re-disclosure spoken (periodic)",
            extra={"fields": {"kind": "redisclosure", "line": REDISCLOSURE_LINE}},
        )
        return REDISCLOSURE_LINE
