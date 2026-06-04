import { motion, AnimatePresence } from "framer-motion";
import { IconChecklist, IconMail, IconWorld, IconBrandGoogle } from "@tabler/icons-react";
import type { AgentDraft, EmailReport, WebFind } from "@/lib/api";
import { TaskChecklist } from "./TaskChecklist";
import { EmailDraftCard } from "./EmailDraftCard";
import { WebIntelCard } from "./WebIntelCard";

export type PanelTab = "tasks" | "emails" | "web";

function ConnectGmailCTA({ onConnect }: { onConnect: () => void }) {
  return (
    <div className="axo-cta">
      <div className="axo-cta-title">Connect Gmail so Jarvis can triage your inbox.</div>
      <div className="axo-cta-sub">
        Read-only — drafts always wait for your approval, nothing is ever sent automatically.
      </div>
      <button className="axo-btn axo-btn-primary" onClick={onConnect} style={{ margin: "0 auto" }}>
        <IconBrandGoogle size={13} /> Connect Gmail
      </button>
    </div>
  );
}

function EmailSummaryRow({ subject, from, kind }: { subject: string; from: string; kind: "urgent" | "important" }) {
  const urgent = kind === "urgent";
  return (
    <div className="axo-email-item">
      <div className="axo-email-top">
        <span className="axo-email-sender">{from || "unknown sender"}</span>
        <span
          className="axo-email-badge"
          style={
            urgent
              ? { background: "#3f1515", color: "#f87171" }
              : { background: "#2a1f0a", color: "#fbbf24" }
          }
        >
          {kind}
        </span>
      </div>
      <div className="axo-email-subject" style={{ marginBottom: 0 }}>
        {subject || "(no subject)"}
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
  const urgent = emailReport?.urgent ?? [];
  const important = emailReport?.important ?? [];
  const hasSummary = urgent.length > 0 || important.length > 0;
  const emailCount = drafts.length + urgent.length + important.length;

  return (
    <>
      <div className="axo-tabs">
        <button className={`axo-tab ${tab === "tasks" ? "active" : ""}`} onClick={() => onTab("tasks")}>
          <IconChecklist size={13} /> Tasks
          {tasks.length > 0 && <span className="axo-count">{tasks.length}</span>}
        </button>
        <button className={`axo-tab ${tab === "emails" ? "active" : ""}`} onClick={() => onTab("emails")}>
          <IconMail size={13} /> Emails
          {emailCount > 0 && (
            <span className={`axo-count ${urgent.length > 0 ? "red" : ""}`}>{emailCount}</span>
          )}
        </button>
        <button className={`axo-tab ${tab === "web" ? "active" : ""}`} onClick={() => onTab("web")}>
          <IconWorld size={13} /> Web
          {findings.length > 0 && <span className="axo-count">{findings.length}</span>}
        </button>
      </div>

      <div className="axo-panel-content">
        {tab === "tasks" && <TaskChecklist tasks={tasks} />}

        {tab === "emails" && (
          <>
            {gmailConnected === false && <ConnectGmailCTA onConnect={onConnectGmail} />}

            {urgent.map((e, i) => (
              <EmailSummaryRow key={`u${i}`} subject={e.subject} from={e.from} kind="urgent" />
            ))}
            {important.map((e, i) => (
              <EmailSummaryRow key={`i${i}`} subject={e.subject} from={e.from} kind="important" />
            ))}

            {draftsLoading ? (
              <div className="axo-empty">Loading drafts…</div>
            ) : (
              drafts.map((d) => (
                <EmailDraftCard key={d.id} draft={d} onAskJarvis={onAskJarvis} onResolve={onResolveDraft} />
              ))
            )}

            {!draftsLoading && drafts.length === 0 && !hasSummary && gmailConnected !== false && (
              <div className="axo-empty">
                No email drafts waiting. Jarvis drafts replies as urgent mail arrives.
              </div>
            )}
          </>
        )}

        {tab === "web" &&
          (findings.length === 0 && findingsLoading ? (
            <div className="axo-empty">Scouting the web…</div>
          ) : findings.length === 0 ? (
            <div className="axo-empty">No web findings yet. The scout surfaces opportunities tied to your goals.</div>
          ) : (
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
          ))}
      </div>
    </>
  );
}
