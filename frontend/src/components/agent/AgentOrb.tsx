import { motion } from "framer-motion";

type OrbState = "idle" | "thinking" | "alert";

const COLOR: Record<OrbState, string> = {
  idle: "#14D4B2", // teal-bright
  thinking: "#FFB300", // amber-bright
  alert: "#FF7043", // coral-bright
};

export function AgentOrb({
  state = "idle",
  size = 36,
}: {
  state?: OrbState;
  size?: number;
}) {
  const color = COLOR[state];
  return (
    <motion.div
      aria-label={`agent-${state}`}
      animate={{ scale: [1, 1.04, 1] }}
      transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
      style={{
        width: size,
        height: size,
        borderRadius: "9999px",
        background: `radial-gradient(circle at 35% 30%, ${color}, ${color}33 70%, transparent)`,
        boxShadow: `0 0 ${size * 0.55}px ${color}55, inset 0 0 ${size * 0.3}px ${color}66`,
        border: `1px solid ${color}66`,
      }}
    >
      <motion.div
        animate={{ opacity: [0.4, 0.9, 0.4] }}
        transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
        style={{
          width: "100%",
          height: "100%",
          borderRadius: "9999px",
          background: `radial-gradient(circle at 50% 50%, ${color}88, transparent 65%)`,
        }}
      />
    </motion.div>
  );
}

export function statusToOrbState(
  status?: string,
  thinking?: boolean
): "idle" | "thinking" | "alert" {
  if (thinking) return "thinking";
  if (status === "busy") return "thinking";
  if (status === "sleeping") return "alert";
  return "idle";
}
