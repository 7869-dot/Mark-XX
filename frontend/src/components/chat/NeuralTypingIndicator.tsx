import { motion } from "framer-motion";

/** Agent "thinking" indicator — a pulsing neural-net instead of the usual
 * three dots. Signal pulses travel input → hidden → output while the nodes
 * breathe, so it reads as a thought forming rather than a generic loader.
 *
 * Pure SVG + Framer Motion, no canvas. Honors prefers-reduced-motion via the
 * `reduced` prop (callers can pass a media-query result). */
const NODES: { x: number; y: number; layer: number }[] = [
  { x: 8, y: 8, layer: 0 },
  { x: 8, y: 24, layer: 0 },
  { x: 30, y: 6, layer: 1 },
  { x: 30, y: 16, layer: 1 },
  { x: 30, y: 26, layer: 1 },
  { x: 52, y: 16, layer: 2 },
];

// Every input→hidden and hidden→output pair (dense between adjacent layers).
const EDGES: [number, number][] = [];
for (const [i, a] of NODES.entries()) {
  for (const [j, b] of NODES.entries()) {
    if (b.layer === a.layer + 1) EDGES.push([i, j]);
  }
}

export function NeuralTypingIndicator({ reduced = false }: { reduced?: boolean }) {
  return (
    <div className="flex items-center gap-2 px-1 py-1.5" aria-label="agent is thinking">
      <svg width={60} height={32} viewBox="0 0 60 32" fill="none" role="img">
        {EDGES.map(([a, b], i) => {
          const n1 = NODES[a];
          const n2 = NODES[b];
          return (
            <motion.line
              key={`e${i}`}
              x1={n1.x}
              y1={n1.y}
              x2={n2.x}
              y2={n2.y}
              stroke="var(--accent-electric)"
              strokeWidth={1}
              initial={{ opacity: 0.1 }}
              animate={reduced ? { opacity: 0.25 } : { opacity: [0.08, 0.6, 0.08] }}
              transition={{
                duration: 1.4,
                repeat: Infinity,
                // Wave by layer then by index so the pulse "flows" left→right.
                delay: (n1.layer * 0.25) + (i % 3) * 0.08,
                ease: "easeInOut",
              }}
            />
          );
        })}
        {NODES.map((n, i) => (
          <motion.circle
            key={`n${i}`}
            cx={n.x}
            cy={n.y}
            r={2.4}
            fill="var(--accent-electric)"
            initial={{ opacity: 0.4 }}
            animate={
              reduced
                ? { opacity: 0.7 }
                : { opacity: [0.4, 1, 0.4], r: [2.2, 3, 2.2] }
            }
            transition={{
              duration: 1.4,
              repeat: Infinity,
              delay: n.layer * 0.25,
              ease: "easeInOut",
            }}
          />
        ))}
      </svg>
    </div>
  );
}
