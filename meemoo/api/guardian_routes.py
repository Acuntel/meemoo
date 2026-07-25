"""Guardian REST: contacts CRUD, alerts + acknowledge, false-alarm counter,
and the Twilio inbound-SMS webhook (reply "ACK" halts escalation).

Acknowledgment goes to the DB first (the durable record: who/when/latency)
and then to the live GuardianService if one is registered — halting the
machine. With no live service (API-only process) the ack still persists and
the counter/audit stay correct (Art. IX §3).
"""

from __future__ import annotations

import logging
from typing import Annotated
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from meemoo.api.deps import get_db
from meemoo.core.models import Alert
from meemoo.guardian import contacts as contacts_crud
from meemoo.guardian import escalation
from meemoo.guardian.contacts import ContactInput
from meemoo.guardian.registry import get_active_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["guardian"])

ACK_WORDS = frozenset({"ack", "ok", "okay", "yes", "acknowledged", "got it", "1"})


class ContactBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str | None = None
    relationship_label: str | None = None
    order_index: int = 0
    notify_sms: bool = True
    notify_call: bool = True
    person_id: int | None = None

    def to_input(self) -> ContactInput:
        return ContactInput(
            name=self.name,
            phone=self.phone,
            relationship_label=self.relationship_label,
            order_index=self.order_index,
            notify_sms=self.notify_sms,
            notify_call=self.notify_call,
            person_id=self.person_id,
        )


class ContactOut(ContactBody):
    id: int
    device_id: int


class AlertOut(BaseModel):
    id: int
    device_id: int
    level: str
    state: str
    reason: str
    opened_at: str
    acknowledged_at: str | None
    acknowledged_by_contact_id: int | None
    evidence_event_id: int | None


class AckBody(BaseModel):
    contact_id: int | None = None
    via: str = "dashboard"


def _contact_out(row: object) -> ContactOut:
    return ContactOut.model_validate(row, from_attributes=True)


# ------------------------------------------------------------------ contacts
@router.get("/devices/{device_id}/contacts")
def get_contacts(device_id: int, db: Annotated[Session, Depends(get_db)]) -> list[ContactOut]:
    return [_contact_out(c) for c in contacts_crud.list_contacts(db, device_id)]


@router.post("/devices/{device_id}/contacts", status_code=201)
def post_contact(
    device_id: int, body: ContactBody, db: Annotated[Session, Depends(get_db)]
) -> ContactOut:
    return _contact_out(contacts_crud.create_contact(db, device_id, body.to_input()))


@router.put("/contacts/{contact_id}")
def put_contact(
    contact_id: int, body: ContactBody, db: Annotated[Session, Depends(get_db)]
) -> ContactOut:
    row = contacts_crud.update_contact(db, contact_id, body.to_input())
    if row is None:
        raise HTTPException(status_code=404, detail="contact not found")
    return _contact_out(row)


@router.delete("/contacts/{contact_id}", status_code=204)
def remove_contact(contact_id: int, db: Annotated[Session, Depends(get_db)]) -> Response:
    if not contacts_crud.delete_contact(db, contact_id):
        raise HTTPException(status_code=404, detail="contact not found")
    return Response(status_code=204)


# -------------------------------------------------------------------- alerts
@router.get("/alerts")
def get_alerts(
    db: Annotated[Session, Depends(get_db)], device_id: int | None = None
) -> list[AlertOut]:
    query = db.query(Alert).order_by(Alert.id.desc())
    if device_id is not None:
        query = query.filter(Alert.device_id == device_id)
    return [
        AlertOut(
            id=a.id, device_id=a.device_id, level=a.level, state=a.state,
            reason=a.reason, opened_at=a.opened_at.isoformat(),
            acknowledged_at=a.acknowledged_at.isoformat() if a.acknowledged_at else None,
            acknowledged_by_contact_id=a.acknowledged_by_contact_id,
            evidence_event_id=a.evidence_event_id,
        )
        for a in query.limit(100).all()
    ]


@router.post("/alerts/{alert_id}/ack")
async def ack_alert(
    alert_id: int, body: AckBody, db: Annotated[Session, Depends(get_db)]
) -> dict[str, object]:
    alert, latency = escalation.ack_alert(
        db, alert_id, contact_id=body.contact_id, via=body.via
    )
    if alert is None:
        raise HTTPException(status_code=404, detail="alert not found")
    machine_state: str | None = None
    service = get_active_service()
    if service is not None:
        result = await service.acknowledge(
            alert_id, contact_id=body.contact_id, via=body.via
        )
        machine_state = str(result["state"])
    return {
        "alert_id": alert.id,
        "state": alert.state,
        "latency_s": latency,
        "machine_state": machine_state,
    }


@router.get("/metrics/false-alarms")
def get_false_alarms(
    db: Annotated[Session, Depends(get_db)], device_id: int | None = None
) -> dict[str, object]:
    """The published headline number (Constitution Art. VIII §3)."""
    return {
        "false_alarms_last_7_days": escalation.false_alarms_per_week(db, device_id),
        "window_days": 7,
    }


# ------------------------------------------------------------- twilio inbound
@router.post("/twilio/sms")
async def twilio_inbound_sms(request: Request, db: Annotated[Session, Depends(get_db)]) -> Response:
    """Twilio SMS webhook: an ack keyword from a known contact halts escalation.

    Parses application/x-www-form-urlencoded with stdlib ``parse_qs`` (no
    python-multipart dependency). Unknown senders / non-ack bodies are logged
    and ignored.
    """
    raw = (await request.body()).decode("utf-8", "replace")
    form = {key: values[0] for key, values in parse_qs(raw).items()}
    sender = form.get("From", "")
    body = form.get("Body", "").strip().lower()
    reply = "Meemoo: message received."
    if body in ACK_WORDS:
        contact = contacts_crud.find_contact_by_phone(db, sender)
        if contact is not None:
            alert = escalation.latest_open_alert(db, contact.device_id)
            if alert is not None:
                escalation.ack_alert(db, alert.id, contact_id=contact.id, via="sms")
                service = get_active_service()
                if service is not None and service.device_id == contact.device_id:
                    await service.acknowledge(alert.id, contact_id=contact.id, via="sms")
                reply = f"Meemoo: acknowledged by {contact.name}. Escalation halted."
                logger.info(
                    "sms acknowledgment",
                    extra={"fields": {"contact_id": contact.id, "alert_id": alert.id}},
                )
            else:
                reply = "Meemoo: no open alert to acknowledge."
        else:
            logger.warning("sms ack from unknown number", extra={"fields": {"from": sender}})
    twiml = f"<?xml version='1.0' encoding='UTF-8'?><Response><Message>{reply}</Message></Response>"
    return Response(content=twiml, media_type="application/xml")
