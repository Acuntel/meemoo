import { useEffect, useState } from "react";

type Health = { status: string; service: string; version: string };

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/v1/health")
      .then((r) => (r.ok ? (r.json() as Promise<Health>) : null))
      .then((h) => {
        if (!cancelled && h !== null) setHealth(h);
      })
      .catch(() => {
        /* API not up yet — the shell still renders */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-950 text-slate-100">
      <div className="text-6xl" aria-hidden="true">
        🎈
      </div>
      <h1 className="text-4xl font-semibold tracking-tight">Meemoo</h1>
      <p className="text-slate-400">
        Round floating companion. The aircraft is dumb; the ground is smart.
      </p>
      <p className="text-sm text-slate-500">
        {health === null
          ? "API: connecting…"
          : `API: ${health.status} · v${health.version}`}
      </p>
    </main>
  );
}
