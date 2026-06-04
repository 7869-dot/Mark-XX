import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "@/hooks/useAuth";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { LandingPage } from "@/pages/Landing";
import { ToastContainer } from "@/components/ui/ToastContainer";
import { captureTokenFromUrl } from "@/lib/api";

// Must run before route guards read localStorage.
captureTokenFromUrl();

const HomePage = lazy(() =>
  import("@/pages/Home").then((m) => ({ default: m.HomePage }))
);
const AuthCallbackPage = lazy(() =>
  import("@/pages/AuthCallback").then((m) => ({ default: m.AuthCallbackPage }))
);

function FullScreenSpinner() {
  return (
    <div
      className="min-h-screen flex items-center justify-center"
      style={{ background: "var(--bg-base)" }}
    >
      <span
        className="text-xs animate-pulse"
        style={{ fontFamily: "var(--font-data)", color: "var(--text-secondary)" }}
      >
        Loading…
      </span>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastContainer />
        <Suspense fallback={<FullScreenSpinner />}>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/auth/callback" element={<AuthCallbackPage />} />
            <Route
              path="/app"
              element={
                <ProtectedRoute>
                  <HomePage />
                </ProtectedRoute>
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </AuthProvider>
    </BrowserRouter>
  );
}
