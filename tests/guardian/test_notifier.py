"""Notifier adapter tests: simulated default, Twilio request shape, factory."""

from __future__ import annotations

from meemoo.core import topics
from meemoo.core.bus import EventBus
from meemoo.core.config import Settings
from meemoo.guardian.notifier import (
    TWILIO_API,
    Notification,
    SimulatedNotifier,
    TwilioNotifier,
    make_notifier,
)


def sms(to: str = "+13125550100") -> Notification:
    return Notification(channel="sms", to=to, body="MEEMOO ALERT (L1): test", level="L1",
                        contact_name="Dana", alert_id=7)


def call(to: str = "+13125550100") -> Notification:
    return Notification(channel="call", to=to, body="This is Meemoo & a test", level="L3")


async def test_simulated_notifier_records_and_publishes(bus: EventBus) -> None:
    notifier = SimulatedNotifier(bus)
    sub = bus.subscribe(topics.NOTIFY_SENT, replay_last=False)
    result = await notifier.send(sms())
    assert result.delivered and result.provider == "simulated"
    assert notifier.sent == [sms()]
    event = await sub.get()
    assert event.payload["simulated"] is True
    assert event.payload["channel"] == "sms"
    assert event.payload["alert_id"] == 7


async def test_twilio_sms_request_shape() -> None:
    requests: list[tuple[str, dict[str, str], tuple[str, str]]] = []

    def transport(url: str, fields: dict[str, str], auth: tuple[str, str]) -> tuple[int, str]:
        requests.append((url, fields, auth))
        return 201, "{}"

    notifier = TwilioNotifier("ACxxx", "token", "+18885550000", transport=transport)
    result = await notifier.send(sms())
    assert result.delivered
    url, fields, auth = requests[0]
    assert url == f"{TWILIO_API}/Accounts/ACxxx/Messages.json"
    assert fields == {"To": "+13125550100", "From": "+18885550000",
                      "Body": "MEEMOO ALERT (L1): test"}
    assert auth == ("ACxxx", "token")


async def test_twilio_call_uses_twiml_with_escaping() -> None:
    requests: list[tuple[str, dict[str, str], tuple[str, str]]] = []

    def transport(url: str, fields: dict[str, str], auth: tuple[str, str]) -> tuple[int, str]:
        requests.append((url, fields, auth))
        return 201, "{}"

    notifier = TwilioNotifier("ACxxx", "token", "+18885550000", transport=transport)
    await notifier.send(call())
    url, fields, _ = requests[0]
    assert url == f"{TWILIO_API}/Accounts/ACxxx/Calls.json"
    assert fields["Twiml"] == "<Response><Say>This is Meemoo &amp; a test</Say></Response>"


async def test_twilio_failure_reports_not_delivered_never_raises() -> None:
    def broken(url: str, fields: dict[str, str], auth: tuple[str, str]) -> tuple[int, str]:
        raise OSError("network down")

    notifier = TwilioNotifier("ACxxx", "token", "+18885550000", transport=broken)
    result = await notifier.send(sms())
    assert not result.delivered
    assert "network down" in result.detail


async def test_twilio_http_error_reports_not_delivered() -> None:
    def rejecting(url: str, fields: dict[str, str], auth: tuple[str, str]) -> tuple[int, str]:
        return 401, '{"message": "authenticate"}'

    notifier = TwilioNotifier("ACxxx", "token", "+18885550000", transport=rejecting)
    result = await notifier.send(sms())
    assert not result.delivered and "401" in result.detail


def test_factory_without_creds_is_simulated(bus: EventBus, bare_settings: Settings) -> None:
    assert isinstance(make_notifier(bare_settings, bus), SimulatedNotifier)


def test_factory_with_creds_is_twilio(bus: EventBus, bare_settings: Settings) -> None:
    settings = bare_settings.model_copy(
        update={"twilio_account_sid": "ACxxx", "twilio_auth_token": "t",
                "twilio_from_number": "+18885550000"}
    )
    assert isinstance(make_notifier(settings, bus), TwilioNotifier)


def test_factory_with_partial_creds_is_simulated(
    bus: EventBus, bare_settings: Settings
) -> None:
    settings = bare_settings.model_copy(update={"twilio_account_sid": "ACxxx"})
    assert isinstance(make_notifier(settings, bus), SimulatedNotifier)
