/**
 * OAuth landing safety-net.
 *
 * The backend performs the Google authorization-code exchange server-side and
 * 302-redirects to /settings/integrations?connected=google (or ?error=true).
 * This route only exists in case anything ever lands on /auth/callback — it
 * forwards to the integrations settings page preserving query params so the
 * connect/error toast still fires. The frontend never handles the raw `code`.
 */
import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

export function AuthCallbackPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();

  useEffect(() => {
    const qs = params.toString();
    navigate(`/settings/integrations${qs ? `?${qs}` : ""}`, { replace: true });
  }, [navigate, params]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <span className="font-mono text-xs text-silver-axo animate-pulse">
        Connecting your account…
      </span>
    </div>
  );
}
