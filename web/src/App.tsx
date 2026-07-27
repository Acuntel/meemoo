/** Meemoo, one warm shell: Today / Studio / Live / History (Amendment A7).
 * When something is live (round in progress or an alert is open) the Live tab
 * jumps to first position with a red pulse. The simulated incoming-call
 * overlay is always mounted, so an escalation takes over the screen no matter
 * which tab is open. */

import { useCallback, useEffect, useState } from "react";
import CallOverlay from "./components/CallOverlay";
import { MeemooLogo } from "./components/Logo";
import HistoryPage from "./pages/HistoryPage";
import LivePage from "./pages/LivePage";
import StudioPage from "./pages/studio/StudioPage";
import TodayPage from "./pages/TodayPage";
import { apiGet } from "./lib/api";
import type { Alert, BusEvent } from "./lib/types";
import { useEventStream, useSimStream } from "./lib/ws";

type TabKey = "today" | "studio" | "live" | "history";

const TAB_LABELS: Record<TabKey, string> = {
  today: "Today",
  studio: "Studio",
  live: "Live",
  history: "History",
};

const RESTING_ORDER: TabKey[] = ["today", "studio", "live", "history"];
const LIVE_ORDER: TabKey[] = ["live", "today", "studio", "history"];

export default function App() {
  const [tab, setTab] = useState<TabKey>("today");
  const [activeAlerts, setActiveAlerts] = useState<Alert[]>([]);
  const sim = useSimStream();

  const refreshAlerts = useCallback(() => {
    apiGet<Alert[]>("/api/v1/alerts?device_id=1")
      .then((rows) => setActiveAlerts(rows.filter((a) => a.acknowledged_at === null)))
      .catch(() => setActiveAlerts([]));
  }, []);

  useEffect(() => {
    refreshAlerts();
    const timer = window.setInterval(refreshAlerts, 10_000);
    return () => window.clearInterval(timer);
  }, [refreshAlerts]);

  const onEvent = useCallback(
    (event: BusEvent) => {
      if (
        event.topic.startsWith("escalation.") ||
        event.topic.startsWith("notify.")
      ) {
        refreshAlerts();
      }
    },
    [refreshAlerts],
  );
  useEventStream(onEvent);

  const roundActive = sim.snapshot !== null && !sim.snapshot.docked;
  const isLive = roundActive || activeAlerts.length > 0;
  const order = isLive ? LIVE_ORDER : RESTING_ORDER;

  return (
    <div className="min-h-screen">
      <CallOverlay />
      <header className="border-b border-line bg-card/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-6 py-4">
          <button type="button" onClick={() => setTab(order[0] ?? "today")}>
            <MeemooLogo />
          </button>
          <nav className="flex flex-1 flex-wrap items-center gap-1">
            {order.map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => setTab(key)}
                className={`flex items-center gap-2 rounded-full px-4 py-1.5 text-sm font-medium transition ${
                  tab === key
                    ? "bg-sage text-white"
                    : "text-ink-soft hover:bg-sage-soft"
                }`}
              >
                {TAB_LABELS[key]}
                {key === "live" && isLive && (
                  <span
                    className="animate-dot h-2 w-2 rounded-full bg-alert"
                    aria-label="Something is happening live"
                  />
                )}
              </button>
            ))}
          </nav>
          <span
            className={`flex items-center gap-2 text-sm ${
              sim.ready ? "text-sage-deep" : "text-ink-faint"
            }`}
          >
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                sim.ready ? "bg-sage" : "bg-line"
              }`}
            />
            {sim.ready ? "Meemoo is home" : "offline"}
          </span>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8">
        {tab === "today" && (
          <TodayPage
            plan={sim.plan}
            snapshot={sim.snapshot}
            simReady={sim.ready}
            activeAlerts={activeAlerts}
            onGoLive={() => setTab("live")}
          />
        )}
        {tab === "live" && (
          <LivePage
            plan={sim.plan}
            snapshot={sim.snapshot}
            simReady={sim.ready}
            activeAlerts={activeAlerts}
            onAlertsChanged={refreshAlerts}
          />
        )}
        {tab === "history" && <HistoryPage />}
        {tab === "studio" && <StudioPage onDone={() => setTab("today")} />}
      </main>

      <footer className="mx-auto max-w-6xl px-6 pb-8 text-center text-xs text-ink-faint">
        Meemoo is an AI companion, not a person and not a medical device. It
        reports what it observes and rings the people you chose. It never
        diagnoses, and it never dials 911 by itself.
      </footer>
    </div>
  );
}
