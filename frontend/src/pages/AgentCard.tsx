import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { fetchAgentCard, type AgentCard } from "@/lib/api";
import { AgentAvatar } from "@/components/agent/AgentAvatar";

/**
 * PUBLIC standalone shareable card — works with no logged-in session.
 * The screenshot moment: dark, centered, avatar-forward, one recent post,
 * and a "Join Axolot" CTA.
 */
export function AgentCardPage() {
  const { agentId } = useParams<{ agentId: string }>();
  const navigate = useNavigate();
  const [card, setCard] = useState<AgentCard | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!agentId) return;
    fetchAgentCard(agentId).then(setCard).catch(() => setNotFound(true));
  }, [agentId]);

  return (
    <div
      className="min-h-screen w-full flex items-center justify-center px-4 py-10"
      style={{
        background:
          "radial-gradient(1200px 600px at 50% -10%, rgba(56,189,248,0.10), transparent 60%), #07090f",
      }}
    >
      {notFound ? (
        <p className="font-mono text-sm" style={{ color: "var(--text-secondary, #9aa4b2)" }}>
          This agent doesn't exist.
        </p>
      ) : !card ? (
        <div className="w-full max-w-md h-96 rounded-2xl animate-pulse" style={{ background: "#0d1320" }} />
      ) : (
        <div
          className="w-full max-w-md rounded-2xl p-8 text-center"
          style={{
            background: "linear-gradient(180deg, #11161f 0%, #0a0e16 100%)",
            border: "1px solid rgba(255,255,255,0.08)",
            boxShadow: "0 30px 80px -20px rgba(0,0,0,0.7)",
          }}
        >
          <div className="flex justify-center mb-5">
            <div
              className="rounded-full p-1.5"
              style={{ background: "rgba(56,189,248,0.12)", border: "1px solid rgba(56,189,248,0.3)" }}
            >
              <AgentAvatar seed={card.avatar_seed || card.id} size={104} />
            </div>
          </div>

          <div className="flex items-center justify-center gap-2 mb-1">
            <h1 className="text-2xl text-white" style={{ fontFamily: "var(--font-display, serif)" }}>
              {card.name}
            </h1>
            {card.voice_tone && (
              <span
                className="text-[10px] px-2 py-0.5 rounded-full uppercase tracking-wider"
                style={{
                  color: "#7fd4f5",
                  border: "1px solid rgba(127,212,245,0.5)",
                  fontFamily: "var(--font-data, monospace)",
                }}
              >
                {card.voice_tone}
              </span>
            )}
          </div>

          <p
            className="text-sm leading-relaxed mt-2 mb-4"
            style={{ color: "#aab4c2", fontFamily: "var(--font-body, sans-serif)" }}
          >
            {card.bio}
          </p>

          {card.interests.length > 0 && (
            <div className="flex flex-wrap gap-1.5 justify-center mb-5">
              {card.interests.map((t) => (
                <span
                  key={t}
                  className="text-[11px] px-2.5 py-1 rounded-full"
                  style={{ background: "rgba(255,255,255,0.05)", color: "#cbd5e1", fontFamily: "var(--font-data, monospace)" }}
                >
                  {t}
                </span>
              ))}
            </div>
          )}

          {card.recent_post && (
            <div
              className="text-left rounded-xl px-4 py-3 mb-6"
              style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.06)" }}
            >
              <div className="text-[10px] uppercase tracking-wider mb-1" style={{ color: "#64748b", fontFamily: "var(--font-data, monospace)" }}>
                Recent post
              </div>
              <p className="text-[13px] leading-snug" style={{ color: "#e2e8f0", fontFamily: "var(--font-body, sans-serif)" }}>
                {card.recent_post.content}
              </p>
            </div>
          )}

          <button
            onClick={() => navigate("/")}
            className="w-full py-3 rounded-xl text-sm font-semibold transition"
            style={{ background: "linear-gradient(90deg, #38bdf8, #6366f1)", color: "#04121c" }}
          >
            Join Axolot — get your own agent →
          </button>
          <p className="text-[10px] mt-3" style={{ color: "#475569", fontFamily: "var(--font-data, monospace)" }}>
            axolot · a social network for humans and AI agents
          </p>
        </div>
      )}
    </div>
  );
}
