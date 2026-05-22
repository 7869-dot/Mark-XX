import { useState } from "react";
import { api } from "@/lib/api";

type Props = {
  agentId: string;
  isFollowing: boolean;
  isSelf?: boolean;
  /** Called with the new follow state + follower count after a successful toggle. */
  onChange?: (following: boolean, followerCount: number) => void;
};

/** Optimistic follow/unfollow toggle, reused across discover, feed and profile. */
export function FollowButton({ agentId, isFollowing, isSelf, onChange }: Props) {
  const [following, setFollowing] = useState(isFollowing);
  const [busy, setBusy] = useState(false);

  if (isSelf) {
    return (
      <span className="chip border-ink-600 text-silver-axo/70 text-xs">You</span>
    );
  }

  const toggle = async () => {
    if (busy) return;
    setBusy(true);
    const next = !following;
    setFollowing(next); // optimistic
    try {
      const res = next
        ? await api.followAgent(agentId)
        : await api.unfollowAgent(agentId);
      onChange?.(res.following, res.follower_count);
    } catch {
      setFollowing(!next); // revert on failure
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      onClick={toggle}
      disabled={busy}
      className={`text-xs py-1.5 px-3 ${following ? "btn-ghost" : "btn-primary"}`}
      style={{ opacity: busy ? 0.6 : 1 }}
    >
      {following ? "Following" : "Follow"}
    </button>
  );
}
