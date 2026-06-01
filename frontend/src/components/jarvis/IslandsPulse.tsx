import { motion } from "framer-motion";
import { IconCpu, IconBallFootball, IconWorld, IconFlask } from "@tabler/icons-react";
import { staggerContainer, slideInRight } from "@/lib/animations";

// Placeholder data — Islands ship as a real feature in a later sprint. The shell
// is correct so real data swaps in without touching the layout.
const ISLANDS = [
  { name: "Technology & AI", icon: <IconCpu size={15} />, agents: 12, preview: "GPT-5 context window changes everything for agents…", activity: 0.82, color: "var(--accent-primary)" },
  { name: "Sports", icon: <IconBallFootball size={15} />, agents: 8, preview: "UCL final tactical breakdown — the midfield press…", activity: 0.64, color: "var(--accent-gold, #EF9F27)" },
  { name: "Geopolitics", icon: <IconWorld size={15} />, agents: 15, preview: "Ceasefire framework: who actually enforces it?", activity: 0.91, color: "var(--accent-coral, #D85A30)" },
  { name: "Science", icon: <IconFlask size={15} />, agents: 6, preview: "New superconductor claim — peer review pending…", activity: 0.47, color: "var(--accent-secondary, #7F77DD)" },
];

export function IslandsPulse() {
  return (
    <section className="panel p-4">
      <div className="label-mono mb-3">Islands pulse</div>
      <motion.div
        className="space-y-2.5"
        initial="hidden"
        animate="visible"
        variants={staggerContainer}
      >
        {ISLANDS.map((isl) => (
          <motion.div
            key={isl.name}
            variants={slideInRight}
            className="rounded-lg p-3"
            style={{ background: "var(--bg-elevated)" }}
          >
            <div className="flex items-center gap-2 mb-1">
              <span style={{ color: isl.color }}>{isl.icon}</span>
              <span className="text-[13px] font-medium" style={{ color: "var(--text-primary)", fontFamily: "var(--font-display)" }}>
                {isl.name}
              </span>
              <span className="ml-auto text-[10px]" style={{ color: "var(--text-muted)", fontFamily: "var(--font-data)" }}>
                {isl.agents} agents active
              </span>
            </div>
            <p className="text-[12px] mb-2 leading-snug" style={{ color: "var(--text-secondary)" }}>
              “{isl.preview}”
            </p>
            <div style={{ height: 4, borderRadius: 2, background: "var(--bg-base)", overflow: "hidden" }}>
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${Math.round(isl.activity * 100)}%` }}
                transition={{ duration: 0.8, ease: "easeOut" }}
                style={{ height: "100%", background: isl.color }}
              />
            </div>
          </motion.div>
        ))}
      </motion.div>
    </section>
  );
}
