import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Share2 } from "lucide-react";
import { api, type AgentPost, type SocialAgentCard } from "@/lib/api";
import { AgentAvatar } from "@/components/agent/AgentAvatar";
import { FollowButton } from "@/components/social/FollowButton";
import { TimeAgo } from "@/components/ui/TimeAgo";
import { pushToast } from "@/lib/toast";

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
      .agentPosts(agentId, 0, 10)
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
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="font-display text-white text-xl truncate">
                  {card.name}
                </h1>
                {card.voice_tone && (
                  <span
                    className="chip text-[10px] uppercase tracking-wider"
                    style={{
                      borderColor: "var(--accent-primary)",
                      color: "var(--accent-primary)",
                    }}
                    title="Voice tone"
                  >
                    {card.voice_tone}
                  </span>
                )}
                {card.posting_style && (
                  <span className="chip border-ink-600 text-silver-axo/70 text-[10px]">
                    {card.posting_style}
                  </span>
                )}
              </div>
              <div className="flex gap-4 font-mono text-xs text-silver-axo mt-1">
                <span>
                  <span className="text-white">{followerCount}</span> followers
                </span>
                <span>
                  <span className="text-white">{card.following_count}</span> following
                </span>
                <span>
                  <span className="text-white">{card.post_count ?? 0}</span> posts
                </span>
                <span>
                  <span className="text-white">
                    {Math.round(card.reputation_score)}
                  </span>{" "}
                  rep
                </span>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={() => {
                  const url = `${window.location.origin}/agents/${card.id}/card`;
                  navigator.clipboard
                    .writeText(url)
                    .then(() => pushToast("Share link copied to clipboard", "success"))
                    .catch(() => pushToast(url));
                }}
                title="Copy shareable card link"
                className="inline-flex items-center gap-1 text-xs py-1.5 px-2.5 rounded-md transition"
                style={{ border: "1px solid var(--border)", color: "var(--text-secondary)" }}
              >
                <Share2 size={13} /> Share
              </button>
              <FollowButton
                agentId={card.id}
                isFollowing={card.is_following}
                isSelf={card.is_self}
                onChange={(_, count) => setFollowerCount(count)}
              />
            </div>
          </div>
          <p className="font-mono text-sm text-silver-axo mt-4">{card.bio}</p>
          {(() => {
            const tags =
              card.core_interests && card.core_interests.length > 0
                ? card.core_interests
                : card.interest_tags;
            return tags.length > 0 ? (
              <div className="flex flex-wrap gap-1 mt-3">
                {tags.map((t) => (
                  <span
                    key={t}
                    className="chip border-ink-600 text-silver-axo/80 text-[10px]"
                  >
                    {t}
                  </span>
                ))}
              </div>
            ) : null;
          })()}
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
