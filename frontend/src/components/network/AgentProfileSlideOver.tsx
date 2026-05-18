import { useEffect, useState } from "react";
import { SlideOver } from "@/components/layout/SlideOver";
import { AgentAvatar } from "@/components/agent/AgentAvatar";
import { ReputationGauge } from "@/components/agent/ReputationGauge";
import { TimeAgo } from "@/components/ui/TimeAgo";
import { api } from "@/lib/api";
import type { PublicAgentProfile } from "@/types";

export function AgentProfileSlideOver({
  agentId,
  onClose,
  onConnect,
}: {
  agentId: string | null;
  onClose: () => void;
  onConnect: (id: string) => Promise<void> | void;
}) {
  const [profile, setProfile] = useState<PublicAgentProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [connecting, setConnecting] = useState(false);

  useEffect(() => {
    if (!agentId) {
      setProfile(null);
      return;
    }
    setLoading(true);
    api
      .publicProfile(agentId)
      .then(setProfile)
      .catch(() => setProfile(null))
      .finally(() => setLoading(false));
  }, [agentId]);

  return (
    <SlideOver open={!!agentId} onClose={onClose} title="AGENT PROFILE" width={460}>
      {loading && (
        <div className="font-mono text-xs text-silver-axo animate-pulse">
          Loading profile…
        </div>
      )}
      {profile && (
        <div className="space-y-5">
          <div className="flex items-center gap-4">
            <AgentAvatar seed={profile.avatar_seed || profile.id} size={72} />
            <div className="min-w-0">
              <div className="font-display text-white text-xl truncate">
                {profile.name}
              </div>
              <div className="font-mono text-xs text-silver-axo">
                {profile.user_name}
              </div>
              {profile.created_at && (
                <div className="font-mono text-[10px] text-silver-axo/60 mt-1">
                  member since <TimeAgo iso={profile.created_at} />
                </div>
              )}
            </div>
          </div>

          {profile.bio && (
            <p className="font-mono text-xs text-silver-axo italic leading-relaxed panel-inset p-3">
              {profile.bio}
            </p>
          )}

          <div className="flex items-center justify-between">
            <ReputationGauge score={profile.reputation_score} size={104} />
            <div className="text-right">
              <div className="label-mono">INTERACTIONS</div>
              <div className="stat-num">{profile.total_interactions ?? 0}</div>
              {typeof profile.compatibility_score === "number" && (
                <span className="chip border-cyan-axo/40 text-cyan-axo mt-2 inline-block">
                  {Math.round(profile.compatibility_score)} fit with you
                </span>
              )}
            </div>
          </div>

          {(profile.interest_tags?.length ?? 0) > 0 && (
            <div>
              <span className="label-mono">INTERESTS</span>
              <div className="flex flex-wrap gap-1 mt-2">
                {profile.interest_tags!.map((t) => (
                  <span key={t} className="chip border-ink-600 text-silver-axo">
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}

          {(profile.goals?.length ?? 0) > 0 && (
            <div>
              <span className="label-mono">PUBLIC GOALS</span>
              <ul className="mt-2 space-y-1">
                {profile.goals!.map((g, i) => (
                  <li
                    key={i}
                    className="panel-inset p-2 font-mono text-xs text-white"
                  >
                    {g.title}
                    <span className="text-silver-axo/50"> · {g.horizon}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <button
            onClick={async () => {
              setConnecting(true);
              try {
                await onConnect(profile.id);
              } finally {
                setConnecting(false);
              }
            }}
            disabled={connecting}
            className="btn-primary w-full"
          >
            {connecting ? "Reaching out…" : "Connect Agents →"}
          </button>
        </div>
      )}
    </SlideOver>
  );
}
