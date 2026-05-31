import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

export const INVITE_CODE_KEY = "axolot_invite_code";

/** /join?code=XXXXXXXX — stash the invite code, then send the visitor to sign in.
 *  The code is picked up in onboarding Step 1 and redeemed on completion. */
export function JoinPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();

  useEffect(() => {
    const code = (params.get("code") || "").trim().toUpperCase();
    if (code) localStorage.setItem(INVITE_CODE_KEY, code);
    navigate("/", { replace: true });
  }, [params, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: "#07090f" }}>
      <span className="font-mono text-xs" style={{ color: "#9aa4b2" }}>
        Taking you to Axolot…
      </span>
    </div>
  );
}
