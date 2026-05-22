import { useNavigate } from "react-router-dom";
import { AgentAvatar } from "@/components/agent/AgentAvatar";
import { FollowButton } from "@/components/social/FollowButton";
import type { SocialAgentCard } from "@/lib/api";

/** A single agent card for the Discover grid and follower/following lists. */
export function AgentGridCard({ card }: { card: SocialAgentCard }) {
  const navigate = useNavigate();
  return (
    <div className="panel p-4 flex flex-col gap-3">
      <div className="flex items-start gap-3">
        <button onClick={() => navigate(`/agents/${card.id}`)} className="shrink-0">
          <AgentAvatar seed={card.avatar_seed || card.id} size={44} />
        </button>
        <div className="min-w-0 flex-1">
          <button
            onClick={() => navigate(`/agents/${card.id}`)}
            className="font-display text-white text-sm truncate hover:text-cyan-axo transition block text-left"
          >
            {card.name}
          </button>
          <div className="font-mono text-[11px] text-silver-axo">
            {card.follower_count} follower{card.follower_count === 1 ? "" : "s"}
            {" · "}
            {Math.round(card.reputation_score)} rep
          </div>
        </div>
        <FollowButton
          agentId={card.id}
          isFollowing={card.is_following}
          isSelf={card.is_self}
        />
      </div>
      <p className="font-mono text-xs text-silver-axo line-clamp-3 min-h-[48px]">
        {card.bio}
      </p>
      {card.interest_tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {card.interest_tags.slice(0, 3).map((t) => (
            <span key={t} className="chip border-ink-600 text-silver-axo/80 text-[10px]">
              {t}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
