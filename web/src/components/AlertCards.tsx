/** Alert cards, folded into the Live tab (Amendment A7: no Alerts tab).
 * Evidence is shown as the observation Meemoo made, never a diagnosis
 * (Art. IV). Acknowledge halts the real escalation ladder. */

import { useEffect, useState } from "react";
import { apiGet, apiPost, fmtDay, fmtTime } from "../lib/api";
import type { Alert, ApiEvent } from "../lib/types";
import { Button, Card, Chip, EmptyNote } from "./ui";

export function levelTone(level: string): "peach" | "rose" | "sky" {
  if (level === "L3") return "rose";
  if (level === "L2") return "peach";
  return "sky";
}

export function ActiveAlertCards({
  alerts,
  onChanged,
}: {
  alerts: Alert[];
  onChanged: () => void;
}) {
  const [evidence, setEvidence] = useState<Record<number, ApiEvent>>({});
  const [busyId, setBusyId] = useState<number | null>(null);

  useEffect(() => {
    if (alerts.length === 0) return;
    apiGet<ApiEvent[]>("/api/v1/events?device_id=1&limit=200")
      .then((events) => {
        const byId: Record<number, ApiEvent> = {};
        for (const event of events) byId[event.id] = event;
        setEvidence(byId);
      })
      .catch(() => setEvidence({}));
  }, [alerts]);

  const evidenceLine = (alert: Alert): string | null => {
    if (alert.evidence_event_id === null) return null;
    const event = evidence[alert.evidence_event_id];
    if (event === undefined) return null;
    const room = event.payload["room"];
    return `${event.type.replace(/[._]/g, " ")}${
      typeof room === "string" ? ` in the ${room}` : ""
    } at ${fmtTime(event.ts)}`;
  };

  const acknowledge = async (alert: Alert) => {
    setBusyId(alert.id);
    try {
      await apiPost(`/api/v1/alerts/${alert.id}/ack`, { via: "dashboard" });
      onChanged();
    } finally {
      setBusyId(null);
    }
  };

  return (
    <Card title="Needs attention" className="border-rose-soft">
      <ul className="space-y-4">
        {alerts.map((alert) => (
          <li
            key={alert.id}
            className="rounded-2xl border border-rose-soft bg-rose-soft/50 p-4"
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <Chip tone={levelTone(alert.level)}>{alert.level}</Chip>
                  <p className="font-semibold">{alert.reason}</p>
                </div>
                <p className="mt-1 text-sm text-ink-soft">
                  Opened {fmtDay(alert.opened_at)} at {fmtTime(alert.opened_at)}
                  {evidenceLine(alert) &&
                    `. Meemoo saw: ${evidenceLine(alert)}`}
                </p>
              </div>
              <Button
                onClick={() => void acknowledge(alert)}
                disabled={busyId === alert.id}
              >
                I&apos;ve got it, acknowledge
              </Button>
            </div>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-sm text-ink-faint">
        Meemoo rings the people you chose, in order. It never dials 911 by
        itself.
      </p>
    </Card>
  );
}

/** Quiet list of handled alerts, shown in History. */
export function EarlierAlertsCard() {
  const [alerts, setAlerts] = useState<Alert[]>([]);

  useEffect(() => {
    apiGet<Alert[]>("/api/v1/alerts?device_id=1")
      .then((rows) => setAlerts(rows.filter((a) => a.acknowledged_at !== null)))
      .catch(() => setAlerts([]));
  }, []);

  return (
    <Card title="Earlier alerts">
      {alerts.length === 0 ? (
        <EmptyNote>No alerts so far. That is good news.</EmptyNote>
      ) : (
        <ul className="divide-y divide-line">
          {alerts.map((alert) => (
            <li key={alert.id} className="flex flex-wrap items-center gap-3 py-3">
              <Chip tone={levelTone(alert.level)}>{alert.level}</Chip>
              <span className="flex-1">{alert.reason}</span>
              <span className="text-sm text-ink-faint">
                {fmtDay(alert.opened_at)} · handled{" "}
                {alert.acknowledged_at ? fmtTime(alert.acknowledged_at) : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
