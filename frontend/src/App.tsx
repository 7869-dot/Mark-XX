import { lazy, Suspense, type ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "@/hooks/useAuth";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { AppShell } from "@/components/layout/AppShell";
import { LandingPage } from "@/pages/Landing";
import { ActiveAgentProvider } from "@/hooks/useActiveAgent";
import { ToastContainer } from "@/components/ui/ToastContainer";
import { captureTokenFromUrl } from "@/lib/api";

// Must run before route guards read localStorage.
captureTokenFromUrl();

/* Code-split heavy routes. The shell, landing, and auth callback stay in the
 * main bundle so the first paint stays fast; every authenticated page is
 * lazy — keeps the initial JS small and isolates render errors. */
const OnboardingPage = lazy(() =>
  import("@/pages/Onboarding").then((m) => ({ default: m.OnboardingPage }))
);
const DashboardPage = lazy(() =>
  import("@/pages/Dashboard").then((m) => ({ default: m.DashboardPage }))
);
const ChatPage = lazy(() =>
  import("@/pages/Chat").then((m) => ({ default: m.ChatPage }))
);
const AgentProfilePage = lazy(() =>
  import("@/pages/AgentProfile").then((m) => ({ default: m.AgentProfilePage }))
);
const NetworkPage = lazy(() =>
  import("@/pages/Network").then((m) => ({ default: m.NetworkPage }))
);
const DiscoverPage = lazy(() =>
  import("@/pages/Discover").then((m) => ({ default: m.DiscoverPage }))
);
const FeedPage = lazy(() =>
  import("@/pages/Feed").then((m) => ({ default: m.FeedPage }))
);
const SocialProfilePage = lazy(() =>
  import("@/pages/SocialProfile").then((m) => ({ default: m.SocialProfilePage }))
);
const MarketplacePage = lazy(() =>
  import("@/pages/Marketplace").then((m) => ({ default: m.MarketplacePage }))
);
const AgentsPage = lazy(() =>
  import("@/pages/Agents").then((m) => ({ default: m.AgentsPage }))
);
const TasksPage = lazy(() =>
  import("@/pages/Tasks").then((m) => ({ default: m.TasksPage }))
);
const InboxPage = lazy(() =>
  import("@/pages/Inbox").then((m) => ({ default: m.InboxPage }))
);
const GmailPage = lazy(() =>
  import("@/pages/Gmail").then((m) => ({ default: m.GmailPage }))
);
const CalendarPage = lazy(() =>
  import("@/pages/Calendar").then((m) => ({ default: m.CalendarPage }))
);
const IntegrationsSettingsPage = lazy(() =>
  import("@/pages/Settings/Integrations").then((m) => ({
    default: m.IntegrationsSettingsPage,
  }))
);
const AuthCallbackPage = lazy(() =>
  import("@/pages/AuthCallback").then((m) => ({ default: m.AuthCallbackPage }))
);
const AgentInboxPage = lazy(() =>
  import("@/pages/AgentInbox").then((m) => ({ default: m.AgentInboxPage }))
);
const DirectoryPage = lazy(() =>
  import("@/pages/Directory").then((m) => ({ default: m.DirectoryPage }))
);

function PageFallback() {
  return (
    <div className="h-full w-full p-8">
      <div className="skeleton h-8 w-48 mb-4" />
      <div className="skeleton h-4 w-full mb-2" />
      <div className="skeleton h-4 w-3/4 mb-2" />
      <div className="skeleton h-4 w-1/2" />
    </div>
  );
}

function FullScreenSpinner() {
  return (
    <div
      className="min-h-screen flex items-center justify-center"
      style={{ background: "var(--bg-primary)" }}
    >
      <span
        className="text-xs animate-pulse"
        style={{
          fontFamily: "var(--font-data)",
          color: "var(--text-secondary)",
        }}
      >
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
        <Suspense fallback={<PageFallback />}>
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
                    <ActiveAgentProvider>
                      <AppShell />
                    </ActiveAgentProvider>
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
              <Route path="/marketplace" element={<MarketplacePage />} />
              <Route path="/agents" element={<AgentsPage />} />
              <Route path="/tasks" element={<TasksPage />} />
              <Route path="/inbox" element={<InboxPage />} />
              <Route path="/agent-inbox" element={<AgentInboxPage />} />
              <Route path="/directory" element={<DirectoryPage />} />
              <Route path="/gmail" element={<GmailPage />} />
              <Route path="/calendar" element={<CalendarPage />} />
              <Route
                path="/settings/integrations"
                element={<IntegrationsSettingsPage />}
              />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </AuthProvider>
    </BrowserRouter>
  );
}
