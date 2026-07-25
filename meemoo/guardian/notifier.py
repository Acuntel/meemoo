"""Notifier adapter: how escalation reaches humans (Constitution Art. III §3).

Two implementations behind one protocol:

- :class:`SimulatedNotifier` — the zero-credential default. Publishes
  ``notify.sent`` (``simulated: True``) on the bus, which drives the fake
  incoming-call screen in the web UI (Phase 7). Never needs network.
- :class:`TwilioNotifier` — DEMO ONLY, sanctioned exception in Art. III §3.
  Talks to the Twilio REST API over stdlib HTTP (no SDK dependency), the same
  pattern as Brady's Paradise call bot. ROADMAP (not optional): replace with
  our own telephony path — a SIP trunk + self-hosted dialer (e.g.
  Asterisk/FreeSWITCH behind this same protocol); the adapter boundary here
  is that replacement seam.

Missing credentials NEVER crash anything (Art. IX §3): the factory silently
returns the simulated implementation, and TwilioNotifier itself reports
delivery failure instead of raising.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol
from xml.sax.saxutils import escape

from meemoo.core import topics
from meemoo.core.bus import EventBus
from meemoo.core.config import Settings

logger = logging.getLogger(__name__)

Channel = Literal["sms", "call"]
# transport(url, form_fields, (user, password)) -> (http_status, response_body)
Transport = Callable[[str, dict[str, str], tuple[str, str]], tuple[int, str]]

TWILIO_API = "https://api.twilio.com/2010-04-01"


@dataclass(frozen=True)
class Notification:
    """One outbound SMS or call request."""

    channel: Channel
    to: str
    body: str
    level: str  # "L1" | "L2" | "L3"
    contact_name: str | None = None
    alert_id: int | None = None


@dataclass(frozen=True)
class NotifyResult:
    delivered: bool
    provider: str
    detail: str = ""


class Notifier(Protocol):
    """Escalation delivery adapter — swap implementations, never call sites."""

    name: str

    async def send(self, notification: Notification) -> NotifyResult: ...


class SimulatedNotifier:
    """Records + publishes every notification; drives the fake call screen."""

    name = "simulated"

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self.sent: list[Notification] = []

    async def send(self, notification: Notification) -> NotifyResult:
        self.sent.append(notification)
        await self._bus.publish(
            topics.NOTIFY_SENT,
            {
                "simulated": True,
                "channel": notification.channel,
                "to": notification.to,
                "body": notification.body,
                "level": notification.level,
                "contact_name": notification.contact_name,
                "alert_id": notification.alert_id,
            },
        )
        logger.info(
            "simulated notification",
            extra={"fields": {"channel": notification.channel, "to": notification.to,
                              "level": notification.level}},
        )
        return NotifyResult(delivered=True, provider=self.name, detail="simulated")


def _urllib_post(url: str, fields: dict[str, str], auth: tuple[str, str]) -> tuple[int, str]:
    """Blocking HTTPS form POST with basic auth (stdlib only)."""
    data = urllib.parse.urlencode(fields).encode()
    token = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
    request = urllib.request.Request(
        url, data=data, headers={"Authorization": f"Basic {token}"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
        return int(response.status), response.read().decode("utf-8", "replace")


class TwilioNotifier:
    """Twilio REST over stdlib HTTP — demo calls only (Art. III §3)."""

    name = "twilio"

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str,
        *,
        transport: Transport = _urllib_post,
    ) -> None:
        self._sid = account_sid
        self._auth = (account_sid, auth_token)
        self._from = from_number
        self._transport = transport

    def _request_for(self, notification: Notification) -> tuple[str, dict[str, str]]:
        if notification.channel == "sms":
            url = f"{TWILIO_API}/Accounts/{self._sid}/Messages.json"
            fields = {"To": notification.to, "From": self._from, "Body": notification.body}
        else:
            url = f"{TWILIO_API}/Accounts/{self._sid}/Calls.json"
            twiml = f"<Response><Say>{escape(notification.body)}</Say></Response>"
            fields = {"To": notification.to, "From": self._from, "Twiml": twiml}
        return url, fields

    async def send(self, notification: Notification) -> NotifyResult:
        url, fields = self._request_for(notification)
        try:
            status, body = await asyncio.to_thread(self._transport, url, fields, self._auth)
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            logger.warning(
                "twilio delivery failed",
                extra={"fields": {"channel": notification.channel, "error": str(exc)}},
            )
            return NotifyResult(delivered=False, provider=self.name, detail=str(exc))
        delivered = 200 <= status < 300
        if not delivered:
            logger.warning(
                "twilio rejected notification",
                extra={"fields": {"status": status, "body": body[:200]}},
            )
        return NotifyResult(delivered=delivered, provider=self.name, detail=f"http {status}")


def make_notifier(settings: Settings, bus: EventBus) -> SimulatedNotifier | TwilioNotifier:
    """Twilio when fully configured, simulated otherwise. Never crashes."""
    if settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_from_number:
        logger.info("notifier: twilio (demo-only per Art. III §3)")
        return TwilioNotifier(
            settings.twilio_account_sid,
            settings.twilio_auth_token,
            settings.twilio_from_number,
        )
    logger.info("notifier: simulated (no Twilio credentials — normal for dev)")
    return SimulatedNotifier(bus)
