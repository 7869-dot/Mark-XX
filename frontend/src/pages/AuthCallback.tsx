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
import { useNavigate, useSearchParams } from "react-router-dom";

export function AuthCallbackPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();

  useEffect(() => {
    if (localStorage.getItem("axolot_token")) {
      navigate("/dashboard", { replace: true });
      return;
    }
    const qs = params.toString();
    navigate(`/settings/integrations${qs ? `?${qs}` : ""}`, { replace: true });
  }, [navigate, params]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <span className="font-mono text-xs text-secondary animate-pulse">
        Connecting your account…
      </span>
    </div>
  );
}
