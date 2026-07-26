/** Small shared UI primitives — one warm, rounded voice for every screen. */

import type { ReactNode } from "react";

export function Card({
  title,
  hint,
  children,
  className = "",
}: {
  title?: string;
  hint?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-3xl border border-line bg-card p-6 shadow-sm ${className}`}
    >
      {(title || hint) && (
        <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
          {title && <h2 className="text-lg font-semibold">{title}</h2>}
          {hint && <span className="text-sm text-ink-faint">{hint}</span>}
        </div>
      )}
      {children}
    </section>
  );
}

export function Chip({
  children,
  tone = "sage",
  onRemove,
}: {
  children: ReactNode;
  tone?: "sage" | "sky" | "peach" | "rose" | "plain";
  onRemove?: () => void;
}) {
  const tones = {
    sage: "bg-sage-soft text-sage-deep",
    sky: "bg-sky-soft text-ink-soft",
    peach: "bg-peach-soft text-ink-soft",
    rose: "bg-rose-soft text-rose",
    plain: "bg-cream text-ink-faint",
  } as const;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm ${tones[tone]}`}
    >
      {children}
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          aria-label="Remove"
          className="-mr-1 rounded-full px-1 leading-none opacity-60 transition hover:opacity-100"
        >
          ×
        </button>
      )}
    </span>
  );
}

export function Button({
  children,
  onClick,
  kind = "primary",
  disabled = false,
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  kind?: "primary" | "soft" | "quiet" | "danger";
  disabled?: boolean;
  type?: "button" | "submit";
}) {
  const kinds = {
    primary: "bg-sage text-white hover:bg-sage-deep shadow-sm",
    soft: "bg-sage-soft text-sage-deep hover:bg-sage/25",
    quiet: "bg-transparent text-ink-soft hover:bg-cream",
    danger: "bg-rose-soft text-rose hover:bg-rose/25",
  } as const;
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`rounded-full px-5 py-2 text-sm font-semibold transition disabled:cursor-default disabled:opacity-50 ${kinds[kind]}`}
    >
      {children}
    </button>
  );
}

export function Toggle({
  checked,
  onChange,
  label,
  detail,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  detail?: string;
}) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-4 py-2">
      <span>
        <span className="block font-medium">{label}</span>
        {detail && <span className="block text-sm text-ink-faint">{detail}</span>}
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        className={`relative h-7 w-12 shrink-0 rounded-full transition ${
          checked ? "bg-sage" : "bg-line"
        }`}
      >
        <span
          className={`absolute top-1 h-5 w-5 rounded-full bg-white shadow transition-all ${
            checked ? "left-6" : "left-1"
          }`}
        />
      </button>
    </label>
  );
}

export function EmptyNote({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-2xl bg-cream px-4 py-6 text-center text-sm text-ink-faint">
      {children}
    </p>
  );
}

/** Clearly-labeled synthetic-data banner (research 07 §F.15 — never silent). */
export function SyntheticBanner({ label }: { label?: string }) {
  return (
    <div className="rounded-2xl border border-peach bg-peach-soft px-4 py-2 text-sm font-medium text-ink-soft">
      {label ?? "SYNTHETIC DEMO DATA — not a real resident"}
    </div>
  );
}
