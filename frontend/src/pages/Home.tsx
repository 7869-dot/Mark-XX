import { useCallback, useEffect, useRef, useState } from "react";
import { IconLogout } from "@tabler/icons-react";
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
import { OnboardingCard } from "@/components/jarvis/OnboardingCard";
import { JarvisChat } from "@/components/home/JarvisChat";
import { AgentPanel, type PanelTab } from "@/components/home/AgentPanel";
import { AgentStatusDots } from "@/components/home/AgentStatusDots";
import { BriefingCard } from "@/components/home/BriefingCard";
import { AgentReportRow } from "@/components/home/AgentReportRow";
import "@/styles/home.css";

type Phase = "loading" | "onboarding" | "ready" | "error";
type Ready = Extract<JarvisSession, { onboarding: false }>;

function salutation(name?: string): string {
  const h = new Date().getHours();
  const part = h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
  const first = (name || "").trim().split(" ")[0];
  return `${part}${first ? `, ${first}` : ""}.`;
}

export function HomePage() {
  const { user, loading: authLoading, signOut } = useAuth();
  const [phase, setPhase] = useState<Phase>("loading");
  const [session, setSession] = useState<Ready | null>(null);
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
  const [prefill, setPrefill] = useState<{ text: string; nonce: number; draftId?: string } | undefined>();

  const [slow, setSlow] = useState(false);
  const [timedOut, setTimedOut] = useState(false);
  const timers = useRef<number[]>([]);
  const clearTimers = () => {
    timers.current.forEach((t) => clearTimeout(t));
    timers.current = [];
  };

  // Web findings stream in over SSE so cards animate in as they arrive.
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
      if (!received) api.webFindings().then((r) => setFindings(r.items)).catch(() => {});
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

  // Fire session start once, only after auth bootstrap settles (fresh token).
  const didInit = useRef(false);
  useEffect(() => {
    if (authLoading || didInit.current) return;
    didInit.current = true;
    loadSession();
    return clearTimers;
  }, [authLoading, loadSession]);

  // ── Cross-panel actions ──────────────────────────────────────────────────
  const onAskJarvis = useCallback((d: AgentDraft) => {
    setPrefill({
      text: `About the email from ${d.recipient_hint || "this contact"} re: ${d.subject_line || "(no subject)"}: `,
      nonce: Date.now(),
      draftId: d.id,
    });
    setTab("emails");
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

  // Surface the Gmail OAuth round-trip and close the SSE stream on unmount.
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

  // ── Render ─────────────────────────────────────────────────────────────────
  const nav = (
    <nav className="axo-nav">
      <span className="axo-logo">Axolot</span>
      <div className="axo-nav-spacer" />
      <AgentStatusDots agents={status} />
      <button className="axo-nav-icon" onClick={signOut} title="Sign out" aria-label="Sign out">
        <IconLogout size={16} />
      </button>
    </nav>
  );

  let body: React.ReactNode;
  if (phase === "onboarding" && onboarding) {
    body = (
      <div className="axo-center" style={{ overflowY: "auto" }}>
        <OnboardingCard greeting={onboarding.greeting} questions={onboarding.questions} onComplete={loadSession} />
      </div>
    );
  } else if (phase === "loading") {
    body = (
      <div className="axo-center">
        <span className="axo-thinking">{slow ? "Jarvis is thinking…" : "Starting your session…"}</span>
        {timedOut && (
          <>
            <span className="axo-subtle">This is taking longer than expected.</span>
            <button className="axo-btn axo-btn-primary" onClick={loadSession}>Retry</button>
          </>
        )}
      </div>
    );
  } else if (phase === "error" || !session) {
    body = (
      <div className="axo-center">
        <span className="axo-subtle">Jarvis couldn't start your session.</span>
        <button className="axo-btn axo-btn-primary" onClick={loadSession}>Try again</button>
      </div>
    );
  } else {
    const webCount = Math.max(findings.length, session.reports?.web?.top_finds?.length ?? 0);
    const urgentCount = emailReport?.counts?.urgent ?? 0;
    const briefingSlot = (
      <>
        <BriefingCard
          greeting={salutation(user?.name)}
          items={session.action_items || []}
          webCount={webCount}
          urgentCount={urgentCount}
          focusPrompt={session.focus_prompt}
        />
        <AgentReportRow emailReport={emailReport} webCount={webCount} />
      </>
    );
    body = (
      <div className="axo-main">
        <JarvisChat
          briefingSlot={briefingSlot}
          prefill={prefill}
          onSwitchTab={setTab}
          onDraftRevised={onDraftRevised}
        />
        <div className="axo-right">
          <AgentPanel
            tab={tab}
            onTab={setTab}
            tasks={session.action_items || []}
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
        </div>
      </div>
    );
  }

  return (
    <div className="axo-shell">
      {nav}
      {body}
    </div>
  );
}
