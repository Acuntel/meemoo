/** The Meemoo mark: a round, friendly beluga. The round head is the sphere
 * body itself (Art. I: fully stylized, soft, two-tone, no realism mixing). */

export function MeemooMark({ size = 28 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 52 52"
      role="img"
      aria-label="Meemoo"
    >
      {/* tail flukes, trailing like a happy swimmer */}
      <path
        d="M 39 27 Q 50 17 47.5 27 Q 50 37 39 27 Z"
        fill="#a9c6e2"
      />
      {/* the sphere body: one round beluga head */}
      <circle cx={23} cy={27} r={16} fill="#bcd4ea" />
      {/* soft belly tone, the second of the two tones */}
      <path
        d="M 9.5 33 A 16 16 0 0 0 36.5 33 Q 23 39.5 9.5 33 Z"
        fill="#a9c6e2"
        opacity={0.55}
      />
      {/* stylized face: dot eyes and a small smile, nothing realistic */}
      <circle cx={17.5} cy={24} r={2.1} fill="#40382f" />
      <circle cx={28.5} cy={24} r={2.1} fill="#40382f" />
      <path
        d="M 19.5 30.5 Q 23 33.5 26.5 30.5"
        stroke="#40382f"
        strokeWidth={1.8}
        fill="none"
        strokeLinecap="round"
      />
    </svg>
  );
}

/** Mark plus the lowercase wordmark, for the header. */
export function MeemooLogo() {
  return (
    <span className="flex items-center gap-2">
      <span className="animate-bob inline-block" aria-hidden="true">
        <MeemooMark size={32} />
      </span>
      <span className="text-xl font-semibold tracking-tight">meemoo</span>
    </span>
  );
}
