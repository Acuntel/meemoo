/** Today: the first screen a worried daughter sees at 11pm. The flight view
 * gets the big box; everything happening right now lives in one Right-now
 * box (components/RightNow.tsx). No fake data when idle (Amendment A7). */

import { useCallback, useEffect, useState } from "react";
import { Bars } from "../components/Chart";
import RightNow from "../components/RightNow";
import SimView from "../components/SimView";
import { apiGet, apiPost, fmtTime } from "../lib/api";
import type {
  Alert,
  ApiEvent,
  Conversation,
  FloorPlan,
  NextCheckin,
  SimSnapshot,
} from "../lib/types";
import { Button, Card, EmptyNote } from "../components/ui";

const MOOD_FALLBACK = "No note from this chat.";

export default function TodayPage({
  plan,
  snapshot,
  simReady,
  activeAlerts,
  onGoLive,
}: {
  plan: FloorPlan | null;
  snapshot: SimSnapshot | null;
  simReady: boolean;
  activeAlerts: Alert[];
  onGoLive: () => void;
}) {
  const [next, setNext] = useState<NextCheckin | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [events, setEvents] = useState<ApiEvent[]>([]);
  const [contactNote, setContactNote] = useState<string | null>(null);

  const refresh = useCallback(() => {
    apiGet<NextCheckin>("/api/v1/devices/1/next-checkin")
      .then(setNext)
      .catch(() => setNext(null));
    apiGet<Conversation[]>("/api/v1/conversations?device_id=1&limit=20")
      .then(setConversations)
      .catch(() => setConversations([]));
    apiGet<ApiEvent[]>("/api/v1/events?device_id=1&limit=30")
      .then(setEvents)
      .catch(() => setEvents([]));
  }, []);

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 15_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const today = new Date().toDateString();
  const todaysChats = conversations.filter(
    (c) => new Date(c.started_at).toDateString() === today,
  );
  const todaysEvents = events.filter(
    (e) =>
      new Date(e.ts).toDateString() === today &&
      (e.type.startsWith("checkin.") || e.type.startsWith("person.")),
  );

  const logContact = async (kind: "call" | "visit") => {
    try {
      await apiPost(`/api/v1/devices/1/human-contact`, { kind });
      setContactNote(
        kind === "call" ? "Lovely. Call noted." : "Lovely. Visit noted.",
      );
      window.setTimeout(() => setContactNote(null), 4000);
    } catch {
      setContactNote("Couldn't save that just now.");
    }
  };

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        {plan !== null ? (
          <SimView plan={plan} snapshot={snapshot} />
        ) : (
          <Card title="Where Meemoo is">
            <EmptyNote>
              {simReady
                ? "Waiting for the first position…"
                : "The simulator isn't running, so there is no flight view. Start the app with the runtime on."}
            </EmptyNote>
          </Card>
        )}

        <Card title="Today">
          {todaysChats.length === 0 && todaysEvents.length === 0 ? (
            <EmptyNote>
              Nothing yet today. The next check-in
              {next ? ` is at ${next.time}` : " is on the usual schedule"}, or
              send Meemoo around right now.
            </EmptyNote>
          ) : (
            <ol className="space-y-3">
              {todaysChats.map((chat) => (
                <li key={`c${chat.id}`} className="flex gap-3">
                  <span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full bg-sage" />
                  <div>
                    <p className="text-sm text-ink-faint">
                      {fmtTime(chat.started_at)} ·{" "}
                      {chat.trigger === "checkin"
                        ? "Meemoo checked in"
                        : "They started a chat"}{" "}
                      · {chat.message_count} turns
                    </p>
                    <p className="mt-0.5">{chat.mood_note ?? MOOD_FALLBACK}</p>
                  </div>
                </li>
              ))}
              {todaysEvents.map((event) => (
                <li key={`e${event.id}`} className="flex gap-3">
                  <span
                    className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${
                      event.type.startsWith("person.") ? "bg-rose" : "bg-sky"
                    }`}
                  />
                  <p className="text-sm text-ink-soft">
                    {fmtTime(event.ts)} · {event.type.replace(/[._]/g, " ")}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </Card>
      </div>

      <div className="space-y-6">
        <RightNow
          snapshot={snapshot}
          simReady={simReady}
          next={next}
          activeAlerts={activeAlerts}
          onGoLive={onGoLive}
        />

        <Card
          title="Next check-in"
          hint={next ? `${next.times.length} a day` : undefined}
        >
          {next ? (
            <>
              <p className="text-3xl font-semibold">{next.time}</p>
              <p className="mt-1 text-sm text-ink-faint">
                Daily: {next.times.join(" · ")}
              </p>
            </>
          ) : (
            <EmptyNote>Schedule unavailable.</EmptyNote>
          )}
        </Card>

        <Card title="Stayed in touch?" hint="keeping real visits first">
          <p className="text-sm text-ink-soft">
            Meemoo works best alongside real calls and visits. Log them so the
            family picture stays honest.
          </p>
          <div className="mt-3 flex gap-2">
            <Button kind="soft" onClick={() => void logContact("call")}>
              We called
            </Button>
            <Button kind="soft" onClick={() => void logContact("visit")}>
              We visited
            </Button>
          </div>
          {contactNote && (
            <p className="mt-2 text-sm text-sage-deep">{contactNote}</p>
          )}
        </Card>

        {todaysChats.length > 0 && (
          <Card title="Chats this week">
            <Bars
              values={Array.from({ length: 7 }, (_, index) => {
                const day = new Date();
                day.setDate(day.getDate() - (6 - index));
                return conversations.filter(
                  (c) =>
                    new Date(c.started_at).toDateString() === day.toDateString(),
                ).length;
              })}
            />
          </Card>
        )}
      </div>
    </div>
  );
}
