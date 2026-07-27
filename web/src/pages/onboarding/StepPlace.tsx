/** Step 1 (Amendment A6): what kind of place is this? The choice shapes the
 * starting map and the wording through the rest of setup. */

import { useState } from "react";
import { apiPut } from "../../lib/api";
import { Card } from "../../components/ui";

const PLACES: { key: string; label: string; blurb: string }[] = [
  {
    key: "house",
    label: "A house",
    blurb: "A few rooms, maybe more than one floor. Meemoo covers the rooms you pick.",
  },
  {
    key: "apartment",
    label: "An apartment",
    blurb: "A cozy layout. Quick to set up, easy for Meemoo to learn.",
  },
  {
    key: "senior_room",
    label: "A senior living room",
    blurb: "One room in a community. Meemoo keeps its rounds small and gentle.",
  },
  {
    key: "hospital_room",
    label: "A hospital room",
    blurb: "A single room with visitors and staff. Meemoo stays polite and out of the way.",
  },
];

export default function StepPlace({
  dwelling,
  planName,
  onChosen,
}: {
  dwelling: string | null;
  planName: string | null;
  onChosen: (type: string) => void;
}) {
  const [saving, setSaving] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const choose = async (key: string) => {
    setSaving(true);
    try {
      await apiPut("/api/v1/devices/1/onboarding", { dwelling_type: key });
      onChosen(key);
    } catch {
      setNote("Couldn't save that just now. Give it another try.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card title="Welcome. Let's set up Meemoo's home.">
      <p className="text-sm text-ink-soft">
        A few quick steps: the rooms, the special spots, the places Meemoo
        should never go, and the code on the aircraft. First, what kind of
        place is this?
      </p>
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {PLACES.map((place) => (
          <button
            key={place.key}
            type="button"
            disabled={saving}
            onClick={() => void choose(place.key)}
            className={`rounded-2xl border p-4 text-left transition ${
              dwelling === place.key
                ? "border-sage bg-sage-soft"
                : "border-line bg-card hover:border-sage/50"
            }`}
          >
            <span className="font-semibold">{place.label}</span>
            <span className="mt-1 block text-sm text-ink-soft">{place.blurb}</span>
          </button>
        ))}
      </div>
      {planName !== null && (
        <p className="mt-4 text-xs text-ink-faint">
          Your base station starts from the {planName.replace(/_/g, " ")} layout.
          The next steps shape it to your place.
        </p>
      )}
      {note && <p className="mt-3 text-sm text-rose">{note}</p>}
    </Card>
  );
}
