/** Step 2 (Amendment A6): guided space capture. About 20 detailed photos per
 * covered room give Meemoo real context for its map. Photos stay on the base
 * station; bathrooms are skipped entirely (Amendment A3). */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { apiDelete, apiGet, apiPost } from "../../lib/api";
import type { FloorPlan, RoomSummary } from "../../lib/types";
import { Button, Card, Chip, EmptyNote } from "../../components/ui";

const isBathroom = (name: string) => name.toLowerCase().includes("bath");

function toBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result ?? "");
      resolve(result.slice(result.indexOf(",") + 1));
    };
    reader.onerror = () => reject(new Error("read failed"));
    reader.readAsDataURL(file);
  });
}

export default function StepRooms({
  plan,
  dwelling,
  onBack,
  onNext,
}: {
  plan: FloorPlan | null;
  dwelling: string | null;
  onBack: () => void;
  onNext: () => void;
}) {
  const [summaries, setSummaries] = useState<RoomSummary[]>([]);
  const [customRooms, setCustomRooms] = useState<string[]>([]);
  const [newRoom, setNewRoom] = useState("");
  const [busyRoom, setBusyRoom] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const inputs = useRef<Record<string, HTMLInputElement | null>>({});

  const refresh = useCallback(() => {
    apiGet<RoomSummary[]>("/api/v1/devices/1/rooms")
      .then(setSummaries)
      .catch(() => setSummaries([]));
  }, []);
  useEffect(refresh, [refresh]);

  const planRooms = useMemo(
    () => (plan?.rooms ?? []).map((r) => r.name).filter((name) => !isBathroom(name)),
    [plan],
  );
  const captured = summaries.map((s) => s.room);
  const rooms = Array.from(new Set([...planRooms, ...customRooms, ...captured]));
  const countFor = (room: string) =>
    summaries.find((s) => s.room === room)?.photo_count ?? 0;

  const upload = async (room: string, files: FileList | null) => {
    if (!files || files.length === 0) return;
    setBusyRoom(room);
    setNote(null);
    try {
      for (const file of Array.from(files)) {
        const image_base64 = await toBase64(file);
        await apiPost(`/api/v1/devices/1/rooms/${encodeURIComponent(room)}/photos`, {
          image_base64,
          content_type: file.type || "image/jpeg",
        });
      }
      refresh();
    } catch (error) {
      setNote(error instanceof Error ? error.message : "Upload didn't go through.");
    } finally {
      setBusyRoom(null);
    }
  };

  const retake = async (room: string) => {
    setBusyRoom(room);
    try {
      await apiDelete(`/api/v1/devices/1/rooms/${encodeURIComponent(room)}/photos`);
      refresh();
    } catch {
      setNote("Couldn't clear that room just now.");
    } finally {
      setBusyRoom(null);
    }
  };

  const noun =
    dwelling === "senior_room" || dwelling === "hospital_room" ? "the room" : "each room";

  return (
    <Card title="Show Meemoo around" hint="photos stay on this base station">
      <p className="text-sm text-ink-soft">
        Walk through {noun} you want covered and take detailed photos: corners,
        furniture, doorways, the floor. About 20 per room gives Meemoo a solid
        picture. They are context for its map, never surveillance, and you can
        delete them any time in Studio. Bathrooms are skipped; Meemoo stays out
        of them.
      </p>

      {rooms.length === 0 && (
        <div className="mt-4">
          <EmptyNote>
            No rooms yet. Add the first room below to start capturing.
          </EmptyNote>
        </div>
      )}

      <ul className="mt-4 space-y-3">
        {rooms.map((room) => {
          const count = countFor(room);
          const done = count >= 20;
          return (
            <li
              key={room}
              className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line bg-card p-4"
            >
              <div>
                <span className="font-medium">{room}</span>
                <span className="ml-2">
                  <Chip tone={done ? "sage" : count > 0 ? "peach" : "plain"}>
                    {count} of ~20 photos
                  </Chip>
                </span>
                {count > 0 && !done && (
                  <p className="mt-1 text-xs text-ink-faint">
                    A few more angles will round this room out.
                  </p>
                )}
              </div>
              <div className="flex items-center gap-2">
                <input
                  ref={(el) => {
                    inputs.current[room] = el;
                  }}
                  type="file"
                  accept="image/*"
                  capture="environment"
                  multiple
                  className="hidden"
                  aria-label={`Add photos of ${room}`}
                  onChange={(event) => {
                    void upload(room, event.target.files);
                    event.target.value = "";
                  }}
                />
                <Button
                  kind="soft"
                  disabled={busyRoom !== null}
                  onClick={() => inputs.current[room]?.click()}
                >
                  {busyRoom === room ? "Saving..." : count > 0 ? "Add photos" : "Capture"}
                </Button>
                {count > 0 && (
                  <Button kind="quiet" disabled={busyRoom !== null} onClick={() => void retake(room)}>
                    Furniture moved? Retake
                  </Button>
                )}
              </div>
            </li>
          );
        })}
      </ul>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <input
          value={newRoom}
          onChange={(event) => setNewRoom(event.target.value)}
          placeholder="Add another room, like the den"
          className="rounded-full border border-line bg-card px-4 py-2 text-sm"
        />
        <Button
          kind="soft"
          disabled={newRoom.trim().length === 0}
          onClick={() => {
            const name = newRoom.trim();
            if (isBathroom(name)) {
              setNote("Bathrooms stay off Meemoo's map entirely.");
            } else if (!rooms.includes(name)) {
              setCustomRooms((previous) => [...previous, name]);
            }
            setNewRoom("");
          }}
        >
          Add room
        </Button>
      </div>

      {note && <p className="mt-3 text-sm text-rose">{note}</p>}

      <div className="mt-6 flex items-center justify-between">
        <Button kind="quiet" onClick={onBack}>
          Back
        </Button>
        <Button onClick={onNext}>Continue</Button>
      </div>
    </Card>
  );
}
