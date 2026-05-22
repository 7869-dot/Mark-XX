import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "@/hooks/useAuth";
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
                <OnboardingPage />
              </ProtectedRoute>
            }
          />
          <Route
            element={
              <ProtectedRoute>
                <AppShell />
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
