/** Plan picker (Amendment A1): consumers see plans, not tokens. Two plain
 * questions route to a tier; the choice is saved on the base station. No
 * payments yet, and the card says so honestly. */

import { useEffect, useState } from "react";
import { apiGet, apiPut } from "../../lib/api";
import { Button, Card, Chip } from "../../components/ui";

type TierKey = "checkins" | "companion" | "fullcare";

const TIERS: { key: TierKey; name: string; blurb: string }[] = [
  {
    key: "checkins",
    name: "Check-ins",
    blurb:
      "A friendly hello a few times a day, reminders at the right moments, and word to the family if something seems off.",
  },
  {
    key: "companion",
    name: "Companion",
    blurb:
      "Real conversation through the day: company, reminders, check-ins from morning to night, and the full escalation ladder.",
  },
  {
    key: "fullcare",
    name: "Full care",
    blurb:
      "Around-the-clock watch: day and night rounds, fall watch, replacement aircraft and helium included, priority support.",
  },
];

const NEEDS: { key: string; label: string; tier: TierKey }[] = [
  { key: "hello", label: "Look in and say hello", tier: "checkins" },
  { key: "company", label: "Keep them company through the day", tier: "companion" },
  { key: "watch", label: "Watch over them, day and night", tier: "fullcare" },
];

const FREQUENCIES: { key: string; label: string; tier: TierKey }[] = [
  { key: "few", label: "A few times a day", tier: "checkins" },
  { key: "daytime", label: "Morning to night", tier: "companion" },
  { key: "always", label: "Around the clock", tier: "fullcare" },
];

const RANK: Record<TierKey, number> = { checkins: 0, companion: 1, fullcare: 2 };

type PlanSelection = { tier?: string; need?: string; frequency?: string };

export default function PlanCard() {
  const [need, setNeed] = useState<string | null>(null);
  const [frequency, setFrequency] = useState<string | null>(null);
  const [chosen, setChosen] = useState<TierKey | null>(null);
  const [savedTier, setSavedTier] = useState<TierKey | null>(null);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    apiGet<PlanSelection>("/api/v1/devices/1/settings/plan.selection")
      .then((value) => {
        const tier = TIERS.find((t) => t.key === value.tier)?.key ?? null;
        setSavedTier(tier);
        setChosen(tier);
        setNeed(typeof value.need === "string" ? value.need : null);
        setFrequency(
          typeof value.frequency === "string" ? value.frequency : null,
        );
      })
      .catch(() => undefined);
  }, []);

  const needTier = NEEDS.find((n) => n.key === need)?.tier ?? null;
  const freqTier = FREQUENCIES.find((f) => f.key === frequency)?.tier ?? null;
  const recommended: TierKey | null =
    needTier !== null && freqTier !== null
      ? RANK[needTier] >= RANK[freqTier]
        ? needTier
        : freqTier
      : (needTier ?? freqTier);
  const selected = chosen ?? recommended;

  const save = async () => {
    if (selected === null) return;
    try {
      await apiPut("/api/v1/devices/1/settings/plan.selection", {
        value: { tier: selected, need, frequency },
      });
      setSavedTier(selected);
      setNote("Saved. This plan is noted for when billing opens.");
    } catch {
      setNote("Couldn't save that just now.");
    }
  };

  return (
    <Card title="Your plan" hint="everything Meemoo needs, in one subscription">
      <p className="text-sm text-ink-soft">
        The subscription covers the models, the helium, and replacement
        aircraft when parts wear out. Two quick questions point to the right
        tier.
      </p>

      <div className="mt-4">
        <p className="mb-2 text-sm font-medium">What do you need Meemoo to do?</p>
        <div className="flex flex-wrap gap-2">
          {NEEDS.map((option) => (
            <button
              key={option.key}
              type="button"
              onClick={() => {
                setNeed(option.key);
                setChosen(null);
              }}
              className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                need === option.key
                  ? "bg-sage text-white"
                  : "bg-cream text-ink-soft hover:bg-sage-soft"
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-3">
        <p className="mb-2 text-sm font-medium">How often?</p>
        <div className="flex flex-wrap gap-2">
          {FREQUENCIES.map((option) => (
            <button
              key={option.key}
              type="button"
              onClick={() => {
                setFrequency(option.key);
                setChosen(null);
              }}
              className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                frequency === option.key
                  ? "bg-sage text-white"
                  : "bg-cream text-ink-soft hover:bg-sage-soft"
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        {TIERS.map((tier) => (
          <button
            key={tier.key}
            type="button"
            onClick={() => setChosen(tier.key)}
            className={`rounded-2xl border p-4 text-left transition ${
              selected === tier.key
                ? "border-sage bg-sage-soft"
                : "border-line bg-card hover:border-sage/50"
            }`}
          >
            <span className="flex items-center gap-2">
              <span className="font-semibold">{tier.name}</span>
              {recommended === tier.key && <Chip tone="peach">suggested</Chip>}
              {savedTier === tier.key && <Chip tone="sage">your plan</Chip>}
            </span>
            <span className="mt-1 block text-sm text-ink-soft">{tier.blurb}</span>
          </button>
        ))}
      </div>

      <div className="mt-4 flex items-center gap-3">
        <Button onClick={() => void save()} disabled={selected === null}>
          {savedTier === null ? "Choose this plan" : "Update my plan"}
        </Button>
        {note && <span className="text-sm text-sage-deep">{note}</span>}
      </div>
      <p className="mt-2 text-xs text-ink-faint">
        No payment is taken here. Billing isn't switched on yet; your choice is
        saved so the right plan is ready when it is.
      </p>
    </Card>
  );
}
