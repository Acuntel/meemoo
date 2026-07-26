/** Full-screen simulated incoming call — the credential-less escalation demo.
 *
 * Listens for `notify.sent` (simulated) and `escalation.l3` on the live event
 * stream and takes over the screen like an incoming call. Acknowledge halts
 * the real escalation ladder via the REST ack endpoint. */

import { useCallback, useState } from "react";
import { apiPost } from "../lib/api";
import type { BusEvent } from "../lib/types";
import { useEventStream } from "../lib/ws";

type CallState = {
  alertId: number | null;
  level: string;
  reason: string;
  channel: string;
  contact: string;
  fullScreenAlert: boolean;
};

export default function CallOverlay() {
  const [call, setCall] = useState<CallState | null>(null);
  const [acked, setAcked] = useState(false);

  const onEvent = useCallback((event: BusEvent) => {
    if (event.topic === "notify.sent" && event.payload["simulated"] === true) {
      setAcked(false);
      setCall({
        alertId: (event.payload["alert_id"] as number | undefined) ?? null,
        level: String(event.payload["level"] ?? "L1"),
        reason: String(event.payload["body"] ?? "needs attention"),
        channel: String(event.payload["channel"] ?? "call"),
        contact: String(event.payload["contact_name"] ?? "you"),
        fullScreenAlert: false,
      });
    }
    if (event.topic === "escalation.l3") {
      setAcked(false);
      setCall((prev) => ({
        alertId: (event.payload["alert_id"] as number | undefined) ?? prev?.alertId ?? null,
        level: "L3",
        reason: String(event.payload["reason"] ?? prev?.reason ?? "needs attention"),
        channel: "call",
        contact: prev?.contact ?? "you",
        fullScreenAlert: true,
      }));
    }
    if (
      event.topic === "escalation.acknowledged" ||
      event.topic === "escalation.resolved"
    ) {
      setCall(null);
    }
  }, []);

  useEventStream(onEvent);

  if (call === null) return null;

  const acknowledge = async () => {
    setAcked(true);
    try {
      if (call.alertId !== null) {
        await apiPost(`/api/v1/alerts/${call.alertId}/ack`, { via: "dashboard" });
      }
    } finally {
      setCall(null);
    }
  };

  return (
    <div
      className={`fixed inset-0 z-50 flex flex-col items-center justify-center gap-6 p-8 ${
        call.fullScreenAlert ? "bg-rose/95" : "bg-ink/90"
      }`}
    >
      <p className="text-sm uppercase tracking-widest text-white/70">
        {call.fullScreenAlert
          ? "Urgent — no one has responded"
          : `Simulated ${call.channel} · escalation ${call.level}`}
      </p>
      <div className="animate-ring flex h-32 w-32 items-center justify-center rounded-full bg-card text-6xl">
        🎈
      </div>
      <div className="text-center text-white">
        <p className="text-2xl font-semibold">Meemoo is calling {call.contact}</p>
        <p className="mt-2 max-w-md text-white/80">{call.reason}</p>
        {call.fullScreenAlert && (
          <p className="mt-3 max-w-md text-sm text-white/70">
            This is the highest alert level. Meemoo never dials 911 by itself —
            a person always makes that call.
          </p>
        )}
      </div>
      <div className="flex gap-4">
        <button
          type="button"
          onClick={() => void acknowledge()}
          disabled={acked}
          className="rounded-full bg-sage px-8 py-3 text-lg font-semibold text-white shadow-lg transition hover:bg-sage-deep disabled:opacity-60"
        >
          I&apos;ve got it — acknowledge
        </button>
        <button
          type="button"
          onClick={() => setCall(null)}
          className="rounded-full bg-white/15 px-6 py-3 text-white/90 transition hover:bg-white/25"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}
