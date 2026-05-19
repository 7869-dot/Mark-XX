import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "@/hooks/useAuth";
import { AppShell } from "@/components/layout/AppShell";
import { LandingPage } from "@/pages/Landing";
import { OnboardingPage } from "@/pages/Onboarding";
import { DashboardPage } from "@/pages/Dashboard";
import { AgentProfilePage } from "@/pages/AgentProfile";
import { NetworkPage } from "@/pages/Network";
import { TasksPage } from "@/pages/Tasks";
import { InboxPage } from "@/pages/Inbox";
import { GmailPage } from "@/pages/Gmail";
import { CalendarPage } from "@/pages/Calendar";
import { IntegrationsSettingsPage } from "@/pages/Settings/Integrations";
import { AuthCallbackPage } from "@/pages/AuthCallback";
import { ToastContainer } from "@/components/ui/ToastContainer";

function Protected({ children }: { children: React.ReactNode }) {
  const { agent, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <span className="font-mono text-xs text-silver-axo animate-pulse">
          Loading agent…
        </span>
      </div>
    );
  }
  if (!agent) return <Navigate to="/onboarding" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastContainer />
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/onboarding" element={<OnboardingPage />} />
          <Route path="/auth/callback" element={<AuthCallbackPage />} />
          <Route
            element={
              <Protected>
                <AppShell />
              </Protected>
            }
          >
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/agent" element={<AgentProfilePage />} />
            <Route path="/network" element={<NetworkPage />} />
            <Route path="/tasks" element={<TasksPage />} />
            <Route path="/inbox" element={<InboxPage />} />
            <Route path="/gmail" element={<GmailPage />} />
            <Route path="/calendar" element={<CalendarPage />} />
            <Route
              path="/settings/integrations"
              element={<IntegrationsSettingsPage />}
            />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
