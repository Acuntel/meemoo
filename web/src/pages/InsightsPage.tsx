/** Insights — the research-credibility layer (Constitution Art. VIII).
 * False-alarms/week is the published headline; engagement is a TRAJECTORY;
 * human contact is the anti-substitution metric. Demo mode is loudly labeled
 * synthetic (research 07 §F.15). */

import { useEffect, useState } from "react";
import { LineChart, StatCard } from "../components/Chart";
import { apiGet } from "../lib/api";
import type {
  Abandonment,
  AdherenceSummary,
  EngagementResponse,
  FalseAlarms,
  HumanContactSummary,
} from "../lib/types";
import { Card, EmptyNote, SyntheticBanner, Toggle } from "../components/ui";

const WEEK6_INDEX = 35; // day 36 of a 42-day window = start of week 6

export default function InsightsPage() {
  const [demo, setDemo] = useState(false);
  const [engagement, setEngagement] = useState<EngagementResponse | null>(null);
  const [adherence, setAdherence] = useState<AdherenceSummary | null>(null);
  const [contact, setContact] = useState<HumanContactSummary | null>(null);
  const [abandonment, setAbandonment] = useState<Abandonment | null>(null);
  const [falseAlarms, setFalseAlarms] = useState<FalseAlarms | null>(null);

  useEffect(() => {
    const suffix = demo ? "&demo=true" : "";
    apiGet<EngagementResponse>(`/api/v1/metrics/engagement?device_id=1${suffix}`)
      .then(setEngagement)
      .catch(() => setEngagement(null));
    apiGet<AdherenceSummary>(`/api/v1/metrics/adherence?device_id=1${suffix}`)
      .then(setAdherence)
      .catch(() => setAdherence(null));
    apiGet<HumanContactSummary>(`/api/v1/metrics/human-contact?device_id=1${suffix}`)
      .then(setContact)
      .catch(() => setContact(null));
    apiGet<Abandonment>(`/api/v1/metrics/abandonment?device_id=1${suffix}`)
      .then(setAbandonment)
      .catch(() => setAbandonment(null));
    if (demo) {
      setFalseAlarms({ false_alarms_last_7_days: 1, window_days: 7, synthetic: true });
    } else {
      apiGet<FalseAlarms>("/api/v1/metrics/false-alarms?device_id=1")
        .then(setFalseAlarms)
        .catch(() => setFalseAlarms(null));
    }
  }, [demo]);

  const series = engagement?.series ?? [];
  const shareValues = series.map((day) =>
    day.sessions > 0 ? day.user_initiated / day.sessions : 0,
  );
  const risk = abandonment?.risk ?? null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        {demo ? (
          <SyntheticBanner label={engagement?.label} />
        ) : (
          <p className="text-sm text-ink-faint">
            Real numbers from this device — empty panels stay honestly empty.
          </p>
        )}
        <div className="w-64">
          <Toggle
            checked={demo}
            onChange={setDemo}
            label="Demo mode"
            detail="labeled synthetic data"
          />
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="False alarms this week"
          value={falseAlarms ? String(falseAlarms.false_alarms_last_7_days) : "—"}
          hint="the published headline number"
          tone="rose"
        />
        <StatCard
          label="Chats they started (7d)"
          value={String(
            series.slice(-7).reduce((sum, day) => sum + day.user_initiated, 0),
          )}
          hint="engagement is a trajectory"
          tone="sage"
        />
        <StatCard
          label="Real calls & visits (28d)"
          value={contact ? String(contact.total) : "—"}
          hint="the anti-substitution metric"
          tone="sky"
        />
        <StatCard
          label="Walking-away risk"
          value={risk === null ? "—" : `${risk}/100`}
          hint={
            abandonment && abandonment.signals.length > 0
              ? abandonment.signals[0]
              : "no warning signs"
          }
          tone={risk !== null && risk >= 50 ? "rose" : "peach"}
        />
      </div>

      <Card
        title="Engagement trajectory"
        hint="share of chats they started, day by day"
      >
        {series.length === 0 ? (
          <EmptyNote>
            No conversations yet — the trajectory starts with the first chat.
          </EmptyNote>
        ) : (
          <LineChart
            values={shareValues}
            labels={series.map((day) => day.date)}
            markerIndex={series.length > WEEK6_INDEX ? WEEK6_INDEX : undefined}
            markerLabel="week 6"
          />
        )}
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Reminder adherence" hint="with prompts required">
          {adherence === null || !adherence.has_data ? (
            <EmptyNote>
              No reminder data yet — adherence fills in once reminders run.
            </EmptyNote>
          ) : (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-3xl font-semibold">
                  {adherence.completion_rate !== null
                    ? `${Math.round(adherence.completion_rate * 100)}%`
                    : "—"}
                </p>
                <p className="text-sm text-ink-faint">completed</p>
              </div>
              <div>
                <p className="text-3xl font-semibold">
                  {adherence.avg_prompts_required ?? "—"}
                </p>
                <p className="text-sm text-ink-faint">prompts needed on average</p>
              </div>
              <p className="col-span-2 text-sm text-ink-soft">
                {adherence.delivered} delivered · {adherence.completed} completed ·{" "}
                {adherence.missed} missed over {adherence.window_days} days
              </p>
            </div>
          )}
        </Card>

        <Card title="Human contact" hint="rising Meemoo use must not replace people">
          {contact === null || contact.total === 0 ? (
            <EmptyNote>
              Log calls and visits from the Today screen — this chart is the
              proof Meemoo adds people rather than replacing them.
            </EmptyNote>
          ) : (
            <>
              <LineChart
                values={contact.weekly.map((week) => week.count)}
                labels={contact.weekly.map((week) => week.week)}
                color="#a9c6e2"
                height={100}
              />
              <p className="mt-2 text-sm text-ink-soft">
                {Object.entries(contact.by_kind)
                  .map(([kind, count]) => `${count} ${kind}${count === 1 ? "" : "s"}`)
                  .join(" · ")}
              </p>
            </>
          )}
        </Card>
      </div>

      {abandonment && abandonment.signals.length > 0 && (
        <Card title="Early warnings">
          <ul className="list-inside list-disc text-sm text-ink-soft">
            {abandonment.signals.map((signal) => (
              <li key={signal}>{signal}</li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
