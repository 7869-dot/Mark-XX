import type { ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "@/hooks/useAuth";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { AppShell } from "@/components/layout/AppShell";
import { LandingPage } from "@/pages/Landing";
import { OnboardingPage } from "@/pages/Onboarding";
import { DashboardPage } from "@/pages/Dashboard";
import { ChatPage } from "@/pages/Chat";
import { AgentProfilePage } from "@/pages/AgentProfile";
import { NetworkPage } from "@/pages/Network";
import { DiscoverPage } from "@/pages/Discover";
import { FeedPage } from "@/pages/Feed";
import { SocialProfilePage } from "@/pages/SocialProfile";
import { TasksPage } from "@/pages/Tasks";
import { InboxPage } from "@/pages/Inbox";
import { GmailPage } from "@/pages/Gmail";
import { CalendarPage } from "@/pages/Calendar";
import { IntegrationsSettingsPage } from "@/pages/Settings/Integrations";
import { AuthCallbackPage } from "@/pages/AuthCallback";
import { ToastContainer } from "@/components/ui/ToastContainer";
import { captureTokenFromUrl } from "@/lib/api";

// Must run before route guards read localStorage.
captureTokenFromUrl();

function FullScreenSpinner() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <span className="font-mono text-xs text-silver-axo animate-pulse">
        Loading…
      </span>
    </div>
  );
}

/** Gate the main app behind a finished onboarding. A signed-in user who hasn't
 *  completed the 3-step flow is bounced to /onboarding from anywhere. */
function RequireOnboarded({ children }: { children: ReactNode }) {
  const { loading, onboardingComplete, agent } = useAuth();
  if (loading) return <FullScreenSpinner />;
  if (agent && !onboardingComplete) return <Navigate to="/onboarding" replace />;
  return <>{children}</>;
}

/** The /onboarding route itself — a returning, already-onboarded user is sent
 *  straight to their feed instead of re-running the flow. */
function OnboardingRoute() {
  const { loading, onboardingComplete } = useAuth();
  if (loading) return <FullScreenSpinner />;
  if (onboardingComplete) return <Navigate to="/feed" replace />;
  return <OnboardingPage />;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastContainer />
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/auth/callback" element={<AuthCallbackPage />} />
          <Route
            path="/onboarding"
            element={
              <ProtectedRoute>
                <OnboardingRoute />
              </ProtectedRoute>
            }
          />
          <Route
            element={
              <ProtectedRoute>
                <RequireOnboarded>
                  <AppShell />
                </RequireOnboarded>
              </ProtectedRoute>
            }
          >
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/agent" element={<AgentProfilePage />} />
            <Route path="/network" element={<NetworkPage />} />
            <Route path="/discover" element={<DiscoverPage />} />
            <Route path="/feed" element={<FeedPage />} />
            <Route path="/agents/:agentId" element={<SocialProfilePage />} />
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
