/** Flight Test bench: four sliders and a STOP that fly the whale today and
 * the real airframe later (same API, UDP bridge underneath at hardware time).
 * Refusals surface honestly: docked, capture finishing, off-limit zones, and
 * the 1.3 m/s governor all say so in plain words. */

import { useCallback, useEffect, useRef, useState } from "react";
import SimView from "../components/SimView";
import { MeemooLogo } from "../components/Logo";
import { Button, Card, EmptyNote } from "../components/ui";
import { apiGet, apiPost } from "../lib/api";
import type { BusEvent, FlightTestState } from "../lib/types";
import { useEventStream, useSimStream } from "../lib/ws";

const SEND_EVERY_MS = 300;

type ControlResult = { accepted: boolean; reason: string | null };

function AxisSlider({
  label,
  low,
  high,
  value,
  onChange,
  onRelease,
}: {
  label: string;
  low: string;
  high: string;
  value: number;
  onChange: (v: number) => void;
  onRelease: () => void;
}) {
  return (
    <div className="rounded-2xl bg-cream p-4">
      <div className="mb-1 flex items-baseline justify-between">
        <span className="text-sm font-medium">{label}</span>
        <span className="font-mono text-xs text-ink-faint">
          {(value * 100).toFixed(0)}%
        </span>
      </div>
      <input
        type="range"
        min={-100}
        max={100}
        value={Math.round(value * 100)}
        aria-label={label}
        onChange={(e) => onChange(Number(e.target.value) / 100)}
        onPointerUp={onRelease}
        onTouchEnd={onRelease}
        onKeyUp={(e) => {
          if (e.key === " " || e.key === "Escape") onRelease();
        }}
        className="w-full accent-sage"
      />
      <div className="flex justify-between text-xs text-ink-faint">
        <span>{low}</span>
        <span>{high}</span>
      </div>
    </div>
  );
}

