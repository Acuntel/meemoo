/** Captured rooms (Amendment A6): the photos are context for Meemoo's map,
 * not surveillance. They live on this base station, and this card is where
 * they stay viewable and deletable. */

import { useCallback, useEffect, useState } from "react";
import { apiDelete, apiGet } from "../../lib/api";
import type { RoomPhoto, RoomSummary } from "../../lib/types";
import { Button, Card, Chip, EmptyNote } from "../../components/ui";

export default function RoomsCard() {
  const [rooms, setRooms] = useState<RoomSummary[]>([]);
  const [openRoom, setOpenRoom] = useState<string | null>(null);
  const [photos, setPhotos] = useState<RoomPhoto[]>([]);

  const refresh = useCallback(() => {
    apiGet<RoomSummary[]>("/api/v1/devices/1/rooms")
      .then(setRooms)
      .catch(() => setRooms([]));
  }, []);
  useEffect(refresh, [refresh]);

  const open = (room: string) => {
    setOpenRoom(room);
    apiGet<RoomPhoto[]>(`/api/v1/devices/1/rooms/${encodeURIComponent(room)}/photos`)
      .then(setPhotos)
      .catch(() => setPhotos([]));
  };

  const removePhoto = async (id: number) => {
    await apiDelete(`/api/v1/photos/${id}`).catch(() => undefined);
    setPhotos((previous) => previous.filter((photo) => photo.id !== id));
    refresh();
  };

  const retake = async (room: string) => {
    await apiDelete(
      `/api/v1/devices/1/rooms/${encodeURIComponent(room)}/photos`,
    ).catch(() => undefined);
    setOpenRoom(null);
    refresh();
  };

  return (
    <Card title="Rooms Meemoo knows" hint="photos stay on this base station">
      <p className="text-sm text-ink-soft">
        These photos give Meemoo context for its map. They never leave this
        base station. Retake a room when furniture moves, or delete anything
        you want gone.
      </p>

      {rooms.length === 0 ? (
        <div className="mt-4">
          <EmptyNote>
            No rooms captured yet. The setup walk-through at /onboarding is
            where rooms get photographed.
          </EmptyNote>
        </div>
      ) : (
        <ul className="mt-4 space-y-3">
          {rooms.map((summary) => (
            <li key={summary.room} className="rounded-2xl border border-line bg-card p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <span className="flex items-center gap-2">
                  <span className="font-medium">{summary.room}</span>
                  <Chip tone={summary.photo_count >= summary.target ? "sage" : "peach"}>
                    {summary.photo_count} of ~{summary.target} photos
                  </Chip>
                </span>
                <span className="flex items-center gap-2">
                  <Button
                    kind="quiet"
                    onClick={() =>
                      openRoom === summary.room ? setOpenRoom(null) : open(summary.room)
                    }
                  >
                    {openRoom === summary.room ? "Hide photos" : "View photos"}
                  </Button>
                  <Button kind="danger" onClick={() => void retake(summary.room)}>
                    Delete all
                  </Button>
                </span>
              </div>
              {openRoom === summary.room && (
                <div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-5">
                  {photos.map((photo) => (
                    <figure key={photo.id} className="relative">
                      <img
                        src={`/api/v1/photos/${photo.id}`}
                        alt={`${summary.room} photo`}
                        className="h-20 w-full rounded-xl object-cover"
                        loading="lazy"
                      />
                      <button
                        type="button"
                        aria-label="Delete photo"
                        onClick={() => void removePhoto(photo.id)}
                        className="absolute right-1 top-1 rounded-full bg-card/90 px-1.5 text-xs text-rose shadow"
                      >
                        ×
                      </button>
                    </figure>
                  ))}
                  {photos.length === 0 && (
                    <p className="col-span-full text-sm text-ink-faint">
                      Nothing here right now.
                    </p>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      <p className="mt-4 text-xs text-ink-faint">
        Furniture moved? Open the walk-through at{" "}
        <a href="/onboarding" className="text-sage-deep underline">
          /onboarding
        </a>{" "}
        to retake a room.
      </p>
    </Card>
  );
}
