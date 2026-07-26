/** History — conversations (when stored), detections, and the cost meter. */

import { useEffect, useState } from "react";
import { Bars } from "../components/Chart";
import { apiGet, fmtDay, fmtTime } from "../lib/api";
import type { ApiEvent, Conversation, Message, UsageInfo } from "../lib/types";
import { Card, Chip, EmptyNote } from "../components/ui";

const EXPORT_TABLES = ["events", "conversations", "alerts", "usage"] as const;

export default function HistoryPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [detections, setDetections] = useState<ApiEvent[]>([]);
  const [usage, setUsage] = useState<UsageInfo | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Record<number, Message[]>>({});

  useEffect(() => {
    apiGet<Conversation[]>("/api/v1/conversations?device_id=1&limit=50")
      .then(setConversations)
      .catch(() => setConversations([]));
    apiGet<ApiEvent[]>("/api/v1/events?device_id=1&type_prefix=person.&limit=50")
      .then(setDetections)
      .catch(() => setDetections([]));
    apiGet<UsageInfo>("/api/v1/devices/1/usage")
      .then(setUsage)
      .catch(() => setUsage(null));
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
            No conversations stored yet — or transcript storage is switched off
            in the Studio&apos;s privacy panel.
          </EmptyNote>
        ) : (
          <ul className="divide-y divide-line">
            {conversations.map((chat) => (
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
                    {chat.trigger === "checkin" ? "check-in" : "they started it"}
                  </Chip>
                  <span className="flex-1 truncate text-sm">
                    {chat.mood_note ?? `${chat.message_count} turns`}
                  </span>
                  <span className="text-ink-faint">{openId === chat.id ? "▴" : "▾"}</span>
                </button>
                {openId === chat.id && (
                  <div className="mt-3 space-y-2 rounded-2xl bg-cream p-3">
                    {(messages[chat.id] ?? []).map((message) => (
                      <p key={message.id} className="text-sm">
                        <span className="font-semibold">
                          {message.role === "assistant" ? "Meemoo" : "Them"}:
                        </span>{" "}
                        {message.content}
                      </p>
                    ))}
                    {(messages[chat.id] ?? []).length === 0 && (
                      <p className="text-sm text-ink-faint">Loading…</p>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <div className="space-y-6">
        <Card title="Detections">
          {detections.length === 0 ? (
            <EmptyNote>No detections — good news.</EmptyNote>
          ) : (
            <ul className="space-y-2">
              {detections.map((event) => (
                <li key={event.id} className="flex items-baseline gap-2 text-sm">
                  <span className="h-2 w-2 shrink-0 rounded-full bg-rose" />
                  <span className="flex-1">{event.type.replace(/[._]/g, " ")}</span>
                  <span className="text-ink-faint">{fmtDay(event.ts)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card
          title="Cost meter"
          hint={usage ? `pricing ${usage.pricing_version}` : undefined}
        >
          {usage === null ? (
            <EmptyNote>Usage unavailable.</EmptyNote>
          ) : (
            <>
              <p className="text-3xl font-semibold">
                ${usage.today.cost_usd.toFixed(2)}
                <span className="ml-2 text-sm font-normal text-ink-faint">today</span>
              </p>
              <p className="mt-1 text-sm text-ink-soft">
                ≈ ${usage.estimated_monthly_usd.toFixed(2)}/month at this pace ·{" "}
                {usage.today.requests} requests today
              </p>
              {usage.series.length > 1 && (
                <div className="mt-3">
                  <Bars values={usage.series.map((day) => day.cost_usd)} />
                </div>
              )}
            </>
          )}
        </Card>

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
