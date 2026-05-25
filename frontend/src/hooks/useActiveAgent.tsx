import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  api,
  getActiveAgentId,
  setActiveAgentId as setStoredActiveAgent,
  type AgentSummary,
} from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";

/**
 * Active-agent context for the multi-agent product.
 *
 * The agent switcher writes the selected id to localStorage; the API client
 * (lib/api.ts) reads it from there and stamps X-Agent-Id on every request.
 * This hook exposes the list of the user's agents + helpers, and keeps the
 * stored id sane (clears it if the agent is deleted).
 */
type ActiveAgentContextValue = {
  agents: AgentSummary[];
  loading: boolean;
  activeAgentId: string | null;
  activeAgent: AgentSummary | null;
  primaryAgent: AgentSummary | null;
  setActiveAgent: (id: string | null) => void;
  refresh: () => Promise<void>;
};

const ActiveAgentContext = createContext<ActiveAgentContextValue | null>(null);

export function ActiveAgentProvider({ children }: { children: ReactNode }) {
  const { agent: primary } = useAuth();
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeAgentId, setActiveAgentIdState] = useState<string | null>(
    getActiveAgentId()
  );

  const refresh = useCallback(async () => {
    try {
      const r = await api.myAgents();
      setAgents(r.items);
      // If the stored active id was deleted, fall back to whatever's primary.
      const stored = getActiveAgentId();
      if (stored && !r.items.find((a) => a.id === stored)) {
        setStoredActiveAgent(null);
        setActiveAgentIdState(null);
      }
    } catch {
      setAgents([]);
    } finally {
      setLoading(false);
    }
  }, []);

  // Re-fetch on auth load (when primary is known) so we have the full list.
  useEffect(() => {
    if (!primary) {
      setAgents([]);
      setLoading(false);
      return;
    }
    refresh();
  }, [primary, refresh]);

  const setActiveAgent = useCallback((id: string | null) => {
    setStoredActiveAgent(id);
    setActiveAgentIdState(id);
  }, []);

  const value = useMemo<ActiveAgentContextValue>(() => {
    const primaryAgent = agents.find((a) => a.is_primary) ?? null;
    // null active id means "use primary" — both for the API header (no X-Agent-Id
    // sent) and for the UI display.
    const active =
      (activeAgentId && agents.find((a) => a.id === activeAgentId)) ||
      primaryAgent;
    return {
      agents,
      loading,
      activeAgentId,
      activeAgent: active ?? null,
      primaryAgent,
      setActiveAgent,
      refresh,
    };
  }, [agents, loading, activeAgentId, setActiveAgent, refresh]);

  return (
    <ActiveAgentContext.Provider value={value}>
      {children}
    </ActiveAgentContext.Provider>
  );
}

export function useActiveAgent() {
  const ctx = useContext(ActiveAgentContext);
  if (!ctx) {
    throw new Error("useActiveAgent must be used inside ActiveAgentProvider");
  }
  return ctx;
}
