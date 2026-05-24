/**
 * Deterministic geometric SVG avatar from a personality_vector.
 *
 * Algorithm (per spec — same vector ALWAYS yields the same SVG):
 *   openness        → polygon sides        (3 = triangle … 8 = octagon)
 *   ambition        → size                 (larger = more ambitious)
 *   sociability     → orbital rings         (0 … 3 rings around the shape)
 *   directness      → color                 (high = cyan #00f5d4, low = purple #7F77DD)
 *   risk_tolerance  → solid vs. outlined    (>= 0.5 solid, else outline only)
 *
 * SVG only, no canvas, no randomness.
 */
function lerpColor(t: number): string {
  // t=1 → cyan #00f5d4 (0,245,212), t=0 → purple #7F77DD (127,119,221)
  const c1 = [0, 245, 212];
  const c0 = [127, 119, 221];
  const r = Math.round(c0[0] + (c1[0] - c0[0]) * t);
  const g = Math.round(c0[1] + (c1[1] - c0[1]) * t);
  const b = Math.round(c0[2] + (c1[2] - c0[2]) * t);
  return `rgb(${r}, ${g}, ${b})`;
}

export function AgentAvatar({
  seed,
  personality,
  size = 56,
  className = "",
}: {
  seed?: string;
  personality?: Record<string, number>;
  size?: number;
  className?: string;
}) {
  const p = {
    openness: personality?.openness ?? 0.5,
    directness: personality?.directness ?? 0.5,
    ambition: personality?.ambition ?? 0.5,
    sociability: personality?.sociability ?? 0.5,
    risk_tolerance: personality?.risk_tolerance ?? 0.5,
  };

  const cx = size / 2;
  const cy = size / 2;

  // An emoji seed (chosen in onboarding) renders as a glyph instead of the
  // geometric shape. UUID seeds — the default — never match this.
  const isEmojiSeed =
    !!seed && /\p{Extended_Pictographic}/u.test(seed) && [...seed].length <= 4;
  if (isEmojiSeed) {
    return (
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className={className}
        role="img"
        aria-label="Agent avatar"
      >
        <circle cx={cx} cy={cy} r={size / 2 - 1} fill="#0d1320" />
        <text
          x={cx}
          y={cy}
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={size * 0.5}
        >
          {seed}
        </text>
      </svg>
    );
  }

  // openness → 3..8 sides
  const sides = 3 + Math.round(p.openness * 5);
  // ambition → shape size as a fraction of the canvas (0.45 .. 0.85)
  const shapeRadius = (size / 2) * (0.45 + p.ambition * 0.4);
  // sociability → 0..3 orbital rings
  const rings = Math.round(p.sociability * 3);
  // directness → color
  const color = lerpColor(p.directness);
  // risk_tolerance → solid or outline
  const solid = p.risk_tolerance >= 0.5;

  const polygon = Array.from({ length: sides }, (_, i) => {
    // start at -90deg so the shape points up; fully deterministic
    const angle = (i / sides) * Math.PI * 2 - Math.PI / 2;
    return `${cx + Math.cos(angle) * shapeRadius},${cy + Math.sin(angle) * shapeRadius}`;
  }).join(" ");

  const gradId = `axo-grad-${sides}-${Math.round(p.directness * 100)}`;

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className={className}
      role="img"
      aria-label="Agent avatar"
    >
      <defs>
        <radialGradient id={gradId} cx="50%" cy="50%">
          <stop offset="0%" stopColor={color} stopOpacity="0.85" />
          <stop offset="100%" stopColor={color} stopOpacity="0.08" />
        </radialGradient>
      </defs>

      <circle cx={cx} cy={cy} r={size / 2 - 1} fill="#0d1320" />

      {Array.from({ length: rings }, (_, i) => {
        const rr = shapeRadius + 4 + i * ((size / 2 - shapeRadius - 2) / Math.max(rings, 1));
        return (
          <circle
            key={`ring-${i}`}
            cx={cx}
            cy={cy}
            r={rr}
            fill="none"
            stroke={color}
            strokeOpacity={0.28 - i * 0.05}
            strokeWidth={0.8}
          />
        );
      })}

      <polygon
        points={polygon}
        fill={solid ? `url(#${gradId})` : "none"}
        stroke={color}
        strokeWidth={solid ? 1 : 1.6}
        strokeOpacity={0.95}
        strokeLinejoin="round"
      />

      {solid && <circle cx={cx} cy={cy} r={shapeRadius * 0.16} fill={color} />}
    </svg>
  );
}
