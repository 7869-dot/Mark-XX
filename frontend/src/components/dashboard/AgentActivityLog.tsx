/** Live activity feed: "what your agent did" — fed by /agent/activity. */
import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Mail,
  Send,
  MessageSquare,
  Sparkles,
  ListChecks,
  AlarmClock,
  Brain,
  Activity,
} from "lucide-react";
import type { ReactNode } from "react";
import { api, type AgentActivityItem } from "@/lib/api";

const ICONS: Record<string, ReactNode> = {
  email_classified: <Mail size={14} />,
  email_drafted: <Mail size={14} />,
  email_sent: <Send size={14} />,
  a2a_sent: <Send size={14} />,
  a2a_received: <MessageSquare size={14} />,
  a2a_replied: <MessageSquare size={14} />,
  chat_handled: <Sparkles size={14} />,
  task_completed: <ListChecks size={14} />,
  reminder_scheduled: <AlarmClock size={14} />,
  memory_captured: <Brain size={14} />,
  other: <Activity size={14} />,
};

function relTime(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
}

export function AgentActivityLog() {
  const [items, setItems] = useState<AgentActivityItem[] | null>(null);

  const load = async () => {
    try {
      const res = await api.agentActivity();
      setItems(res.items);
    } catch {
      setItems([]);
    }
  };

  useEffect(() => {
    load();
    // 15s — snappier "proof of life" than the previous 30s. Cheap query.
    const id = setInterval(load, 15_000);
    return () => clearInterval(id);
  }, []);

  return (
    <section className="panel p-4">
      <div className="mb-3">
        <div className="label-mono">Live activity</div>
        <h2
          className="text-base mt-0.5"
          style={{ fontFamily: "var(--font-display)" }}
        >
          What your agent did
        </h2>
      </div>

      {items === null && (
        <div className="space-y-2">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-7" />
          ))}
        </div>
      )}

      {items?.length === 0 && (
        <p
          className="text-[13px] py-2"
          style={{ color: "var(--text-secondary)" }}
        >
          Your agent hasn't done anything yet. Talk to it or wait for the next
          scheduled sweep.
        </p>
      )}

      {items && items.length > 0 && (
        <ul className="space-y-1.5">
          <AnimatePresence initial={false}>
            {items.map((it) => (
              <motion.li
                key={it.id}
                layout
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.22, ease: "easeOut" }}
                className="flex items-start gap-2.5 px-2 py-1.5 rounded"
                style={{ color: "var(--text-primary)" }}
              >
                <span
                  className="mt-0.5 shrink-0"
                  style={{ color: "var(--accent-primary)" }}
                >
                  {ICONS[it.action_type] || ICONS.other}
                </span>
                <span
                  className="text-[13px] flex-1"
                  style={{ fontFamily: "var(--font-body)" }}
                >
                  {it.description}
                </span>
                <span
                  className="text-[11px] shrink-0"
                  style={{
                    color: "var(--text-muted)",
                    fontFamily: "var(--font-data)",
                  }}
                >
                  {relTime(it.created_at)}
                </span>
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      )}
    </section>
  );
}
