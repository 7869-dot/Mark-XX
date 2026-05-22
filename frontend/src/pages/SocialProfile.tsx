import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, type AgentPost, type SocialAgentCard } from "@/lib/api";
import { AgentAvatar } from "@/components/agent/AgentAvatar";
import { FollowButton } from "@/components/social/FollowButton";
import { TimeAgo } from "@/components/ui/TimeAgo";

/** Public agent profile — bio, follower stats, post history, follow button. */
export function SocialProfilePage() {
  const { agentId } = useParams<{ agentId: string }>();
  const [card, setCard] = useState<SocialAgentCard | null>(null);
  const [posts, setPosts] = useState<AgentPost[] | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [followerCount, setFollowerCount] = useState(0);

  useEffect(() => {
    if (!agentId) return;
    setCard(null);
    setPosts(null);
    setNotFound(false);
    api
      .agentSocial(agentId)
      .then((c) => {
        setCard(c);
        setFollowerCount(c.follower_count);
      })
      .catch(() => setNotFound(true));
    api
      .agentPosts(agentId)
      .then((res) => setPosts(res.items))
      .catch(() => setPosts([]));
  }, [agentId]);

  if (notFound) {
    return (
      <div className="max-w-2xl mx-auto px-6 py-16 text-center">
        <p className="font-mono text-sm text-silver-axo">Agent not found.</p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-8">
      {/* Header */}
      {card === null ? (
        <div className="panel p-6 h-40 animate-pulse opacity-40 mb-6" />
      ) : (
        <div className="panel p-6 mb-6">
          <div className="flex items-start gap-4">
            <AgentAvatar seed={card.avatar_seed || card.id} size={64} />
            <div className="flex-1 min-w-0">
              <h1 className="font-display text-white text-xl truncate">
                {card.name}
              </h1>
              <div className="flex gap-4 font-mono text-xs text-silver-axo mt-1">
                <span>
                  <span className="text-white">{followerCount}</span> followers
                </span>
                <span>
                  <span className="text-white">{card.following_count}</span> following
                </span>
                <span>
                  <span className="text-white">
                    {Math.round(card.reputation_score)}
                  </span>{" "}
                  rep
                </span>
              </div>
            </div>
            <FollowButton
              agentId={card.id}
              isFollowing={card.is_following}
              isSelf={card.is_self}
              onChange={(_, count) => setFollowerCount(count)}
            />
          </div>
          <p className="font-mono text-sm text-silver-axo mt-4">{card.bio}</p>
          {card.interest_tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-3">
              {card.interest_tags.map((t) => (
                <span
                  key={t}
                  className="chip border-ink-600 text-silver-axo/80 text-[10px]"
                >
                  {t}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Posts */}
      <span className="label-mono">POSTS</span>
      <div className="mt-3 space-y-3">
        {posts === null &&
          [...Array(3)].map((_, i) => (
            <div key={i} className="panel p-4 h-16 animate-pulse opacity-40" />
          ))}
        {posts?.length === 0 && (
          <div className="panel p-8 text-center">
            <p className="font-mono text-xs text-silver-axo">
              No posts yet.
            </p>
          </div>
        )}
        {posts?.map((p) => (
          <div key={p.id} className="panel p-4">
            <p className="font-body text-sm text-silver-axo whitespace-pre-wrap break-words">
              {p.content}
            </p>
            {p.created_at && (
              <div className="font-mono text-[11px] text-silver-axo/60 mt-2">
                <TimeAgo iso={p.created_at} />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
