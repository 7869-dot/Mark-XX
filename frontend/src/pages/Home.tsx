import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { IconLayoutSidebarRightExpand, IconLayoutSidebarRightCollapse, IconLogout } from "@tabler/icons-react";
import {
  api,
  type AgentDraft,
  type JarvisSession,
  type SubAgentStatus,
  type WebFind,
} from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { buildGreeting } from "@/lib/briefing";
import { OnboardingCard } from "@/components/jarvis/OnboardingCard";
import { JarvisChat, type ChatPrefill } from "@/components/home/JarvisChat";
import { AgentPanel, type PanelTab } from "@/components/home/AgentPanel";
import { AgentStatusDots } from "@/components/home/AgentStatusDots";

type Phase = "loading" | "onboarding" | "ready" | "error";

export function HomePage() {
  const { user, signOut } = useAuth();
  const [phase, setPhase] = useState<Phase>("loading");
  const [session, setSession] = useState<Extract<JarvisSession, { onboarding: false }> | null>(null);
  const [onboarding, setOnboarding] = useState<Extract<JarvisSession, { onboarding: true }> | null>(null);

  const [drafts, setDrafts] = useState<AgentDraft[]>([]);
  const [draftsLoading, setDraftsLoading] = useState(true);
  const [findings, setFindings] = useState<WebFind[]>([]);
  const [findingsLoading, setFindingsLoading] = useState(true);
  const [status, setStatus] = useState<SubAgentStatus[]>([]);

  const [tab, setTab] = useState<PanelTab>("tasks");
  const [prefill, setPrefill] = useState<ChatPrefill | undefined>();
  const [mobilePanelOpen, setMobilePanelOpen] = useState(false);

  // Loading UX: "Jarvis is thinking…" after 8s, a timeout note after 15s.
  const [slow, setSlow] = useState(false);
  const [timedOut, setTimedOut] = useState(false);
  const timers = useRef<number[]>([]);

  const clearTimers = () => {
    timers.current.forEach((t) => clearTimeout(t));
    timers.current = [];
  };

  const loadSidePanels = useCallback(async () => {
    setDraftsLoading(true);
    setFindingsLoading(true);
    api
      .agentDrafts()
      .then((r) => setDrafts(r.items))
      .catch(() => setDrafts([]))
      .finally(() => setDraftsLoading(false));
    api
      .webFindings()
      .then((r) => setFindings(r.items))
      .catch(() => setFindings([]))
      .finally(() => setFindingsLoading(false));
    api
      .agentsStatus()
      .then((r) => setStatus(r.agents))
      .catch(() => setStatus([]));
  }, []);

  const loadSession = useCallback(async () => {
    setPhase("loading");
    setSlow(false);
    setTimedOut(false);
    clearTimers();
    timers.current.push(window.setTimeout(() => setSlow(true), 8000));
    timers.current.push(window.setTimeout(() => setTimedOut(true), 15000));
    try {
      const s = await api.jarvisSessionStart();
      if (s.onboarding) {
        setOnboarding(s);
        setPhase("onboarding");
      } else {
        setSession(s);
        setStatus(s.agent_status || []);
        setPhase("ready");
        loadSidePanels();
      }
    } catch {
      setPhase("error");
    } finally {
      clearTimers();
    }
  }, [loadSidePanels]);

  // Fire the session start exactly once. /jarvis/session/start runs the sub-
  // agents (expensive) and seeds the team on first login — React StrictMode's
  // double-mount would otherwise call it twice and race the team creation.
  const didInit = useRef(false);
  useEffect(() => {
    if (didInit.current) return;
    didInit.current = true;
    loadSession();
    return clearTimers;
  }, [loadSession]);

  const greeting = useMemo(() => {
    if (!session) return "";
    return buildGreeting(session, user?.name || "", drafts.length);
  }, [session, user, drafts.length]);

  // ── Cross-panel actions ──────────────────────────────────────────────────
  const onAskJarvis = useCallback((d: AgentDraft) => {
    setPrefill({
      text: `About the email from ${d.recipient_hint || "this contact"} re: ${d.subject_line || "(no subject)"}: `,
      nonce: Date.now(),
      draftId: d.id,
    });
    setMobilePanelOpen(false); // surface the chat on mobile
  }, []);

  const onResolveDraft = useCallback((id: string) => {
    setDrafts((ds) => ds.filter((d) => d.id !== id));
  }, []);

  const onDraftRevised = useCallback((id: string, content: string) => {
    setDrafts((ds) => ds.map((d) => (d.id === id ? { ...d, draft_content: content } : d)));
    setTab("emails");
  }, []);

  // ── Render states ────────────────────────────────────────────────────────
  if (phase === "onboarding" && onboarding) {
    return (
      <Shell status={status} signOut={signOut}>
        <div className="flex-1 min-h-0 overflow-y-auto">
          <OnboardingCard
            greeting={onboarding.greeting}
            questions={onboarding.questions}
            onComplete={loadSession}
          />
        </div>
      </Shell>
    );
  }

  if (phase === "loading") {
    return (
      <Shell status={status} signOut={signOut}>
        <div className="flex-1 flex flex-col items-center justify-center gap-3 px-6 text-center">
          <span
            className="text-sm animate-pulse"
            style={{ color: "var(--text-secondary)", fontFamily: "var(--font-data)" }}
          >
            {slow ? "Jarvis is thinking…" : "Starting your session…"}
          </span>
          {timedOut && (
            <div className="flex flex-col items-center gap-2">
              <span className="text-xs" style={{ color: "var(--text-secondary)" }}>
                This is taking longer than expected.
              </span>
              <button onClick={loadSession} className="btn-primary text-xs px-3 py-1.5">
                Retry
              </button>
            </div>
          )}
        </div>
      </Shell>
    );
  }

  if (phase === "error" || !session) {
    return (
      <Shell status={status} signOut={signOut}>
        <div className="flex-1 flex flex-col items-center justify-center gap-3 px-6 text-center">
          <span className="text-sm" style={{ color: "var(--text-secondary)" }}>
            Jarvis couldn't start your session.
          </span>
          <button onClick={loadSession} className="btn-primary text-xs px-3 py-1.5">
            Try again
          </button>
        </div>
      </Shell>
    );
  }

  const tasks = session.action_items || [];

  return (
    <Shell status={status} signOut={signOut}>
      {/* Desktop: split view. Mobile: chat on top, panel as a toggle below. */}
      <div className="flex-1 min-h-0 flex flex-col lg:flex-row">
        {/* Left — Jarvis chat (primary) */}
        <section
          className="min-h-0 flex-1 lg:flex-[1.4] flex flex-col"
          style={{ borderRight: "1px solid var(--border)" }}
        >
          <JarvisChat
            greeting={greeting}
            prefill={prefill}
            onSwitchTab={(t) => {
              setTab(t);
              setMobilePanelOpen(true);
            }}
            onDraftRevised={onDraftRevised}
          />
        </section>

        {/* Mobile accordion toggle */}
        <button
          onClick={() => setMobilePanelOpen((o) => !o)}
          className="lg:hidden flex items-center justify-center gap-2 py-2 text-xs shrink-0"
          style={{
            borderTop: "1px solid var(--border)",
            color: "var(--text-secondary)",
            fontFamily: "var(--font-data)",
          }}
        >
          {mobilePanelOpen ? (
            <IconLayoutSidebarRightCollapse size={15} />
          ) : (
            <IconLayoutSidebarRightExpand size={15} />
          )}
          Agent work ({tasks.length + drafts.length + findings.length})
        </button>

        {/* Right — agent work panel (secondary) */}
        <aside
          className={`${mobilePanelOpen ? "flex" : "hidden"} lg:flex min-h-0 flex-1 lg:flex-none lg:w-[380px] xl:w-[420px] flex-col`}
        >
          <AgentPanel
            tab={tab}
            onTab={setTab}
            tasks={tasks}
            drafts={drafts}
            draftsLoading={draftsLoading}
            findings={findings}
            findingsLoading={findingsLoading}
            onAskJarvis={onAskJarvis}
            onResolveDraft={onResolveDraft}
          />
        </aside>
      </div>
    </Shell>
  );
}

/** App frame: header (JARVIS + status + sign out) and the content slot. */
function Shell({
  status,
  signOut,
  children,
}: {
  status: SubAgentStatus[];
  signOut: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="h-screen flex flex-col" style={{ background: "var(--bg-base)" }}>
      <header
        className="flex items-center justify-between px-4 py-3 shrink-0"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <span
          className="text-sm tracking-[0.2em]"
          style={{ fontFamily: "var(--font-data)", color: "var(--text-primary)" }}
        >
          JARVIS
        </span>
        <div className="flex items-center gap-4">
          <AgentStatusDots agents={status} />
          <button
            onClick={signOut}
            title="Sign out"
            className="inline-flex items-center"
            style={{ color: "var(--text-secondary)" }}
          >
            <IconLogout size={16} />
          </button>
        </div>
      </header>
      {children}
    </div>
  );
}
