/** Who Meemoo rings, in order: the escalation ladder's phone book. */

import { useCallback, useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost } from "../../lib/api";
import type { Contact } from "../../lib/types";
import { Button, Card, EmptyNote } from "../../components/ui";

export default function ContactsCard({
  onChanged,
}: {
  onChanged?: (contacts: Contact[]) => void;
}) {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [relationship, setRelationship] = useState("");
  const [note, setNote] = useState<string | null>(null);

  const refresh = useCallback(() => {
    apiGet<Contact[]>("/api/v1/devices/1/contacts")
      .then((rows) => {
        setContacts(rows);
        onChanged?.(rows);
      })
      .catch(() => setContacts([]));
  }, [onChanged]);

  useEffect(refresh, [refresh]);

  const add = async () => {
    if (!name.trim()) return;
    try {
      await apiPost(`/api/v1/devices/1/contacts`, {
        name: name.trim(),
        phone: phone.trim() || null,
        relationship_label: relationship.trim() || null,
        order_index: contacts.length,
      });
      setName("");
      setPhone("");
      setRelationship("");
      setNote(null);
      refresh();
    } catch {
      setNote("Couldn't add that person.");
    }
  };

  const remove = async (id: number) => {
    try {
      await apiDelete(`/api/v1/contacts/${id}`);
      refresh();
    } catch {
      setNote("Couldn't remove them.");
    }
  };

  return (
    <Card title="Who to ring" hint="in this order, never 911 by itself">
      {contacts.length === 0 ? (
        <EmptyNote>
          Add at least one person. When Meemoo is worried, this is who it
          rings, in order.
        </EmptyNote>
      ) : (
        <ol className="mb-4 space-y-2">
          {contacts.map((contact, index) => (
            <li
              key={contact.id}
              className="flex items-center gap-3 rounded-2xl bg-cream px-4 py-2"
            >
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-sage-soft text-sm font-semibold text-sage-deep">
                {index + 1}
              </span>
              <span className="flex-1">
                <span className="font-medium">{contact.name}</span>
                {contact.relationship_label && (
                  <span className="text-ink-faint"> · {contact.relationship_label}</span>
                )}
                {contact.phone && (
                  <span className="block text-sm text-ink-faint">{contact.phone}</span>
                )}
              </span>
              <button
                type="button"
                onClick={() => void remove(contact.id)}
                className="text-sm text-rose transition hover:underline"
              >
                remove
              </button>
            </li>
          ))}
        </ol>
      )}
      <form
        className="flex flex-wrap gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          void add();
        }}
      >
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Name"
          className="min-w-0 flex-1 rounded-full border border-line bg-card px-4 py-2 text-sm outline-none focus:border-sage"
        />
        <input
          value={relationship}
          onChange={(event) => setRelationship(event.target.value)}
          placeholder="daughter, nurse…"
          className="w-36 rounded-full border border-line bg-card px-4 py-2 text-sm outline-none focus:border-sage"
        />
        <input
          value={phone}
          onChange={(event) => setPhone(event.target.value)}
          placeholder="Phone (optional)"
          className="w-40 rounded-full border border-line bg-card px-4 py-2 text-sm outline-none focus:border-sage"
        />
        <Button type="submit" kind="soft" disabled={!name.trim()}>
          Add
        </Button>
      </form>
      {note && <p className="mt-2 text-sm text-rose">{note}</p>}
    </Card>
  );
}
