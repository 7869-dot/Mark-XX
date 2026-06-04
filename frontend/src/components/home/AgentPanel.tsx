import { motion, AnimatePresence } from "framer-motion";
import { IconBrandGoogle, IconAlertTriangle, IconFlag } from "@tabler/icons-react";
import type { AgentDraft, EmailReport, WebFind } from "@/lib/api";
import { TaskChecklist } from "./TaskChecklist";
import { EmailDraftCard } from "./EmailDraftCard";
import { WebIntelCard } from "./WebIntelCard";

export type PanelTab = "tasks" | "emails" | "web";

const TABS: { id: PanelTab; label: string }[] = [
  { id: "tasks", label: "Tasks" },
  { id: "emails", label: "Emails" },
  { id: "web", label: "Web Intel" },
];

function EmptyState({ text }: { text: string }) {
  return (
    <p className="text-sm px-1 py-8 text-center" style={{ color: "var(--text-secondary)" }}>
      {text}
    </p>
  );
}

function Loading() {
  return (
    <div className="space-y-2.5">
      <div className="skeleton h-20 w-full rounded-xl" />
      <div className="skeleton h-20 w-full rounded-xl" />
    </div>
  );
}

function ConnectGmailCTA({ onConnect }: { onConnect: () => void }) {
  return (
    <div
      className="rounded-xl p-4 text-center"
      style={{ background: "var(--bg-surface)", border: "1px dashed var(--border-strong)" }}
    >
      <p className="text-sm" style={{ color: "var(--text-primary)" }}>
        Connect Gmail so Jarvis can triage your inbox.
      </p>
      <p className="text-xs mt-1 mb-3" style={{ color: "var(--text-secondary)" }}>
        Read-only — drafts always wait for your approval, nothing is ever sent automatically.
      </p>
      <button
        onClick={onConnect}
        className="btn-primary text-xs py-2 px-3 inline-flex items-center gap-2"
      >
        <IconBrandGoogle size={14} /> Connect Gmail
      </button>
    </div>
  );
}

function EmailSummaryRow({ subject, from, kind }: { subject: string; from: string; kind: "urgent" | "important" }) {
  const urgent = kind === "urgent";
  return (
    <div
      className="rounded-lg px-3 py-2 flex items-start gap-2.5"
      style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
    >
      <span
        className="mt-0.5 shrink-0 inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded"
        style={{
          background: urgent ? "var(--accent-red-soft)" : "var(--accent-gold-soft)",
          color: urgent ? "var(--accent-red)" : "var(--accent-gold)",
          fontFamily: "var(--font-data)",
        }}
      >
        {urgent ? <IconAlertTriangle size={10} /> : <IconFlag size={10} />}
        {urgent ? "urgent" : "important"}
      </span>
      <div className="min-w-0">
        <div className="text-[13px] truncate" style={{ color: "var(--text-primary)" }}>
          {subject || "(no subject)"}
        </div>
        <div className="text-[11px] truncate" style={{ color: "var(--text-secondary)" }}>
          {from || "unknown sender"}
        </div>
      </div>
    </div>
  );
}

export function AgentPanel({
  tab,
  onTab,
  tasks,
  drafts,
  draftsLoading,
  findings,
  findingsLoading,
  gmailConnected,
  emailReport,
  onConnectGmail,
  onAskJarvis,
  onResolveDraft,
}: {
  tab: PanelTab;
  onTab: (t: PanelTab) => void;
  tasks: string[];
  drafts: AgentDraft[];
  draftsLoading: boolean;
  findings: WebFind[];
  findingsLoading: boolean;
  gmailConnected: boolean | null;
  emailReport: EmailReport | null;
  onConnectGmail: () => void;
  onAskJarvis: (d: AgentDraft) => void;
  onResolveDraft: (id: string) => void;
}) {
  const counts: Record<PanelTab, number> = {
    tasks: tasks.length,
    emails: drafts.length,
    web: findings.length,
  };

  const urgent = emailReport?.urgent ?? [];
  const important = emailReport?.important ?? [];
  const hasSummary = urgent.length > 0 || important.length > 0;

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Tab bar */}
      <div
        className="flex items-center gap-1 px-2 py-2 shrink-0"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        {TABS.map((t) => {
          const active = tab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => onTab(t.id)}
              className="px-3 py-1.5 rounded-lg text-xs inline-flex items-center gap-1.5 transition"
              style={{
                background: active ? "var(--bg-elevated)" : "transparent",
                color: active ? "var(--text-primary)" : "var(--text-secondary)",
                fontFamily: "var(--font-data)",
                border: `1px solid ${active ? "var(--border)" : "transparent"}`,
              }}
            >
              {t.label}
              {counts[t.id] > 0 && (
                <span
                  className="text-[10px] px-1.5 rounded-full"
                  style={{
                    background: active ? "var(--accent-primary)" : "var(--bg-elevated)",
                    color: active ? "#fff" : "var(--text-secondary)",
                  }}
                >
                  {counts[t.id]}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      <div className="flex-1 min-h-0 overflow-y-auto p-3">
        {tab === "tasks" && <TaskChecklist tasks={tasks} />}

        {tab === "emails" && (
          <div className="space-y-3">
            {gmailConnected === false && <ConnectGmailCTA onConnect={onConnectGmail} />}

            {hasSummary && (
              <div className="space-y-2">
                {urgent.map((e, i) => (
                  <EmailSummaryRow key={`u${i}`} subject={e.subject} from={e.from} kind="urgent" />
                ))}
                {important.map((e, i) => (
                  <EmailSummaryRow key={`i${i}`} subject={e.subject} from={e.from} kind="important" />
                ))}
              </div>
            )}

            {draftsLoading ? (
              <Loading />
            ) : drafts.length === 0 ? (
              !hasSummary && gmailConnected !== false ? (
                <EmptyState text="No email drafts waiting. Jarvis will draft replies as urgent mail arrives." />
              ) : null
            ) : (
              <div className="space-y-2.5">
                {drafts.map((d) => (
                  <EmailDraftCard
                    key={d.id}
                    draft={d}
                    onAskJarvis={onAskJarvis}
                    onResolve={onResolveDraft}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {tab === "web" &&
          (findings.length === 0 && findingsLoading ? (
            <Loading />
          ) : findings.length === 0 ? (
            <EmptyState text="No web findings yet. The scout surfaces opportunities tied to your goals." />
          ) : (
            <div className="space-y-2.5">
              <AnimatePresence initial={false}>
                {findings.map((f) => (
                  <motion.div
                    key={f.id}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.28, ease: "easeOut" }}
                  >
                    <WebIntelCard find={f} />
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          ))}
      </div>
    </div>
  );
}
