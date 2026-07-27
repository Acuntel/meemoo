/** Onboarding wizard (Amendments A1/A3/A6): what kind of place, room
 * capture, named pins, off-limit zones, pairing code, plan. Progress is
 * saved on the base station, so closing the page never loses a step. */

import { useCallback, useEffect, useState } from "react";
import { apiGet, apiPut } from "../../lib/api";
import type { FloorPlan, OnboardingStatus } from "../../lib/types";
import { MeemooLogo } from "../../components/Logo";
import StepFinish from "./StepFinish";
import StepPairing from "./StepPairing";
import StepPins from "./StepPins";
import StepPlace from "./StepPlace";
import StepRooms from "./StepRooms";
import StepZones from "./StepZones";

export type StepKey = "place" | "rooms" | "pins" | "zones" | "pairing" | "plan";

const STEP_ORDER: StepKey[] = ["place", "rooms", "pins", "zones", "pairing", "plan"];

const STEP_TITLES: Record<StepKey, string> = {
  place: "Your place",
  rooms: "Rooms",
  pins: "Special spots",
  zones: "Off limits",
  pairing: "Pairing",
  plan: "Your plan",
};

export default function OnboardingWizard({ onDone }: { onDone: () => void }) {
  const [step, setStep] = useState<StepKey>("place");
  const [dwelling, setDwelling] = useState<string | null>(null);
  const [plan, setPlan] = useState<FloorPlan | null>(null);

  useEffect(() => {
    apiGet<OnboardingStatus>("/api/v1/devices/1/onboarding")
      .then((status) => {
        setDwelling(status.dwelling_type);
        if (STEP_ORDER.includes(status.step as StepKey)) {
          setStep(status.step as StepKey);
        }
      })
      .catch(() => undefined);
    apiGet<{ ready: boolean; plan: FloorPlan | null }>("/api/v1/sim/state")
      .then((state) => setPlan(state.plan))
      .catch(() => setPlan(null));
  }, []);

  const goTo = useCallback((next: StepKey) => {
    setStep(next);
    window.scrollTo({ top: 0 });
    apiPut("/api/v1/devices/1/onboarding", { step: next }).catch(() => undefined);
  }, []);

  const advance = useCallback(() => {
    const index = STEP_ORDER.indexOf(step);
    const next = STEP_ORDER[index + 1];
    if (next) goTo(next);
  }, [step, goTo]);

  const back = useCallback(() => {
    const index = STEP_ORDER.indexOf(step);
    const previous = STEP_ORDER[index - 1];
    if (previous) goTo(previous);
  }, [step, goTo]);

  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-card/80 backdrop-blur">
        <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-3 px-6 py-4">
          <MeemooLogo />
          <nav className="flex flex-wrap items-center gap-1.5" aria-label="Setup steps">
            {STEP_ORDER.map((key) => (
              <span
                key={key}
                className={`rounded-full px-3 py-1 text-xs font-medium ${
                  key === step
                    ? "bg-sage text-white"
                    : STEP_ORDER.indexOf(key) < STEP_ORDER.indexOf(step)
                      ? "bg-sage-soft text-sage-deep"
                      : "bg-cream text-ink-faint"
                }`}
              >
                {STEP_TITLES[key]}
              </span>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-3xl space-y-6 px-6 py-8">
        {step === "place" && (
          <StepPlace
            dwelling={dwelling}
            planName={plan?.name ?? null}
            onChosen={(type) => {
              setDwelling(type);
              advance();
            }}
          />
        )}
        {step === "rooms" && (
          <StepRooms plan={plan} dwelling={dwelling} onBack={back} onNext={advance} />
        )}
        {step === "pins" && <StepPins plan={plan} onBack={back} onNext={advance} />}
        {step === "zones" && (
          <StepZones plan={plan} dwelling={dwelling} onBack={back} onNext={advance} />
        )}
        {step === "pairing" && <StepPairing onBack={back} onNext={advance} />}
        {step === "plan" && <StepFinish onBack={back} onDone={onDone} />}
      </main>

      <footer className="mx-auto max-w-3xl px-6 pb-8 text-center text-xs text-ink-faint">
        Everything you set here stays on this base station. You can change any
        of it later in Studio.
      </footer>
    </div>
  );
}
