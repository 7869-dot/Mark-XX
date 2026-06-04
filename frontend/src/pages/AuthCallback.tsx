/**
 * OAuth landing safety-net.
 *
 * The sign-in flow normally lands on /dashboard?token=<jwt> (token captured
 * app-wide before route guards run). The Gmail/Calendar grant 302s straight to
 * /settings/integrations. This route only catches anything that lands on
 * /auth/callback: if a session token is present go to the dashboard, otherwise
 * forward to integrations settings preserving query params for the toast.
 */
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

export function AuthCallbackPage() {
  const navigate = useNavigate();

  useEffect(() => {
    // Both the login grant and the Gmail/Calendar grant funnel back here; in the
    // PA-core app there's a single destination once a session token exists.
    if (localStorage.getItem("axolot_token")) {
      navigate("/app", { replace: true });
      return;
    }
    navigate("/", { replace: true });
  }, [navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <span className="font-mono text-xs text-secondary animate-pulse">
        Connecting your account…
      </span>
    </div>
  );
}
