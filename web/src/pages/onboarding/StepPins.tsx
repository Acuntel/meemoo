/** Step 3 (Amendment A6): drop pins on the floor plan and name them.
 * Pins are saved as real waypoints, so "go to Ruth's chair" means something. */

import { useEffect, useState } from "react";
import { apiDelete, apiGet, apiPost } from "../../lib/api";
import type { FloorPlan } from "../../lib/types";
import { Button, Card, EmptyNote } from "../../components/ui";
import PlanCanvas, { type Pin } from "./PlanCanvas";

const ROUTE_NAME = "My places";

type RouteRow = {
  id: number;
  name: string;
  waypoints: { label: string | null; x: number; y: number }[];
};

export default function StepPins({
  plan,
  onBack,
  onNext,
}: {
  plan: FloorPlan | null;
  onBack: () => void;
  onNext: () => void;
}) {
  const [pins, setPins] = useState<Pin[]>([]);
  const [draft, setDraft] = useState<{ x: number; y: number } | null>(null);
  const [draftName, setDraftName] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    apiGet<RouteRow[]>("/api/v1/devices/1/routes")
      .then((routes) => {
        const mine = routes.find((r) => r.name === ROUTE_NAME);
        if (mine) {
          setPins(
            mine.waypoints.map((w) => ({ label: w.label ?? "spot", x: w.x, y: w.y })),
          );
        }
      })
      .catch(() => undefined);
  }, []);

  const saveAndContinue = async () => {
    setSaving(true);
    setNote(null);
    try {
      const routes = await apiGet<RouteRow[]>("/api/v1/devices/1/routes");
      const existing = routes.find((r) => r.name === ROUTE_NAME);
      if (existing) await apiDelete(`/api/v1/routes/${existing.id}`);
      if (pins.length > 0) {
        await apiPost("/api/v1/devices/1/routes", {
          name: ROUTE_NAME,
          is_default: false,
          waypoints: pins.map((pin, index) => ({
            order_index: index,
            kind: "area",
            label: pin.label,
            x: pin.x,
            y: pin.y,
          })),
        });
      }
      onNext();
    } catch {
      setNote("Couldn't save the pins just now. Give it another try.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card title="Mark the spots that matter" hint="tap the map, then name the pin">
      <p className="text-sm text-ink-soft">
        Tap where the favorite chair is, the kitchen table, the reading lamp.
        Give each pin a name. Later you can say "Hey Meemoo, go to Ruth's
        chair" and it knows exactly where that is.
      </p>

      {plan === null ? (
        <div className="mt-4">
          <EmptyNote>
            The floor plan isn't available right now, so pins have to wait.
            You can continue and come back to this page later.
          </EmptyNote>
        </div>
      ) : (
        <div className="mt-4">
          <PlanCanvas
            plan={plan}
            pins={pins}
            onTap={(x, y) => {
              setDraft({ x, y });
              setDraftName("");
            }}
          />
          {draft && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <input
                autoFocus
                value={draftName}
                onChange={(event) => setDraftName(event.target.value)}
                placeholder="Name this spot, like Ruth's chair"
                className="rounded-full border border-line bg-card px-4 py-2 text-sm"
                onKeyDown={(event) => {
                  if (event.key === "Enter" && draftName.trim()) {
                    setPins((previous) => [
                      ...previous,
                      { label: draftName.trim(), ...draft },
                    ]);
                    setDraft(null);
                  }
                }}
              />
              <Button
                kind="soft"
                disabled={draftName.trim().length === 0}
                onClick={() => {
                  setPins((previous) => [
                    ...previous,
                    { label: draftName.trim(), ...draft },
                  ]);
                  setDraft(null);
                }}
              >
                Add pin
              </Button>
              <Button kind="quiet" onClick={() => setDraft(null)}>
                Cancel
              </Button>
            </div>
          )}
          {pins.length > 0 && (
            <ul className="mt-3 flex flex-wrap gap-2">
              {pins.map((pin, index) => (
                <li
                  key={`${pin.label}-${index}`}
                  className="flex items-center gap-1.5 rounded-full bg-peach-soft px-3 py-1 text-sm"
                >
                  {pin.label}
                  <button
                    type="button"
                    aria-label={`Remove ${pin.label}`}
                    className="opacity-60 hover:opacity-100"
                    onClick={() =>
                      setPins((previous) => previous.filter((_, i) => i !== index))
                    }
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {note && <p className="mt-3 text-sm text-rose">{note}</p>}

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
