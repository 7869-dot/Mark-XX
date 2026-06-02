import { memo, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  IconMail, IconWorld, IconRadar, IconChevronDown, IconRefresh,
} from "@tabler/icons-react";
import { api, type SubAgentName, type SubAgentStatus } from "@/lib/api";

const META: Record<SubAgentName, { label: string; icon: React.ReactNode; run: "email" | "feed" | "web" }> = {
  email_agent: { label: "Email", icon: <IconMail size={15} />, run: "email" },
  feed_agent: { label: "World Feed", icon: <IconWorld size={15} />, run: "feed" },
  web_agent: { label: "Web Scout", icon: <IconRadar size={15} />, run: "web" },
};

function timeAgo(iso: string | null): string {
  if (!iso) return "never";
  const secs = Math.max(1, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (secs < 60) return `${secs}s ago`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}

/** Collapsible panel showing real-time status of the three sub-agents, each with
 * a "Run now" button that triggers an on-demand run and refreshes the briefing. */
function AgentStatusPanelImpl({ onRan }: { onRan?: () => void }) {
  const [open, setOpen] = useState(true);
  const [agents, setAgents] = useState<SubAgentStatus[] | null>(null);
  const [running, setRunning] = useState<string | null>(null);

  const load = () => api.agentsStatus().then((d) => setAgents(d.agents)).catch(() => setAgents([]));
  useEffect(() => { load(); }, []);

  const runNow = async (name: "email" | "feed" | "web") => {
    setRunning(name);
    try {
      await api.runSubAgent(name);
      await load();
      onRan?.();
    } catch {
      /* ignore */
    } finally {
      setRunning(null);
    }
  };

  return (
    <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-2.5"
        style={{ background: "var(--bg-elevated)" }}
      >
        <span className="text-xs tracking-wide" style={{ fontFamily: "var(--font-data)", color: "var(--text-secondary)" }}>
          AGENT TEAM
        </span>
        <motion.span animate={{ rotate: open ? 0 : -90 }} transition={{ duration: 0.2 }}>
          <IconChevronDown size={16} style={{ color: "var(--text-muted)" }} />
        </motion.span>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
          >
            <div className="divide-y" style={{ borderColor: "var(--border)" }}>
              {(agents || []).map((a) => {
                const meta = META[a.agent_name];
                if (!meta) return null;
                const busy = running === meta.run || a.status === "running";
                return (
                  <div key={a.agent_name} className="px-4 py-3 flex items-start gap-3">
                    <span style={{ color: "var(--accent-primary)" }} className="mt-0.5">{meta.icon}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm" style={{ color: "var(--text-primary)", fontWeight: 500 }}>
                          {meta.label}
                        </span>
                        <span className="text-[10px]" style={{ color: "var(--text-muted)", fontFamily: "var(--font-data)" }}>
                          {timeAgo(a.last_run)}
                        </span>
                      </div>
                      <p className="text-[12px] mt-0.5 leading-snug truncate" style={{ color: "var(--text-secondary)" }}>
                        {a.last_summary || "Idle — hasn't run yet."}
                      </p>
                    </div>
                    <button
                      onClick={() => runNow(meta.run)}
                      disabled={busy}
                      className="text-[11px] px-2 py-1 rounded inline-flex items-center gap-1 shrink-0"
                      style={{ border: "1px solid var(--border)", color: "var(--accent-primary)", opacity: busy ? 0.6 : 1 }}
                    >
                      <motion.span animate={busy ? { rotate: 360 } : {}} transition={busy ? { repeat: Infinity, duration: 0.8, ease: "linear" } : {}}>
                        <IconRefresh size={12} />
                      </motion.span>
                      {busy ? "Running" : "Run now"}
                    </button>
                  </div>
                );
              })}
              {agents === null && (
                <div className="px-4 py-4 text-[12px]" style={{ color: "var(--text-muted)" }}>Loading agents…</div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export const AgentStatusPanel = memo(AgentStatusPanelImpl);
