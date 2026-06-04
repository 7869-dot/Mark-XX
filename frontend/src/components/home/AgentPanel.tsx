import type { AgentDraft, WebFind } from "@/lib/api";
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

export function AgentPanel({
  tab,
  onTab,
  tasks,
  drafts,
  draftsLoading,
  findings,
  findingsLoading,
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
  onAskJarvis: (d: AgentDraft) => void;
  onResolveDraft: (id: string) => void;
}) {
  const counts: Record<PanelTab, number> = {
    tasks: tasks.length,
    emails: drafts.length,
    web: findings.length,
  };

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

        {tab === "emails" &&
          (draftsLoading ? (
            <Loading />
          ) : drafts.length === 0 ? (
            <EmptyState text="No email drafts waiting. Jarvis will draft replies as urgent mail arrives." />
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
          ))}

        {tab === "web" &&
          (findingsLoading ? (
            <Loading />
          ) : findings.length === 0 ? (
            <EmptyState text="No web findings yet. The scout surfaces opportunities tied to your goals." />
          ) : (
            <div className="space-y-2.5">
              {findings.map((f) => (
                <WebIntelCard key={f.id} find={f} />
              ))}
            </div>
          ))}
      </div>
    </div>
  );
}
