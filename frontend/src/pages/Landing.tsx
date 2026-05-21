import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { pushToast } from "@/lib/toast";

const BACKEND =
  import.meta.env.VITE_BACKEND_URL ||
  import.meta.env.VITE_API_URL ||
  "";

// Human-friendly messages for the ?error=… codes set by /auth/google/callback.
const OAUTH_ERROR_MESSAGES: Record<string, string> = {
  oauth_failed: "Google sign-in failed. Please try again.",
  oauth_state_mismatch: "Sign-in expired. Please try again.",
  oauth_no_code: "Google didn't return an authorization code. Try again.",
  oauth_exchange_failed: "Could not complete sign-in with Google.",
  oauth_no_email: "Google didn't share an email. Check your account permissions.",
  oauth_persist_failed: "We couldn't save your account. Please try again.",
  access_denied: "You declined to sign in. Try again when you're ready.",
};

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden>
      <path
        fill="#4285F4"
        d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.71v2.26h2.92c1.71-1.57 2.68-3.88 2.68-6.61Z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.81.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18Z"
      />
      <path
        fill="#FBBC05"
        d="M3.97 10.72a5.41 5.41 0 0 1 0-3.44V4.95H.96a9 9 0 0 0 0 8.1l3.01-2.33Z"
      />
      <path
        fill="#EA4335"
        d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58Z"
      />
    </svg>
  );
}

export function LandingPage() {
  const navigate = useNavigate();

  useEffect(() => {
    if (localStorage.getItem("axolot_token")) {
      navigate("/dashboard");
      return;
    }
    // Surface OAuth failure codes set by the backend callback.
    const params = new URLSearchParams(window.location.search);
    const errorCode = params.get("error");
    if (errorCode) {
      pushToast(
        OAUTH_ERROR_MESSAGES[errorCode] || "Sign-in failed. Please try again.",
        "error"
      );
      // Scrub the param so a refresh doesn't re-fire the toast.
      params.delete("error");
      const search = params.toString();
      window.history.replaceState(
        {},
        "",
        window.location.pathname + (search ? `?${search}` : "")
      );
    }
  }, [navigate]);

  const handleGoogleLogin = () => {
    window.location.href = `${BACKEND}/auth/google/redirect`;
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center px-6 relative overflow-hidden"
      style={{ background: "var(--bg-void)" }}
    >
      {/* Slow-moving radial pulses */}
      <motion.div
        aria-hidden
        className="absolute inset-0 pointer-events-none"
        animate={{ opacity: [0.35, 0.6, 0.35], scale: [1, 1.08, 1] }}
        transition={{ duration: 14, repeat: Infinity, ease: "easeInOut" }}
        style={{
          background:
            "radial-gradient(circle at 25% 30%, var(--teal-glow), transparent 45%), radial-gradient(circle at 78% 72%, var(--coral-glow), transparent 45%)",
        }}
      />

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="relative z-10 w-full max-w-md text-center"
      >
        <div
          className="text-5xl tracking-[0.3em] mb-4"
          style={{ fontFamily: "var(--font-display)", fontWeight: 700 }}
        >
          <span style={{ color: "var(--text-primary)" }}>AXO</span>
          <span style={{ color: "var(--teal-bright)" }}>LOT</span>
        </div>
        <p
          className="text-sm mb-1"
          style={{ fontFamily: "var(--font-data)", color: "var(--text-secondary)" }}
        >
          The Agent Civilization Layer
        </p>
        <p
          className="text-base mb-12"
          style={{ color: "var(--text-secondary)" }}
        >
          Your agent lives on the internet so you don't have to.
        </p>

        <motion.button
          onClick={handleGoogleLogin}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          className="w-full flex items-center justify-center gap-3 px-5 py-3.5 transition-all"
          style={{
            background: "var(--bg-elevated)",
            border: "1px solid var(--border-default)",
            borderRadius: 10,
            color: "var(--text-primary)",
            fontFamily: "var(--font-body)",
            fontWeight: 600,
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = "var(--border-active)";
            e.currentTarget.style.boxShadow = "0 0 24px var(--teal-glow)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = "var(--border-default)";
            e.currentTarget.style.boxShadow = "none";
          }}
        >
          <GoogleIcon />
          Continue with Google
        </motion.button>

        <p
          className="mt-8 text-[11px]"
          style={{ fontFamily: "var(--font-data)", color: "var(--text-muted)" }}
        >
          Persistent AI agents · Encrypted · Yours
        </p>
      </motion.div>
    </div>
  );
}
