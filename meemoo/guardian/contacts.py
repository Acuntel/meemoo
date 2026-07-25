"""Contacts CRUD — the ordered escalation ladder (MASTER_PROMPT §4).

Pure DB helpers over the ``contacts`` table; the REST layer (api/guardian
routes) and the escalation fan-out both go through here. Ordering is
``order_index`` ascending: L1 notifies the primary (first) contact, L2
notifies everyone after it.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from meemoo.core.models import Contact


@dataclass(frozen=True)
class ContactInput:
    """Creation/update payload (API-facing shape)."""

    name: str
    phone: str | None = None
    relationship_label: str | None = None
    order_index: int = 0
    notify_sms: bool = True
    notify_call: bool = True
    person_id: int | None = None


def list_contacts(db: Session, device_id: int) -> list[Contact]:
    """All contacts for a device, escalation order (order_index, then id)."""
    return list(
        db.query(Contact)
        .filter(Contact.device_id == device_id)
        .order_by(Contact.order_index.asc(), Contact.id.asc())
        .all()
    )


def create_contact(db: Session, device_id: int, data: ContactInput) -> Contact:
    contact = Contact(
        device_id=device_id,
        person_id=data.person_id,
        name=data.name,
        phone=data.phone,
        relationship_label=data.relationship_label,
        order_index=data.order_index,
        notify_sms=data.notify_sms,
        notify_call=data.notify_call,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def update_contact(db: Session, contact_id: int, data: ContactInput) -> Contact | None:
    contact = db.get(Contact, contact_id)
    if contact is None:
        return None
    contact.name = data.name
    contact.phone = data.phone
    contact.relationship_label = data.relationship_label
    contact.order_index = data.order_index
    contact.notify_sms = data.notify_sms
    contact.notify_call = data.notify_call
    contact.person_id = data.person_id
    db.commit()
    db.refresh(contact)
    return contact


def delete_contact(db: Session, contact_id: int) -> bool:
    contact = db.get(Contact, contact_id)
    if contact is None:
        return False
    db.delete(contact)
    db.commit()
    return True


def _digits(phone: str) -> str:
    return "".join(ch for ch in phone if ch.isdigit())


def find_contact_by_phone(db: Session, phone: str) -> Contact | None:
    """Match a contact by phone number, ignoring formatting (+1, dashes)."""
    wanted = _digits(phone)
    if not wanted:
        return None
    for contact in db.query(Contact).filter(Contact.phone.isnot(None)).all():
        have = _digits(contact.phone or "")
        if have and (have == wanted or have[-10:] == wanted[-10:]):
            return contact
    return None
