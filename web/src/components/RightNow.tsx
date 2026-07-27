/** The Right-now box: current status, any open alert, and the live feed all
 * in one place. When nothing is happening it says so plainly; no fake data
 * on a consumer surface (Amendment A7). */

import { useCallback, useState } from "react";
import { apiPost } from "../lib/api";
import type { Alert, BusEvent, NextCheckin, SimSnapshot } from "../lib/types";
import { useEventStream } from "../lib/ws";
import { Button, Card, Chip } from "./ui";

const FEED_TOPICS = [
  "checkin.",
  "person.",
  "candidate.",
  "utterance.",
  "escalation.",
  "notify.",
  "flight.",
  "dock.",
];

/** Routine telemetry that would bury the quiet state in noise. */
const FEED_SKIP = ["flight.battery", "flight.state"];

export default function RightNow({
  snapshot,
  simReady,
  next,
  activeAlerts,
  onGoLive,
}: {
  snapshot: SimSnapshot | null;
  simReady: boolean;
  next: NextCheckin | null;
  activeAlerts: Alert[];
  onGoLive: () => void;
}) {
  const [feed, setFeed] = useState<BusEvent[]>([]);
  const [roundNote, setRoundNote] = useState<string | null>(null);
  const onEvent = useCallback((event: BusEvent) => {
    if (!FEED_TOPICS.some((prefix) => event.topic.startsWith(prefix))) return;
    if (FEED_SKIP.includes(event.topic)) return;
    setFeed((prev) => [event, ...prev].slice(0, 8));
  }, []);
  useEventStream(onEvent);

  const flying = snapshot !== null && !snapshot.docked;
  const quiet = !flying && activeAlerts.length === 0 && feed.length === 0;

  const runRound = async () => {
    setRoundNote("Sending Meemoo on a round…");
    try {
      const result = await apiPost<{ started: boolean; reason?: string }>(
        "/api/v1/devices/1/rounds/run",
      );
      setRoundNote(
        result.started
          ? "Meemoo is on the way. Watch the Live view."
          : `Couldn't start: ${result.reason ?? "unknown"}`,
      );
      if (result.started) onGoLive();
    } catch {
      setRoundNote("Couldn't reach Meemoo just now.");
    }
  };

  return (
    <Card title="Right now">
      {activeAlerts.map((alert) => (
        <div
          key={alert.id}
          className="mb-3 rounded-2xl border border-rose-soft bg-rose-soft/50 p-3"
        >
          <p className="text-sm font-semibold text-rose">
            {alert.level}: {alert.reason}
          </p>
          <button
            type="button"
            onClick={onGoLive}
            className="mt-1 text-sm font-medium text-rose underline"
          >
            See it in Live and acknowledge
          </button>
        </div>
      ))}

      {quiet ? (
        <p>
          {!simReady
            ? "Meemoo isn't flying right now. Start the app with the runtime on to see the flight view."
            : snapshot === null
              ? "Meemoo is quiet right now. Waiting for its first word."
              : `Meemoo is resting on its dock.${next ? ` Next round at ${next.time}.` : ""}`}
        </p>
      ) : (
        <p>
          {flying
            ? snapshot.waypoint_label
              ? `Meemoo is on its way to ${snapshot.waypoint_label}.`
              : "Meemoo is out on a round."
            : snapshot !== null
              ? "Meemoo is home on its dock."
              : "Meemoo is quiet right now."}
        </p>
      )}

      {snapshot !== null && (
        <div className="mt-3 flex flex-wrap gap-2">
          <Chip tone="sky">
            Battery {Math.round(snapshot.battery_pct)}%
            {snapshot.charging ? " ⚡" : ""}
          </Chip>
          <Chip tone="sage">{snapshot.docked ? "Docked" : "Flying"}</Chip>
        </div>
      )}

      {feed.length > 0 && (
        <ul className="mt-4 space-y-2 border-t border-line pt-3">
          {feed.map((event) => (
            <li key={event.seq} className="flex items-baseline gap-2 text-sm">
              <span
                className={`h-2 w-2 shrink-0 rounded-full ${
                  event.topic.startsWith("escalation.") ||
                  event.topic.startsWith("person.")
                    ? "bg-rose"
                    : "bg-sage"
                }`}
              />
              <span className="text-ink-soft">
                {event.topic.replace(/\./g, " · ")}
              </span>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-4">
        <Button onClick={() => void runRound()}>Send Meemoo around now</Button>
      </div>
      {roundNote && <p className="mt-2 text-sm text-ink-faint">{roundNote}</p>}
    </Card>
  );
}
