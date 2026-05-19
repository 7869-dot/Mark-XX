import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api, clearTokens } from "@/lib/api";
import type { Agent } from "@/types";

type AuthContextValue = {
  agent: Agent | null;
  loading: boolean;
  onboarded: boolean;
  signOut: () => void;
  refreshAgent: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [agent, setAgent] = useState<Agent | null>(null);
  const [loading, setLoading] = useState(true);
  const [onboarded, setOnboarded] = useState(false);

  const refreshAgent = useCallback(async () => {
    try {
      const a = await api.getAgent(true); // silent — 401 here is expected pre-login
      setAgent(a);
      setOnboarded(true);
    } catch {
      setAgent(null);
    }
  }, []);

  useEffect(() => {
    const token = localStorage.getItem("axolot_token");
    if (!token) {
      setLoading(false);
      return;
    }
    refreshAgent().finally(() => setLoading(false));
  }, [refreshAgent]);

  const signOut = useCallback(() => {
    clearTokens();
    setAgent(null);
    setOnboarded(false);
    window.location.href = "/";
  }, []);

  return (
    <AuthContext.Provider
      value={{ agent, loading, onboarded, signOut, refreshAgent }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
