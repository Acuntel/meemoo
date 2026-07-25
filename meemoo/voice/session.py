"""Conversation sessions: rolling context, 45 s silence close, transcripts.

Constitution Art. V §2: transcript storage defaults ON with a per-device
toggle (``Device.store_transcripts``); raw audio is NEVER retained after
transcription (sessions store text only — there is no audio field anywhere in
this module, by design). Persistence is optional: with no DB session factory
the manager runs memory-only and nothing crashes (Art. IX §3).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from meemoo.core import topics
from meemoo.core.bus import EventBus
from meemoo.core.models import Conversation, Device, Message
from meemoo.voice.disclosure import DisclosureSchedule

logger = logging.getLogger(__name__)

ROLLING_CONTEXT_MAX = 40  # messages kept in the in-memory rolling context


@dataclass(slots=True)
class ConversationSession:
    """One live voice session (text only — never audio)."""

    device_id: int
    trigger: str  # "ptt" | "wake" | "checkin" | "demo"
    person_id: int | None = None
    opened_at: float = 0.0  # monotonic
    last_activity: float = 0.0  # monotonic
    store_transcripts: bool = True
    conversation_row_id: int | None = None
    context: list[dict[str, str]] = field(default_factory=list)
    closed: bool = False

    def add(self, role: str, text: str, now: float) -> None:
        self.context.append({"role": role, "content": text})
        if len(self.context) > ROLLING_CONTEXT_MAX:
            del self.context[: len(self.context) - ROLLING_CONTEXT_MAX]
        self.last_activity = now


class SessionManager:
    """Opens/closes sessions, persists transcripts, speaks disclosures.

    ``clock`` is injectable (monotonic seconds) so tests control the 45 s
    silence-close and the re-disclosure timer.
    """

    def __init__(
        self,
        bus: EventBus,
        db_factory: sessionmaker[DbSession] | None = None,
        *,
        silence_close_s: float = 45.0,
        disclosure: DisclosureSchedule | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._bus = bus
        self._db_factory = db_factory
        self._silence_close_s = silence_close_s
        self._disclosure = disclosure or DisclosureSchedule()
        self._clock: Callable[[], float] = clock or time.monotonic
        self.active: ConversationSession | None = None

    # ------------------------------------------------------------- lifecycle
    async def open(
        self, device_id: int, trigger: str, person_id: int | None = None
    ) -> tuple[ConversationSession, str]:
        """Open a session; returns it plus the AI-disclosure line to speak."""
        if self.active is not None and not self.active.closed:
            await self.close(reason="superseded")
        now = self._clock()
        session = ConversationSession(
            device_id=device_id,
            trigger=trigger,
            person_id=person_id,
            opened_at=now,
            last_activity=now,
            store_transcripts=self._device_stores_transcripts(device_id),
        )
        if session.store_transcripts:
            session.conversation_row_id = self._persist_open(session)
        self.active = session
        logger.info(
            "voice session opened",
            extra={"fields": {"device_id": device_id, "trigger": trigger,
                              "store_transcripts": session.store_transcripts}},
        )
        await self._bus.publish(
            topics.VOICE_SESSION_OPENED,
            {"device_id": device_id, "trigger": trigger,
             "conversation_id": session.conversation_row_id},
        )
        line = self._disclosure.session_start_line(now)
        session.add("assistant", line, now)
        self._persist_message(session, "assistant", line)
        return session, line

    async def close(self, reason: str = "silence") -> None:
        session = self.active
        if session is None or session.closed:
            return
        session.closed = True
        self.active = None
        if session.conversation_row_id is not None and self._db_factory is not None:
            with self._db_factory() as db:
                row = db.get(Conversation, session.conversation_row_id)
                if row is not None:
                    row.ended_at = datetime.now(UTC).replace(tzinfo=None)
                    db.commit()
        logger.info(
            "voice session closed",
            extra={"fields": {"device_id": session.device_id, "reason": reason,
                              "messages": len(session.context)}},
        )
        await self._bus.publish(
            topics.VOICE_SESSION_CLOSED,
            {"device_id": session.device_id, "reason": reason,
             "conversation_id": session.conversation_row_id},
        )

    async def tick(self) -> str | None:
        """Periodic housekeeping: silence-close + periodic re-disclosure.

        Returns a re-disclosure line to speak, if one is due."""
        session = self.active
        if session is None:
            return None
        now = self._clock()
        if now - session.last_activity >= self._silence_close_s:
            await self.close(reason="silence")
            return None
        line = self._disclosure.maybe_redisclose(now)
        if line is not None:
            session.add("assistant", line, session.last_activity)  # not user activity
            self._persist_message(session, "assistant", line)
        return line

    # -------------------------------------------------------------- messages
    def add_user(self, text: str) -> None:
        self._add("user", text)

    def add_assistant(self, text: str) -> None:
        self._add("assistant", text)

    def _add(self, role: str, text: str) -> None:
        session = self.active
        if session is None:
            return
        session.add(role, text, self._clock())
        self._persist_message(session, role, text)

    # ----------------------------------------------------------- persistence
    def _device_stores_transcripts(self, device_id: int) -> bool:
        """Per-device toggle; default ON (Art. V §2) when no DB/row exists."""
        if self._db_factory is None:
            return True
        with self._db_factory() as db:
            device = db.get(Device, device_id)
            return True if device is None else bool(device.store_transcripts)

    def _persist_open(self, session: ConversationSession) -> int | None:
        if self._db_factory is None:
            return None
        with self._db_factory() as db:
            row = Conversation(device_id=session.device_id, person_id=session.person_id)
            db.add(row)
            db.commit()
            return int(row.id)

    def _persist_message(self, session: ConversationSession, role: str, text: str) -> None:
        if (
            self._db_factory is None
            or not session.store_transcripts
            or session.conversation_row_id is None
        ):
            return
        with self._db_factory() as db:
            db.add(Message(conversation_id=session.conversation_row_id, role=role, content=text))
            db.commit()
