/** Step 4 (Amendment A3): off-limit zones. Every bathroom is prompted by
 * default; drawing a rectangle marks any other area. Meemoo never enters a
 * zone, never points a camera at one, and anything accidentally captured
 * inside one is deleted right away with a record of the deletion. */

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiDelete, apiGet, apiPost } from "../../lib/api";
import type { FloorPlan, NoGoZone } from "../../lib/types";
import { Button, Card, Chip, EmptyNote, Toggle } from "../../components/ui";
import PlanCanvas, { type DraftRect } from "./PlanCanvas";

const isBathroom = (name: string) => name.toLowerCase().includes("bath");

export default function StepZones({
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
  const [zones, setZones] = useState<NoGoZone[]>([]);
  const [bathroomOn, setBathroomOn] = useState<Record<string, boolean>>({});
  const [drafts, setDrafts] = useState<(DraftRect & { name: string })[]>([]);
  const [note, setNote] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(() => {
    apiGet<NoGoZone[]>("/api/v1/devices/1/zones")
      .then(setZones)
      .catch(() => setZones([]));
  }, []);
  useEffect(refresh, [refresh]);

  const bathrooms = useMemo(
    () => (plan?.rooms ?? []).filter((room) => isBathroom(room.name)),
    [plan],
  );

  // Every bathroom is prompted ON by default (A3) unless already zoned.
  useEffect(() => {
    setBathroomOn((previous) => {
      const next = { ...previous };
      for (const room of bathrooms) {
        if (!(room.name in next)) next[room.name] = true;
      }
      return next;
    });
  }, [bathrooms]);

  const zoneNames = zones.map((zone) => zone.name);
  const bathroomZoned = (name: string) => zoneNames.includes(`the ${name}`);

  const saveAndContinue = async () => {
    setSaving(true);
    setNote(null);
    let purged = 0;
    try {
      for (const room of bathrooms) {
        if (bathroomOn[room.name] && !bathroomZoned(room.name)) {
          const created = await apiPost<{ purged: number }>("/api/v1/devices/1/zones", {
            name: `the ${room.name}`,
            x: room.x,
            y: room.y,
            w: room.w,
            h: room.h,
            reason: "bathroom",
          });
          purged += created.purged;
        }
      }
      for (const draft of drafts) {
        const created = await apiPost<{ purged: number }>("/api/v1/devices/1/zones", {
          name: draft.name,
          x: draft.x,
          y: draft.y,
          w: draft.w,
          h: draft.h,
          reason: "user",
        });
        purged += created.purged;
      }
      setDrafts([]);
      if (purged > 0) {
        setNote(
          `Done. ${purged} saved ${purged === 1 ? "picture" : "pictures"} from inside the new zones ${purged === 1 ? "was" : "were"} deleted, with a record kept of each deletion.`,
        );
        refresh();
        setSaving(false);
        return; // let the person read the purge note; Continue again to move on
      }
      onNext();
    } catch {
      setNote("Couldn't save the zones just now. Give it another try.");
    } finally {
      setSaving(false);
    }
  };

  const roomWord = dwelling === "hospital_room" ? "this room" : "your place";

  return (
    <Card title="Where should Meemoo never go?" hint="hard boundaries, not suggestions">
      <p className="text-sm text-ink-soft">
        Meemoo never enters an off-limit zone, never points its camera at one,
        and anything accidentally captured inside one is deleted right away
        with a record of the deletion. Bathrooms in {roomWord} are marked for
        you; drag on the map to mark anywhere else.
      </p>

      {bathrooms.length > 0 && (
        <div className="mt-4 rounded-2xl border border-line bg-cream/60 p-4">
          {bathrooms.map((room) => (
            <Toggle
              key={room.name}
              checked={bathroomZoned(room.name) || (bathroomOn[room.name] ?? true)}
              onChange={(next) => {
                if (bathroomZoned(room.name)) return; // remove below, in the list
                setBathroomOn((previous) => ({ ...previous, [room.name]: next }));
              }}
              label={`Keep Meemoo out of the ${room.name}`}
              detail={
                bathroomZoned(room.name)
                  ? "Already marked off limits."
                  : "Recommended and on by default."
              }
            />
          ))}
        </div>
      )}

      {plan === null ? (
        <div className="mt-4">
          <EmptyNote>
            The floor plan isn't available right now, so zones have to wait.
            You can continue and come back to this page later.
          </EmptyNote>
        </div>
      ) : (
        <div className="mt-4">
          <PlanCanvas
            plan={plan}
            zones={[...zones, ...drafts]}
            onDrawRect={(rect) =>
              setDrafts((previous) => [
                ...previous,
                { ...rect, name: `off limits ${previous.length + zones.length + 1}` },
              ])
            }
          />
          <p className="mt-2 text-xs text-ink-faint">
            Drag on the map to draw a new off-limit area.
          </p>
        </div>
      )}

      {(zones.length > 0 || drafts.length > 0) && (
        <ul className="mt-3 space-y-2">
          {zones.map((zone) => (
            <li key={zone.id} className="flex items-center justify-between gap-2 text-sm">
              <span className="flex items-center gap-2">
                <Chip tone="rose">{zone.name}</Chip>
                <span className="text-ink-faint">
                  {zone.reason === "bathroom" ? "bathroom" : "marked by you"}
                </span>
              </span>
              <Button
                kind="quiet"
                onClick={() => {
                  void apiDelete(`/api/v1/zones/${zone.id}`).then(refresh);
                }}
              >
                Remove
              </Button>
            </li>
          ))}
          {drafts.map((draft, index) => (
            <li key={`draft-${index}`} className="flex items-center gap-2 text-sm">
              <input
                value={draft.name}
                aria-label="Zone name"
                onChange={(event) =>
                  setDrafts((previous) =>
                    previous.map((d, i) =>
                      i === index ? { ...d, name: event.target.value } : d,
                    ),
                  )
                }
                className="rounded-full border border-line bg-card px-3 py-1 text-sm"
              />
              <span className="text-ink-faint">not saved yet</span>
              <Button
                kind="quiet"
                onClick={() =>
                  setDrafts((previous) => previous.filter((_, i) => i !== index))
                }
              >
                Remove
              </Button>
            </li>
          ))}
        </ul>
      )}

      {note && <p className="mt-3 text-sm text-sage-deep">{note}</p>}

      <div className="mt-6 flex items-center justify-between">
        <Button kind="quiet" onClick={onBack}>
          Back
        </Button>
        <Button onClick={() => void saveAndContinue()} disabled={saving}>
          {saving ? "Saving..." : "Save and continue"}
        </Button>
      </div>
    </Card>
  );
}
