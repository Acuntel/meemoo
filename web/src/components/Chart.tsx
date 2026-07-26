/** Tiny dependency-free SVG charts, tuned to the warm palette. */

export function LineChart({
  values,
  labels,
  height = 120,
  color = "#7fa98e",
  markerIndex,
  markerLabel,
}: {
  values: number[];
  labels?: string[];
  height?: number;
  color?: string;
  markerIndex?: number;
  markerLabel?: string;
}) {
  const width = 560;
  const pad = 8;
  const max = Math.max(...values, 1);
  const stepX = values.length > 1 ? (width - pad * 2) / (values.length - 1) : 0;
  const point = (value: number, index: number): [number, number] => [
    pad + index * stepX,
    height - pad - (value / max) * (height - pad * 2),
  ];
  const path = values
    .map((value, index) => {
      const [x, y] = point(value, index);
      return `${index === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
  const area = `${path} L ${pad + (values.length - 1) * stepX} ${height - pad} L ${pad} ${height - pad} Z`;

  return (
    <svg viewBox={`0 0 ${width} ${height + 16}`} className="w-full">
      <path d={area} fill={color} opacity={0.12} />
      <path d={path} fill="none" stroke={color} strokeWidth={2.5} strokeLinecap="round" />
      {markerIndex !== undefined && markerIndex >= 0 && markerIndex < values.length && (
        <g>
          <line
            x1={pad + markerIndex * stepX}
            y1={pad}
            x2={pad + markerIndex * stepX}
            y2={height - pad}
            stroke="#dc9a8f"
            strokeWidth={1.5}
            strokeDasharray="4 4"
          />
          {markerLabel && (
            <text
              x={pad + markerIndex * stepX + 5}
              y={pad + 10}
              fontSize={11}
              fill="#dc9a8f"
            >
              {markerLabel}
            </text>
          )}
        </g>
      )}
      {labels && labels.length > 1 && (
        <>
          <text x={pad} y={height + 12} fontSize={10} fill="#b4a996">
            {labels[0]}
          </text>
          <text
            x={width - pad}
            y={height + 12}
            fontSize={10}
            fill="#b4a996"
            textAnchor="end"
          >
            {labels[labels.length - 1]}
          </text>
        </>
      )}
    </svg>
  );
}

export function Bars({
  values,
  height = 90,
  color = "#a9c6e2",
}: {
  values: number[];
  height?: number;
  color?: string;
}) {
  const width = 560;
  const gap = 3;
  const barWidth = Math.max(2, width / Math.max(values.length, 1) - gap);
  const max = Math.max(...values, 1);
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full">
      {values.map((value, index) => {
        const barHeight = (value / max) * (height - 8);
        return (
          <rect
            key={index}
            x={index * (barWidth + gap)}
            y={height - barHeight}
            width={barWidth}
            height={barHeight}
            rx={2}
            fill={color}
          />
        );
      })}
    </svg>
  );
}

export function StatCard({
  label,
  value,
  hint,
  tone = "sage",
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "sage" | "sky" | "peach" | "rose";
}) {
  const tones = {
    sage: "bg-sage-soft text-sage-deep",
    sky: "bg-sky-soft text-ink-soft",
    peach: "bg-peach-soft text-ink-soft",
    rose: "bg-rose-soft text-rose",
  } as const;
  return (
    <div className="rounded-3xl border border-line bg-card p-5 shadow-sm">
      <p className="text-sm text-ink-soft">{label}</p>
      <p className="mt-1 text-3xl font-semibold">{value}</p>
      {hint && (
        <span
          className={`mt-2 inline-block rounded-full px-2.5 py-0.5 text-xs ${tones[tone]}`}
        >
          {hint}
        </span>
      )}
    </div>
  );
}
