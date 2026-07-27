/** Clickable floor plan for onboarding: tap to drop pins, drag to draw
 * off-limit rectangles. Purely presentational; parents own the data. */

import { useRef, useState } from "react";
import type { PointerEvent, ReactNode } from "react";
import type { FloorPlan, NoGoZone } from "../../lib/types";

const SCALE = 60; // px per meter, matching SimView

export type Pin = { label: string; x: number; y: number };
export type DraftRect = { x: number; y: number; w: number; h: number };

export default function PlanCanvas({
  plan,
  pins = [],
  zones = [],
  onTap,
  onDrawRect,
  children,
}: {
  plan: FloorPlan;
  pins?: Pin[];
  zones?: (NoGoZone | (DraftRect & { name: string }))[];
  onTap?: (x: number, y: number) => void;
  onDrawRect?: (rect: DraftRect) => void;
  children?: ReactNode;
}) {
  const [x0, y0, x1, y1] = plan.bounds;
  const width = (x1 - x0) * SCALE;
  const height = (y1 - y0) * SCALE;
  const px = (x: number) => (x - x0) * SCALE;
  const py = (y: number) => (y - y0) * SCALE;
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);
  const [dragNow, setDragNow] = useState<{ x: number; y: number } | null>(null);

  const toPlan = (event: PointerEvent<SVGSVGElement>) => {
    const svg = svgRef.current;
    if (!svg) return null;
    const rect = svg.getBoundingClientRect();
    const scaleX = (width + 20) / rect.width;
    const scaleY = (height + 20) / rect.height;
    const localX = (event.clientX - rect.left) * scaleX - 10;
    const localY = (event.clientY - rect.top) * scaleY - 10;
    const x = Math.min(Math.max(localX / SCALE + x0, x0), x1);
    const y = Math.min(Math.max(localY / SCALE + y0, y0), y1);
    return { x: Math.round(x * 100) / 100, y: Math.round(y * 100) / 100 };
  };

  const onPointerDown = (event: PointerEvent<SVGSVGElement>) => {
    const point = toPlan(event);
    if (!point) return;
    if (onDrawRect) {
      setDragStart(point);
      setDragNow(point);
      event.currentTarget.setPointerCapture(event.pointerId);
    }
  };

  const onPointerMove = (event: PointerEvent<SVGSVGElement>) => {
    if (dragStart) setDragNow(toPlan(event));
  };

  const onPointerUp = (event: PointerEvent<SVGSVGElement>) => {
    const point = toPlan(event);
    if (dragStart && point && onDrawRect) {
      const w = Math.abs(point.x - dragStart.x);
      const h = Math.abs(point.y - dragStart.y);
      if (w >= 0.3 && h >= 0.3) {
        onDrawRect({
          x: Math.min(dragStart.x, point.x),
          y: Math.min(dragStart.y, point.y),
          w: Math.round(w * 100) / 100,
          h: Math.round(h * 100) / 100,
        });
      } else if (onTap) {
        onTap(point.x, point.y);
      }
    } else if (point && onTap) {
      onTap(point.x, point.y);
    }
    setDragStart(null);
    setDragNow(null);
  };

  const draft: DraftRect | null =
    dragStart && dragNow
      ? {
          x: Math.min(dragStart.x, dragNow.x),
          y: Math.min(dragStart.y, dragNow.y),
          w: Math.abs(dragNow.x - dragStart.x),
          h: Math.abs(dragNow.y - dragStart.y),
        }
      : null;

  return (
    <svg
      ref={svgRef}
      viewBox={`-10 -10 ${width + 20} ${height + 20}`}
      className="w-full touch-none rounded-2xl border border-line bg-card"
      role="img"
      aria-label={`Floor plan of ${plan.name}`}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
    >
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
          <text x={px(room.x) + 12} y={py(room.y) + 22} fontSize={12} fill="#b4a996">
            {room.name}
          </text>
        </g>
      ))}
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
      {zones.map((zone, index) => (
        <g key={"id" in zone ? `z${zone.id}` : `draft${index}`}>
          <rect
            x={px(zone.x)}
            y={py(zone.y)}
            width={zone.w * SCALE}
            height={zone.h * SCALE}
            rx={10}
            fill="#dc6454"
            fillOpacity={0.14}
            stroke="#dc6454"
            strokeDasharray="6 4"
            strokeWidth={2}
          />
          <text
            x={px(zone.x) + 8}
            y={py(zone.y) + 18}
            fontSize={11}
            fill="#dc6454"
          >
            {zone.name}
          </text>
        </g>
      ))}
      {draft && draft.w > 0.05 && (
        <rect
          x={px(draft.x)}
          y={py(draft.y)}
          width={draft.w * SCALE}
          height={draft.h * SCALE}
          rx={10}
          fill="#dc6454"
          fillOpacity={0.1}
          stroke="#dc6454"
          strokeDasharray="4 4"
          strokeWidth={1.5}
        />
      )}
      {pins.map((pin, index) => (
        <g key={`${pin.label}-${index}`}>
          <circle cx={px(pin.x)} cy={py(pin.y)} r={7} fill="#f2c9a3" stroke="#e0a56f" strokeWidth={1.5} />
          <text x={px(pin.x) + 10} y={py(pin.y) + 4} fontSize={11} fill="#857a6c">
            {pin.label}
          </text>
        </g>
      ))}
      {children}
    </svg>
  );
}
