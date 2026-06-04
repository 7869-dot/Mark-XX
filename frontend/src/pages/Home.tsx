import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { IconLayoutSidebarRightExpand, IconLayoutSidebarRightCollapse, IconLogout } from "@tabler/icons-react";
import {
  api,
  webStreamUrl,
  type AgentDraft,
  type EmailReport,
  type JarvisSession,
  type SubAgentStatus,
  type WebFind,
} from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { pushToast } from "@/lib/toast";
import { buildGreeting } from "@/lib/briefing";
import { OnboardingCard } from "@/components/jarvis/OnboardingCard";
import { JarvisChat, type ChatPrefill } from "@/components/home/JarvisChat";
import { AgentPanel, type PanelTab } from "@/components/home/AgentPanel";
import { AgentStatusDots } from "@/components/home/AgentStatusDots";

type Phase = "loading" | "onboarding" | "ready" | "error";

export function HomePage() {
  const { user, loading: authLoading, signOut } = useAuth();
  const [phase, setPhase] = useState<Phase>("loading");
  const [session, setSession] = useState<Extract<JarvisSession, { onboarding: false }> | null>(null);
  const [onboarding, setOnboarding] = useState<Extract<JarvisSession, { onboarding: true }> | null>(null);

  const [drafts, setDrafts] = useState<AgentDraft[]>([]);
  const [draftsLoading, setDraftsLoading] = useState(true);
  const [findings, setFindings] = useState<WebFind[]>([]);
  const [findingsLoading, setFindingsLoading] = useState(true);
  const [status, setStatus] = useState<SubAgentStatus[]>([]);
  const [gmailConnected, setGmailConnected] = useState<boolean | null>(null);
  const [emailReport, setEmailReport] = useState<EmailReport | null>(null);
  const esRef = useRef<EventSource | null>(null);

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

  // Web findings stream in over SSE so cards animate in as they arrive. Falls
  // back to a one-shot fetch if the EventSource errors before any result.
  const streamFindings = useCallback(() => {
    esRef.current?.close();
    setFindings([]);
    setFindingsLoading(true);
    let received = false;
    let es: EventSource;
    try {
      es = new EventSource(webStreamUrl());
    } catch {
      setFindingsLoading(false);
      return;
    }
    esRef.current = es;
    es.onmessage = (ev) => {
      let d: WebFind & { done?: boolean };
      try {
        d = JSON.parse(ev.data);
      } catch {
        return;
      }
      if (d.done) {
        setFindingsLoading(false);
        es.close();
        return;
      }
      received = true;
      setFindingsLoading(false);
      setFindings((prev) => (prev.some((f) => f.id === d.id) ? prev : [...prev, d]));
    };
    es.onerror = () => {
      es.close();
      setFindingsLoading(false);
      if (!received) {
        api.webFindings().then((r) => setFindings(r.items)).catch(() => {});
      }
    };
  }, []);

  const loadSidePanels = useCallback(() => {
    setDraftsLoading(true);
    api.agentDrafts().then((r) => setDrafts(r.items)).catch(() => setDrafts([])).finally(() => setDraftsLoading(false));
    api.agentsStatus().then((r) => setStatus(r.agents)).catch(() => setStatus([]));
    api.integrationsStatus().then((r) => setGmailConnected(r.gmail)).catch(() => setGmailConnected(null));
    api.emailSummary().then((r) => setEmailReport(r)).catch(() => setEmailReport(null));
    streamFindings();
  }, [streamFindings]);

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

  // Fire the session start exactly once, and only AFTER auth bootstrap settles
  // (useAuth.getMe triggers any needed token refresh). Gating here means
  // /jarvis/session/start always sends a fresh token — no startup 401 race.
  // The ref also defends against React StrictMode's double-mount (which would
  // otherwise call session/start twice and race the team creation).
  const didInit = useRef(false);
  useEffect(() => {
    if (authLoading || didInit.current) return;
    didInit.current = true;
    loadSession();
    return clearTimers;
  }, [authLoading, loadSession]);

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

  const onConnectGmail = useCallback(async () => {
    try {
      const { authorization_url } = await api.gmailConnect();
      window.location.href = authorization_url; // backend redirects to /app?gmail=connected
    } catch {
      pushToast("Couldn't start Gmail connect — try again.");
    }
  }, []);

  // Surface the Gmail OAuth round-trip result and close the SSE stream on unmount.
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const g = p.get("gmail");
    if (g) {
      pushToast(g === "connected" ? "Gmail connected." : "Gmail connection failed.",
        g === "connected" ? "success" : "error");
      p.delete("gmail");
      const qs = p.toString();
      window.history.replaceState({}, "", window.location.pathname + (qs ? `?${qs}` : ""));
    }
    return () => esRef.current?.close();
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
            gmailConnected={gmailConnected}
            emailReport={emailReport}
            onConnectGmail={onConnectGmail}
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
