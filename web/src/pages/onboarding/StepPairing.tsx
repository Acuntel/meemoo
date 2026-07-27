/** Step 5 (Amendment A1): type the code printed on the aircraft. This binds
 * the unit to the base station, and it's how a replacement unit joins later:
 * unbox, type the new code, done. */

import { useEffect, useState } from "react";
import { ApiError, apiGet, apiPost } from "../../lib/api";
import type { OnboardingStatus } from "../../lib/types";
import { Button, Card, Chip } from "../../components/ui";

const CODE_RE = /^MEEMOO-[A-Z0-9]{4}-[A-Z0-9]{4}$/;

export default function StepPairing({
  onBack,
  onNext,
}: {
  onBack: () => void;
  onNext: () => void;
}) {
  const [code, setCode] = useState("");
  const [paired, setPaired] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    apiGet<OnboardingStatus>("/api/v1/devices/1/onboarding")
      .then((status) => setPaired(status.paired))
      .catch(() => undefined);
  }, []);

  const normalized = code.trim().toUpperCase();
  const wellFormed = CODE_RE.test(normalized);

  const pair = async () => {
    setSaving(true);
    setNote(null);
    try {
      await apiPost("/api/v1/devices/1/pair", { code: normalized });
      setPaired(true);
    } catch (error) {
      setNote(
        error instanceof ApiError
          ? error.message
          : "Couldn't pair just now. Give it another try.",
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card title="Connect your aircraft" hint="the code is printed on the unit">
      <p className="text-sm text-ink-soft">
        Look for a code shaped like MEEMOO-XXXX-XXXX printed on the aircraft.
        Typing it here ties that unit to this base station. When a replacement
        unit arrives someday, the same step connects it: unbox, type its code,
        done.
      </p>

      {paired ? (
        <div className="mt-4 flex items-center gap-2">
          <Chip tone="sage">Aircraft connected</Chip>
          <span className="text-sm text-ink-soft">You're all set here.</span>
        </div>
      ) : (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <input
            value={code}
            onChange={(event) => setCode(event.target.value)}
            placeholder="MEEMOO-XXXX-XXXX"
            autoCapitalize="characters"
            spellCheck={false}
            className="w-56 rounded-full border border-line bg-card px-4 py-2 font-mono text-sm tracking-wide"
            aria-label="Pairing code"
          />
          <Button onClick={() => void pair()} disabled={!wellFormed || saving}>
            {saving ? "Connecting..." : "Connect"}
          </Button>
          {code.length > 0 && !wellFormed && (
            <span className="text-xs text-ink-faint">
              Keep going: MEEMOO, then two groups of four letters or numbers.
            </span>
          )}
        </div>
      )}

      {note && <p className="mt-3 text-sm text-rose">{note}</p>}

      <div className="mt-6 flex items-center justify-between">
        <Button kind="quiet" onClick={onBack}>
          Back
        </Button>
        <div className="flex items-center gap-2">
          {!paired && (
            <Button kind="quiet" onClick={onNext}>
              Skip for now
            </Button>
          )}
          <Button onClick={onNext}>Continue</Button>
        </div>
      </div>
    </Card>
  );
}
