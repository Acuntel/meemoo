/** Step 6: pick a plan (Amendment A1: consumers see plans, not tokens) and
 * finish. Reuses the Studio plan card so the two surfaces never drift. */

import { useState } from "react";
import { apiPost } from "../../lib/api";
import { Button, Card } from "../../components/ui";
import PlanCard from "../studio/PlanCard";

export default function StepFinish({
  onBack,
  onDone,
}: {
  onBack: () => void;
  onDone: () => void;
}) {
  const [finishing, setFinishing] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const finish = async () => {
    setFinishing(true);
    setNote(null);
    try {
      await apiPost("/api/v1/devices/1/onboarding/complete");
      onDone();
    } catch {
      setNote("Couldn't wrap up just now. Give it another try.");
      setFinishing(false);
    }
  };

  return (
    <div className="space-y-6">
      <PlanCard />
      <Card>
        <p className="text-sm text-ink-soft">
          That's everything. Meemoo knows the place, the special spots, and
          where it must never go. You can change any of this later in Studio.
        </p>
        {note && <p className="mt-3 text-sm text-rose">{note}</p>}
        <div className="mt-4 flex items-center justify-between">
          <Button kind="quiet" onClick={onBack}>
            Back
          </Button>
          <Button onClick={() => void finish()} disabled={finishing}>
            {finishing ? "Finishing..." : "Finish setup"}
          </Button>
        </div>
      </Card>
    </div>
  );
}