export default function FlightTestPage() {
  const sim = useSimStream();
  const [state, setState] = useState<FlightTestState | null>(null);
  const [forward, setForward] = useState(0);
  const [vertical, setVertical] = useState(0);
  const [yaw, setYaw] = useState(0);
  const [power, setPower] = useState(60);
  const [notice, setNotice] = useState<string | null>(null);
  const frame = useRef({ forward: 0, vertical: 0, yaw: 0 });
  frame.current = {
    forward: (forward * power) / 100,
    vertical: (vertical * power) / 100,
    yaw: (yaw * power) / 100,
  };

  // Telemetry strip poll.
  useEffect(() => {
    const poll = () =>
      apiGet<FlightTestState>("/api/v1/flight-test/state")
        .then(setState)
        .catch(() => setState(null));
    poll();
    const timer = window.setInterval(poll, 500);
    return () => window.clearInterval(timer);
  }, []);

  // Slider frames re-send while held; letting go sends one zero frame and the
  // 1 s server-side expiry brakes to a hover (the HTTP twin of the packet ttl).
  const active = forward !== 0 || vertical !== 0 || yaw !== 0;
  useEffect(() => {
    if (!active) return;
    let stale = false;
    const send = () => {
      apiPost<ControlResult>("/api/v1/flight-test/control", frame.current)
        .then((r) => {
          if (!stale) setNotice(r.accepted ? null : r.reason);
        })
        .catch((e: Error) => {
          if (!stale) setNotice(e.message);
        });
    };
    send();
    const timer = window.setInterval(send, SEND_EVERY_MS);
    return () => {
      stale = true;
      window.clearInterval(timer);
      void apiPost("/api/v1/flight-test/control", {
        forward: 0,
        vertical: 0,
        yaw: 0,
      }).catch(() => undefined);
    };
  }, [active]);

  // Off-limit refusals arrive on the bus; show them in the same notice line.
  const onEvent = useCallback((event: BusEvent) => {
    if (event.topic === "flight.refused") {
      setNotice(String(event.payload.reason ?? "That flight was refused."));
    }
  }, []);
  useEventStream(onEvent);

  const releaseAll = () => {
    setForward(0);
    setVertical(0);
    setYaw(0);
  };

  const stop = () => {
    releaseAll();
    apiPost<ControlResult>("/api/v1/flight-test/stop")
      .then(() => setNotice("Stopped. Meemoo is braking to a hover."))
      .catch((e: Error) => setNotice(e.message));
  };

  const simpleAction = (path: string) => {
    apiPost<ControlResult>(`/api/v1/flight-test/${path}`)
      .then((r) => setNotice(r.accepted ? null : r.reason))
      .catch((e: Error) => setNotice(e.message));
  };

  const capOn = state !== null && state.ready && state.cap_engaged;

  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-card/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-6 py-4">
          <a href="/">
            <MeemooLogo />
          </a>
          <span className="text-sm font-semibold text-ink-soft">
            Flight Test bench
          </span>
          <a href="/" className="ml-auto text-sm text-ink-faint hover:underline">
            Back to Meemoo
          </a>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-6 px-6 py-8">
        {/* Telemetry strip */}
        <div className="flex flex-wrap items-center gap-2 text-sm">
          {state === null || !state.ready ? (
            <span className="rounded-full bg-cream px-3 py-1 text-ink-faint">
              No aircraft is running. Start the app with the runtime on.
            </span>
          ) : (
            <>
              <span
                className={`rounded-full px-3 py-1 font-mono ${
                  capOn ? "bg-rose-soft text-rose" : "bg-sky-soft text-ink-soft"
                }`}
              >
                {state.speed_mps.toFixed(2)} / {state.speed_cap_mps.toFixed(1)} m/s
              </span>
              {capOn && (
                <span className="rounded-full bg-rose-soft px-3 py-1 text-rose">
                  At the speed cap. Meemoo will not go faster.
                </span>
              )}
              <span className="rounded-full bg-cream px-3 py-1 font-mono text-ink-soft">
                alt {state.altitude_m.toFixed(2)} m
              </span>
              <span className="rounded-full bg-cream px-3 py-1 font-mono text-ink-soft">
                hdg {Math.round(state.heading_deg)}
              </span>
              <span className="rounded-full bg-sky-soft px-3 py-1 text-ink-soft">
                Battery {Math.round(state.battery_pct)}%
                {state.charging ? " charging" : ""}
              </span>
              <span className="rounded-full bg-peach-soft px-3 py-1 text-ink-soft">
                Trim {state.net_buoyancy_gf.toFixed(1)} g
              </span>
              <span className="rounded-full bg-sage-soft px-3 py-1 text-sage-deep">
                {state.manual_active ? "Your hands on the sticks" : state.mode}
              </span>
            </>
          )}
        </div>

        {notice && (
          <p className="rounded-2xl bg-peach-soft px-4 py-3 text-sm text-ink-soft">
            {notice}
          </p>
        )}

        <div className="grid gap-6 lg:grid-cols-2">
          <div>
            {sim.plan ? (
              <SimView plan={sim.plan} snapshot={sim.snapshot} />
            ) : (
              <Card>
                <EmptyNote>
                  The flight view appears when the simulator is running.
                </EmptyNote>
              </Card>
            )}
          </div>

          <Card
            title="Sliders"
            hint="Same controls the real airframe will obey over WiFi"
          >
            <div className="space-y-3">
              <AxisSlider
                label="Up / down"
                low="down"
                high="up"
                value={vertical}
                onChange={setVertical}
                onRelease={() => setVertical(0)}
              />
              <AxisSlider
                label="Forward / back"
                low="back"
                high="forward"
                value={forward}
                onChange={setForward}
                onRelease={() => setForward(0)}
              />
              <AxisSlider
                label="Turn left / right"
                low="left"
                high="right"
                value={yaw}
                onChange={setYaw}
                onRelease={() => setYaw(0)}
              />
              <div className="rounded-2xl bg-cream p-4">
                <div className="mb-1 flex items-baseline justify-between">
                  <span className="text-sm font-medium">Power</span>
                  <span className="font-mono text-xs text-ink-faint">{power}%</span>
                </div>
                <input
                  type="range"
                  min={10}
                  max={100}
                  value={power}
                  aria-label="Power"
                  onChange={(e) => setPower(Number(e.target.value))}
                  className="w-full accent-sage"
                />
                <p className="mt-1 text-xs text-ink-faint">
                  Scales the other three sliders. Start gentle.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-3 pt-2">
                <button
                  type="button"
                  onClick={stop}
                  className="rounded-full bg-alert px-8 py-3 text-base font-bold text-white shadow-sm transition hover:opacity-90"
                >
                  STOP
                </button>
                <Button kind="soft" onClick={() => simpleAction("takeoff")}>
                  Lift off
                </Button>
                <Button kind="quiet" onClick={() => simpleAction("dock")}>
                  Go dock
                </Button>
              </div>
              <p className="text-xs text-ink-faint">
                Sliders spring back when you let go, and Meemoo brakes to a
                hover about a second later. Off-limit rooms stay off limits
                here too.
              </p>
            </div>
          </Card>
        </div>
      </main>
    </div>
  );
}
