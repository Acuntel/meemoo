/** Live View — the sim floor plan, the camera, and a live line to Meemoo. */

import { useCallback, useState } from "react";
import SimView from "../components/SimView";
import TalkWidget from "../components/TalkWidget";
import { Card, EmptyNote } from "../components/ui";
import type { BusEvent, FloorPlan, SimSnapshot } from "../lib/types";
import { useEventStream, useVideoStream } from "../lib/ws";

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

function interesting(topic: string): boolean {
  return FEED_TOPICS.some((prefix) => topic.startsWith(prefix));
}

export default function LivePage({
  plan,
  snapshot,
  simReady,
}: {
  plan: FloorPlan | null;
  snapshot: SimSnapshot | null;
  simReady: boolean;
}) {
  const [feed, setFeed] = useState<BusEvent[]>([]);
  const onEvent = useCallback((event: BusEvent) => {
    if (!interesting(event.topic)) return;
    setFeed((prev) => [event, ...prev].slice(0, 30));
  }, []);
  const { connected } = useEventStream(onEvent);
  const video = useVideoStream();

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
                : "The simulator isn't running — start the app with the runtime on."}
            </EmptyNote>
          </Card>
        )}

        <Card title="Room camera" hint="detections happen here, on the ground">
          {video.frameUrl !== null ? (
            <img
              src={video.frameUrl}
              alt="Annotated room camera"
              className="w-full rounded-2xl"
            />
          ) : (
            <EmptyNote>
              {video.ready
                ? "Camera connected — waiting for the first frame…"
                : "No camera connected. Perception runs when a webcam (or clip replay) is attached."}
            </EmptyNote>
          )}
        </Card>
      </div>

      <div className="space-y-6">
        <Card title="Talk to Meemoo" hint="the real pipeline">
          <TalkWidget />
        </Card>

        <Card
          title="Happening now"
          hint={connected ? "live" : "reconnecting…"}
        >
          {feed.length === 0 ? (
            <EmptyNote>Quiet so far — events appear the moment they happen.</EmptyNote>
          ) : (
            <ul className="space-y-2">
              {feed.map((event) => (
                <li
                  key={event.seq}
                  className="flex items-baseline gap-2 text-sm"
                >
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
        </Card>
      </div>
    </div>
  );
}
