import { useCallback, useEffect, useState } from "react";
import { api, type JarvisSession } from "@/lib/api";
import { CommandChatbox } from "@/components/jarvis/CommandChatbox";
import { OnboardingCard } from "@/components/jarvis/OnboardingCard";
import { SessionBriefing } from "@/components/jarvis/SessionBriefing";
import { AgentStatusPanel } from "@/components/jarvis/AgentStatusPanel";

/** Jarvis command center. On first interaction Jarvis onboards the user (5
 * questions); afterwards it runs the three sub-agents, presents a briefing +
 * action items, and the conversational layer + agent status panel. */
export function JarvisPage() {
  const [session, setSession] = useState<JarvisSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [prefill, setPrefill] = useState<string | undefined>();

  const loadSession = useCallback(async () => {
    setLoading(true);
    try {
      setSession(await api.jarvisSessionStart());
    } catch {
      setSession(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadSession(); }, [loadSession]);

  if (loading) return <JarvisSkeleton />;

  if (session?.onboarding) {
    return (
      <OnboardingCard
        greeting={session.greeting}
        questions={session.questions}
        onComplete={loadSession}
      />
    );
  }

  return (
    <div className="h-full flex flex-col lg:flex-row gap-4 p-4 max-w-6xl mx-auto w-full">
      {/* Conversation */}
      <div
        className="flex-1 min-h-0 rounded-2xl overflow-hidden"
        style={{ border: "1px solid var(--border)" }}
      >
        <CommandChatbox prefill={prefill} />
      </div>

      {/* Right rail: briefing + agent status */}
      <aside className="lg:w-80 shrink-0 space-y-4 overflow-y-auto">
        {session && !session.onboarding && (
          <SessionBriefing session={session} onPrompt={setPrefill} />
        )}
        <AgentStatusPanel onRan={loadSession} />
      </aside>
    </div>
  );
}

function JarvisSkeleton() {
  return (
    <div className="h-full flex flex-col lg:flex-row gap-4 p-4 max-w-6xl mx-auto w-full">
      <div className="flex-1 rounded-2xl p-5 space-y-3" style={{ border: "1px solid var(--border)" }}>
        <div className="skeleton h-6 w-40" />
        <div className="skeleton h-4 w-full" />
        <div className="skeleton h-4 w-3/4" />
        <div className="skeleton h-4 w-2/3" />
      </div>
      <aside className="lg:w-80 shrink-0 space-y-3">
        <div className="skeleton h-24 w-full rounded-xl" />
        <div className="skeleton h-32 w-full rounded-xl" />
      </aside>
    </div>
  );
}
