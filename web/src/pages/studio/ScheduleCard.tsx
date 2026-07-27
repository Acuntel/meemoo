/** When Meemoo does its rounds: the daily check-in times, editable in place. */

import { useCallback, useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost, apiPut } from "../../lib/api";
import { Button, Card, EmptyNote, Toggle } from "../../components/ui";

interface ScheduleEntry {
  id: number;
  device_id: number;
  time_of_day: string;
  label: string | null;
  enabled: boolean;
}

const DEFAULT_TIMES = ["09:00", "13:00", "18:00", "21:00"];

export default function ScheduleCard() {
  const [entries, setEntries] = useState<ScheduleEntry[]>([]);
  const [time, setTime] = useState("");
  const [label, setLabel] = useState("");
  const [note, setNote] = useState<string | null>(null);

  const refresh = useCallback(() => {
    apiGet<ScheduleEntry[]>("/api/v1/devices/1/schedule")
      .then(setEntries)
      .catch(() => setEntries([]));
  }, []);

  useEffect(refresh, [refresh]);

  const add = async (t?: string) => {
    const value = (t ?? time).trim();
    if (!/^([01]?\d|2[0-3]):[0-5]\d$/.test(value)) {
      setNote("Time must look like 9:00 or 18:30.");
      return;
    }
    try {
      await apiPost("/api/v1/devices/1/schedule", {
        time_of_day: value.padStart(5, "0"),
        label: label.trim() || null,
        enabled: true,
      });
      setTime("");
      setLabel("");
      setNote(null);
      refresh();
    } catch {
      setNote("Couldn't save that time. Is the server running?");
    }
  };

  const toggle = async (entry: ScheduleEntry) => {
    await apiPut(`/api/v1/schedule/${entry.id}`, {
      time_of_day: entry.time_of_day,
      label: entry.label,
      enabled: !entry.enabled,
    });
    refresh();
  };

  const remove = async (id: number) => {
    await apiDelete(`/api/v1/schedule/${id}`);
    refresh();
  };

  const useDefaults = async () => {
    for (const t of DEFAULT_TIMES) {
      if (!entries.some((e) => e.time_of_day === t)) await add(t);
    }
    refresh();
  };

  return (
    <Card>
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="text-lg font-semibold">Daily rounds</h2>
        <span className="text-sm text-stone-500">
          Meemoo flies a round and checks in at each time
        </span>
      </div>

      {entries.length === 0 ? (
        <div className="mb-4">
          <EmptyNote>
            No custom times yet. Meemoo is using its usual rhythm (9:00, 13:00,
            18:00, 21:00).
          </EmptyNote>
          <div className="mt-2">
            <Button kind="soft" onClick={() => void useDefaults()}>
              Copy the usual times here to edit them
            </Button>
          </div>
        </div>
      ) : (
        <ul className="mb-4 space-y-2">
          {entries.map((entry) => (
            <li
              key={entry.id}
              className="flex items-center justify-between rounded-xl bg-stone-50 px-4 py-2"
            >
              <div className="flex items-center gap-3">
                <span className="font-mono text-base">{entry.time_of_day}</span>
                {entry.label && (
                  <span className="text-sm text-stone-500">{entry.label}</span>
                )}
              </div>
              <div className="flex items-center gap-3">
                <Toggle
                  checked={entry.enabled}
                  onChange={() => void toggle(entry)}
                  label={entry.enabled ? "on" : "off"}
                />
                <Button kind="quiet" onClick={() => void remove(entry.id)}>
                  Remove
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <div className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col text-sm text-stone-600">
          Time
          <input
            className="mt-1 w-28 rounded-xl border border-stone-200 px-3 py-2 font-mono"
            placeholder="15:30"
            value={time}
            onChange={(e) => setTime(e.target.value)}
          />
        </label>
        <label className="flex flex-col text-sm text-stone-600">
          Label (optional)
          <input
            className="mt-1 w-48 rounded-xl border border-stone-200 px-3 py-2"
            placeholder="afternoon medication"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
          />
        </label>
        <Button onClick={() => void add()}>Add time</Button>
      </div>
      {note && <p className="mt-2 text-sm text-rose-600">{note}</p>}
    </Card>
  );
}
