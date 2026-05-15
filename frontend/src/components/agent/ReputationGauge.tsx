import { useEffect, useState } from "react";

export function ReputationGauge({
  score,
  size = 120,
}: {
  score: number;
  size?: number;
}) {
  const [animated, setAnimated] = useState(0);

  useEffect(() => {
    let raf = 0;
    let start: number | null = null;
    const from = animated;
    const duration = 800;
    const tick = (t: number) => {
      if (start == null) start = t;
      const p = Math.min(1, (t - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setAnimated(from + (score - from) * eased);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [score]);

  const radius = size / 2 - 8;
  const circ = 2 * Math.PI * radius;
  const dash = (animated / 100) * circ;
  const color =
    animated >= 70 ? "#00f5d4" : animated >= 40 ? "#ffb347" : "#ff6b6b";

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={8}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={8}
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circ - dash}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ filter: `drop-shadow(0 0 8px ${color})` }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-display text-2xl text-white tabular-nums">
          {Math.round(animated)}
        </span>
        <span className="label-mono">REPUTATION</span>
      </div>
    </div>
  );
}
