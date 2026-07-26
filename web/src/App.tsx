/** Meemoo — one warm shell: Family Dashboard tabs + the Setup Studio.
 * The simulated incoming-call overlay is always mounted, so an escalation
 * takes over the screen no matter which tab is open. */

import { useState } from "react";
import CallOverlay from "./components/CallOverlay";
import AlertsPage from "./pages/AlertsPage";
import HistoryPage from "./pages/HistoryPage";
import InsightsPage from "./pages/InsightsPage";
import LivePage from "./pages/LivePage";
import StudioPage from "./pages/studio/StudioPage";
import TodayPage from "./pages/TodayPage";
import { useSimStream } from "./lib/ws";

const TABS = [
  { key: "today", label: "Today" },
  { key: "live", label: "Live" },
  { key: "alerts", label: "Alerts" },
  { key: "history", label: "History" },
  { key: "insights", label: "Insights" },
  { key: "studio", label: "Studio" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

export default function App() {
  const [tab, setTab] = useState<TabKey>("today");
  const sim = useSimStream();

  return (
    <div className="min-h-screen">
      <CallOverlay />
      <header className="border-b border-line bg-card/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-6 py-4">
          <button
            type="button"
            onClick={() => setTab("today")}
            className="flex items-center gap-2 text-xl font-semibold tracking-tight"
          >
            <span className="animate-bob inline-block text-2xl" aria-hidden="true">
              🎈
            </span>
            Meemoo
          </button>
          <nav className="flex flex-1 flex-wrap items-center gap-1">
            {TABS.map((entry) => (
              <button
                key={entry.key}
                type="button"
                onClick={() => setTab(entry.key)}
                className={`rounded-full px-4 py-1.5 text-sm font-medium transition ${
                  tab === entry.key
                    ? "bg-sage text-white"
                    : "text-ink-soft hover:bg-sage-soft"
                }`}
              >
                {entry.label}
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
          <TodayPage snapshot={sim.snapshot} onGoLive={() => setTab("live")} />
        )}
        {tab === "live" && (
          <LivePage plan={sim.plan} snapshot={sim.snapshot} simReady={sim.ready} />
        )}
        {tab === "alerts" && <AlertsPage />}
        {tab === "history" && <HistoryPage />}
        {tab === "insights" && <InsightsPage />}
        {tab === "studio" && <StudioPage onDone={() => setTab("today")} />}
      </main>

      <footer className="mx-auto max-w-6xl px-6 pb-8 text-center text-xs text-ink-faint">
        Meemoo is an AI companion, not a person and not a medical device. It
        reports what it observes and rings the people you chose — it never
        diagnoses and never dials 911 by itself.
      </footer>
    </div>
  );
}
