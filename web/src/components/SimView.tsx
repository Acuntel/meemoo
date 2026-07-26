/** The 2D sim: floor plan + the round whale drifting with floaty easing. */

import type { FloorPlan, SimSnapshot } from "../lib/types";

const SCALE = 60; // px per meter

function phaseLabel(snapshot: SimSnapshot): string {
  if (snapshot.docked && snapshot.charging) return "On the dock, charging";
  if (snapshot.docked) return "Resting on the dock";
  const phase = snapshot.phase.toLowerCase().replace(/_/g, " ");
  if (snapshot.waypoint_label) return `Drifting to ${snapshot.waypoint_label}`;
  return `In the air — ${phase}`;
}

function Whale({ x, y, heading }: { x: number; y: number; heading: number }) {
  return (
    <g
      style={{
        transform: `translate(${x}px, ${y}px)`,
        transition: "transform 0.35s cubic-bezier(0.34, 1.2, 0.64, 1)",
      }}
    >
      <g className="animate-bob">
        <g style={{ transform: `rotate(${heading}deg)` }}>
          {/* tail + fins double as the character's tail (Art. I) */}
          <path d="M -20 0 Q -34 -12 -30 0 Q -34 12 -20 0 Z" fill="#a9c6e2" />
          <ellipse cx={0} cy={13} rx={9} ry={4} fill="#a9c6e2" opacity={0.8} />
        </g>
        <circle r={19} fill="#bcd4ea" />
        <circle r={19} fill="url(#whaleShine)" />
        <circle cx={-5} cy={-3} r={2.6} fill="#40382f" />
        <circle cx={7} cy={-3} r={2.6} fill="#40382f" />
        <path
          d="M -2 5 Q 1 8 4 5"
          stroke="#40382f"
          strokeWidth={1.6}
          fill="none"
          strokeLinecap="round"
        />
        <ellipse cx={-9} cy={4} rx={3.4} ry={2.2} fill="#f2c9a3" opacity={0.75} />
        <ellipse cx={11} cy={4} rx={3.4} ry={2.2} fill="#f2c9a3" opacity={0.75} />
      </g>
    </g>
  );
}

export default function SimView({
  plan,
  snapshot,
  compact = false,
}: {
  plan: FloorPlan;
  snapshot: SimSnapshot | null;
  compact?: boolean;
}) {
  const [x0, y0, x1, y1] = plan.bounds;
  const width = (x1 - x0) * SCALE;
  const height = (y1 - y0) * SCALE;
  const px = (x: number) => (x - x0) * SCALE;
  const py = (y: number) => (y - y0) * SCALE;

  return (
    <div className="rounded-3xl border border-line bg-card p-4 shadow-sm">
      <svg
        viewBox={`-10 -10 ${width + 20} ${height + 20}`}
        className="w-full"
        role="img"
        aria-label={`Floor plan of ${plan.name}`}
      >
        <defs>
          <radialGradient id="whaleShine" cx="0.35" cy="0.3" r="0.9">
            <stop offset="0%" stopColor="#ffffff" stopOpacity={0.75} />
            <stop offset="55%" stopColor="#ffffff" stopOpacity={0.08} />
            <stop offset="100%" stopColor="#7ea8cd" stopOpacity={0.35} />
          </radialGradient>
        </defs>
        {plan.rooms.map((room) => (
          <g key={room.name}>
            <rect
              x={px(room.x)}
              y={py(room.y)}
              width={room.w * SCALE}
              height={room.h * SCALE}
              rx={14}
              fill="#f6efe3"
              stroke="#ece4d6"
              strokeWidth={2}
            />
            <text
              x={px(room.x) + 12}
              y={py(room.y) + 22}
              fontSize={12}
              fill="#b4a996"
            >
              {room.name}
            </text>
          </g>
        ))}
        {plan.waypoints.map((wp) => (
          <g key={wp.label}>
            <circle
              cx={px(wp.x)}
              cy={py(wp.y)}
              r={wp.kind === "person" ? 8 : 5}
              fill={wp.kind === "person" ? "#f2c9a3" : "#e4efe7"}
              stroke={wp.kind === "person" ? "#e0a56f" : "#7fa98e"}
              strokeWidth={1.5}
            />
            {!compact && (
              <text
                x={px(wp.x) + 11}
                y={py(wp.y) + 4}
                fontSize={11}
                fill="#857a6c"
              >
                {wp.label}
              </text>
            )}
          </g>
        ))}
        {/* the dock — its own little device (Art. II §3) */}
        <g>
          <rect
            x={px(plan.dock.x) - 16}
            y={py(plan.dock.y) - 12}
            width={32}
            height={24}
            rx={9}
            fill="#e4efe7"
            stroke="#7fa98e"
            strokeWidth={2}
          />
          <circle cx={px(plan.dock.x)} cy={py(plan.dock.y)} r={5} fill="#7fa98e" />
        </g>
        {snapshot && (
          <Whale x={px(snapshot.x)} y={py(snapshot.y)} heading={snapshot.heading_deg} />
        )}
      </svg>
      {snapshot && (
        <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
          <span className="rounded-full bg-sage-soft px-3 py-1 text-sage-deep">
            {phaseLabel(snapshot)}
          </span>
          <span className="rounded-full bg-sky-soft px-3 py-1 text-ink-soft">
            Battery {Math.round(snapshot.battery_pct)}%
            {snapshot.charging ? " ⚡" : ""}
          </span>
          <span className="rounded-full bg-peach-soft px-3 py-1 text-ink-soft">
            Helium {snapshot.helium_level_pct.toFixed(1)}%
          </span>
          {!compact && (
            <span className="rounded-full bg-cream px-3 py-1 text-ink-faint">
              Trim {snapshot.net_buoyancy_gf.toFixed(1)} g
            </span>
          )}
        </div>
      )}
    </div>
  );
}
