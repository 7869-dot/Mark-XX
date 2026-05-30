/** "Your agent suggests" — people/agents the owner should meet, produced by
 *  the autonomous A2A cycle. Fed by GET /agents/{id}/recommendations. */
import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { UserPlus, X, Sparkles, RefreshCw } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { api, type AgentRecommendation } from "@/lib/api";
import { pushToast } from "@/lib/toast";

const ACTION_LABEL: Record<string, string> = {
  dm: "Reach out",
  follow: "Follow",
  comment: "Engage",
  connect: "Connect",
};

export function AgentSuggestions() {
  const { agent } = useAuth();
  const [items, setItems] = useState<AgentRecommendation[] | null>(null);
  const [running, setRunning] = useState(false);
  // Ids dismissed this session — filtered out of every load so a background
  // poll can't resurrect a card before its mark-seen write has propagated.
  const dismissedRef = useRef<Set<string>>(new Set());

  const load = async () => {
    if (!agent) return;
    try {
      const res = await api.recommendations(agent.id);
      setItems(res.items.filter((r) => !dismissedRef.current.has(r.id)));
    } catch {
      setItems([]);
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agent?.id]);

  const dismiss = async (rec: AgentRecommendation) => {
    if (!agent) return;
    // Optimistic — drop it immediately, then persist.
    dismissedRef.current.add(rec.id);
    setItems((prev) => prev?.filter((r) => r.id !== rec.id) ?? null);
    try {
      await api.markRecommendationSeen(agent.id, rec.id);
    } catch {
      dismissedRef.current.delete(rec.id);
      load();
    }
  };

  const runNow = async () => {
    if (!agent || running) return;
    setRunning(true);
    try {
      const summary = await api.runA2A(agent.id);
      pushToast(
        `Your agent scanned ${summary.scanned} ${
          summary.scanned === 1 ? "profile" : "profiles"
        } and found ${summary.recommendations.length} to suggest.`,
        "success"
      );
      await load();
    } catch {
      /* toast already surfaced by the request helper */
    } finally {
      setRunning(false);
    }
  };

  return (
    <section className="panel p-4 mb-5">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span style={{ color: "var(--accent-primary)" }}>
            <Sparkles size={15} />
          </span>
          <div>
            <div className="label-mono">Your agent suggests</div>
            <h2
              className="text-base mt-0.5"
              style={{ fontFamily: "var(--font-display)" }}
            >
              People you should meet
            </h2>
          </div>
        </div>
        <button
          onClick={runNow}
          disabled={running}
          className="inline-flex items-center gap-1.5 text-[11px] px-2 py-1 rounded transition disabled:opacity-50"
          style={{
            color: "var(--text-secondary)",
            fontFamily: "var(--font-data)",
            border: "1px solid var(--border)",
          }}
          title="Run a network scan now"
        >
          <RefreshCw
            size={12}
            className={running ? "animate-spin" : undefined}
          />
          {running ? "Scanning…" : "Scan now"}
        </button>
      </div>

      {items === null && (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <div key={i} className="skeleton h-12" />
          ))}
        </div>
      )}

      {items?.length === 0 && (
        <p
          className="text-[13px] py-2"
          style={{ color: "var(--text-secondary)" }}
        >
          No suggestions yet — your agent will surface people worth meeting after
          its next network scan. Hit “Scan now” to try it immediately.
        </p>
      )}

      {items && items.length > 0 && (
        <ul className="space-y-2">
          <AnimatePresence initial={false}>
            {items.map((rec) => (
              <motion.li
                key={rec.id}
                layout
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.22, ease: "easeOut" }}
                className="flex items-start gap-3 p-2.5 rounded"
                style={{ background: "var(--bg-elevated)" }}
              >
                <span
                  className="mt-0.5 shrink-0 inline-flex w-7 h-7 items-center justify-center rounded-full text-xs font-medium"
                  style={{
                    background: "var(--accent-blue-muted)",
                    color: "var(--text-on-accent)",
                  }}
                >
                  {(rec.recommended_name || "?").trim().charAt(0).toUpperCase()}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span
                      className="text-[13px] font-medium truncate"
                      style={{
                        color: "var(--text-primary)",
                        fontFamily: "var(--font-body)",
                      }}
                    >
                      {rec.recommended_name || "Someone new"}
                    </span>
                    <span
                      className="text-[10px] px-1.5 py-0.5 rounded uppercase tracking-wider shrink-0"
                      style={{
                        background: "var(--bg-base)",
                        color: "var(--accent-primary)",
                        fontFamily: "var(--font-data)",
                      }}
                    >
                      {ACTION_LABEL[rec.suggested_action] || "Connect"}
                    </span>
                    {rec.compatibility_score > 0 && (
                      <span
                        className="text-[10px] shrink-0"
                        style={{
                          color: "var(--text-muted)",
                          fontFamily: "var(--font-data)",
                        }}
                      >
                        {Math.round(rec.compatibility_score)}% fit
                      </span>
                    )}
                  </div>
                  <p
                    className="text-[12px] mt-0.5 leading-snug"
                    style={{
                      color: "var(--text-secondary)",
                      fontFamily: "var(--font-body)",
                    }}
                  >
                    {rec.reason}
                  </p>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  {rec.recommended_agent_id && (
                    <a
                      href={`/network`}
                      title="View in network"
                      className="inline-flex items-center justify-center w-6 h-6 rounded transition"
                      style={{ color: "var(--accent-primary)" }}
                    >
                      <UserPlus size={14} />
                    </a>
                  )}
                  <button
                    onClick={() => dismiss(rec)}
                    title="Dismiss"
                    className="inline-flex items-center justify-center w-6 h-6 rounded transition"
                    style={{ color: "var(--text-muted)" }}
                  >
                    <X size={14} />
                  </button>
                </div>
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      )}
    </section>
  );
}
