/** History: conversations (summary first for longer chats, Amendment A7),
 * detections, earlier alerts, and CSV export. */

import { useEffect, useState } from "react";
import { EarlierAlertsCard } from "../components/AlertCards";
import { apiGet, fmtDay, fmtTime } from "../lib/api";
import type { ApiEvent, Conversation, Message } from "../lib/types";
import { Card, Chip, EmptyNote } from "../components/ui";

const EXPORT_TABLES = ["events", "conversations", "alerts", "usage"] as const;

function durationSeconds(chat: Conversation): number | null {
  if (chat.ended_at === null) return null;
  const seconds =
    (new Date(chat.ended_at).getTime() - new Date(chat.started_at).getTime()) /
    1000;
  return Number.isFinite(seconds) && seconds >= 0 ? seconds : null;
}

/** Summary line: the brain's mood note when it exists, otherwise a plain
 * template from the metadata we actually have. Never invented content. */
function summaryText(chat: Conversation): string {
  if (chat.mood_note !== null && chat.mood_note.trim() !== "") {
    return chat.mood_note;
  }
  const seconds = durationSeconds(chat);
  const opener =
    chat.trigger === "checkin"
      ? "Meemoo checked in"
      : "They started the chat";
  if (seconds === null) {
    return `${opener}. ${chat.message_count} turns. No note was written for this one.`;
  }
  const minutes = Math.max(1, Math.round(seconds / 60));
  return `${opener} and they talked for about ${minutes} minute${
    minutes === 1 ? "" : "s"
  } (${chat.message_count} turns). No note was written for this one.`;
}

function Transcript({ messages }: { messages: Message[] }) {
  if (messages.length === 0) {
    return <p className="text-sm text-ink-faint">Loading…</p>;
  }
  return (
    <>
      {messages.map((message) => (
        <p key={message.id} className="text-sm">
          <span className="font-semibold">
            {message.role === "assistant" ? "Meemoo" : "Them"}:
          </span>{" "}
          {message.content}
        </p>
      ))}
    </>
  );
}

export default function HistoryPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [detections, setDetections] = useState<ApiEvent[]>([]);
  const [openId, setOpenId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Record<number, Message[]>>({});

  useEffect(() => {
    apiGet<Conversation[]>("/api/v1/conversations?device_id=1&limit=50")
      .then(setConversations)
      .catch(() => setConversations([]));
    apiGet<ApiEvent[]>("/api/v1/events?device_id=1&type_prefix=person.&limit=50")
      .then(setDetections)
      .catch(() => setDetections([]));
  }, []);

  const toggle = (id: number) => {
    if (openId === id) {
      setOpenId(null);
      return;
    }
    setOpenId(id);
    if (!(id in messages)) {
      apiGet<Message[]>(`/api/v1/conversations/${id}/messages`)
        .then((rows) => setMessages((prev) => ({ ...prev, [id]: rows })))
        .catch(() => undefined);
    }
  };

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <Card className="lg:col-span-2" title="Conversations">
        {conversations.length === 0 ? (
          <EmptyNote>
            No conversations stored yet, or transcript storage is switched off
            in the Studio&apos;s privacy panel.
          </EmptyNote>
        ) : (
          <ul className="divide-y divide-line">
            {conversations.map((chat) => {
              const seconds = durationSeconds(chat);
              const longChat = seconds !== null && seconds > 60;
              return (
                <li key={chat.id} className="py-3">
                  <button
                    type="button"
                    onClick={() => toggle(chat.id)}
                    className="flex w-full flex-wrap items-center gap-3 text-left"
                  >
                    <span className="text-sm text-ink-faint">
                      {fmtDay(chat.started_at)} {fmtTime(chat.started_at)}
                    </span>
                    <Chip tone={chat.trigger === "checkin" ? "sky" : "sage"}>
                      {chat.trigger === "checkin"
                        ? "check-in"
                        : "they started it"}
                    </Chip>
                    <span className="flex-1 truncate text-sm">
                      {chat.mood_note ?? `${chat.message_count} turns`}
                    </span>
                    <span className="text-ink-faint">
                      {openId === chat.id ? "▴" : "▾"}
                    </span>
                  </button>
                  {openId === chat.id && (
                    <div className="mt-3 space-y-2 rounded-2xl bg-cream p-3">
                      {longChat ? (
                        <>
                          <p className="text-sm">
                            <span className="font-semibold">In short:</span>{" "}
                            {summaryText(chat)}
                          </p>
                          <details>
                            <summary className="cursor-pointer text-sm font-medium text-ink-soft">
                              Read the whole conversation
                            </summary>
                            <div className="mt-2 space-y-2 border-t border-line pt-2">
                              <Transcript messages={messages[chat.id] ?? []} />
                            </div>
                          </details>
                        </>
                      ) : (
                        <Transcript messages={messages[chat.id] ?? []} />
                      )}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      <div className="space-y-6">
        <Card title="Detections">
          {detections.length === 0 ? (
            <EmptyNote>No detections. Good news.</EmptyNote>
          ) : (
            <ul className="space-y-2">
              {detections.map((event) => (
                <li key={event.id} className="flex items-baseline gap-2 text-sm">
                  <span className="h-2 w-2 shrink-0 rounded-full bg-rose" />
                  <span className="flex-1">
                    {event.type.replace(/[._]/g, " ")}
                  </span>
                  <span className="text-ink-faint">{fmtDay(event.ts)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <EarlierAlertsCard />

        <Card title="Export data" hint="CSV, one click">
          <div className="flex flex-wrap gap-2">
            {EXPORT_TABLES.map((table) => (
              <a
                key={table}
                href={`/api/v1/export?table=${table}&device_id=1`}
                download
                className="rounded-full bg-sky-soft px-4 py-2 text-sm font-medium text-ink-soft transition hover:bg-sky/40"
              >
                {table}.csv
              </a>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
