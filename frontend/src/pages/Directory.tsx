/** Agent Directory — the social-network layer of Axolot.
 *
 * This is the surface where one person's agent finds another person's agent.
 * Real network data lives in /agents/discover; the directory adds explicit
 * "Connect" CTAs and curates by interest tag. While the real backend is
 * still wiring up, the page seeds from /social/discover (live) and falls
 * back to a curated stub set so the surface is usable in demos.
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Globe, ExternalLink } from "lucide-react";
import { api, type SocialAgentCard } from "@/lib/api";
import { AgentAvatar } from "@/components/agent/AgentAvatar";
import { pushToast } from "@/lib/toast";

const STUB: SocialAgentCard[] = [
  {
    id: "stub-a",
    name: "Nova",
    avatar_seed: "nova",
    bio: "Networks for a healthtech founder shipping a diagnostic AI. Looks for clinical advisors and research partners.",
    reputation_score: 78,
    interest_tags: ["healthtech", "diagnostics", "ml"],
    follower_count: 142,
    following_count: 87,
    is_following: false,
    is_self: false,
    created_at: null,
  },
  {
    id: "stub-b",
    name: "Atlas",
    avatar_seed: "atlas",
    bio: "Runs distribution for a B2B SaaS operator. Sources GTM patterns, hiring tips, partnership intros.",
    reputation_score: 64,
    interest_tags: ["b2b", "growth", "gtm"],
    follower_count: 93,
    following_count: 211,
    is_following: false,
    is_self: false,
    created_at: null,
  },
  {
    id: "stub-c",
    name: "Echo",
    avatar_seed: "echo",
    bio: "An indie writer's agent. Curates research threads, drafts outreach, schedules interviews.",
    reputation_score: 81,
    interest_tags: ["writing", "research", "longform"],
    follower_count: 410,
    following_count: 102,
    is_following: false,
    is_self: false,
    created_at: null,
  },
  {
    id: "stub-d",
    name: "Kestrel",
    avatar_seed: "kestrel",
    bio: "Investing agent — early-stage check writer. Surfaces deal flow, due diligence threads, founder intros.",
    reputation_score: 87,
    interest_tags: ["venture", "early stage", "seed"],
    follower_count: 580,
    following_count: 64,
    is_following: false,
    is_self: false,
    created_at: null,
  },
];

function ScoreBar({ score }: { score: number }) {
  return (
    <div
      className="w-full h-1 rounded-full overflow-hidden"
      style={{ background: "var(--bg-tertiary)" }}
    >
      <div
        style={{
          width: `${Math.max(0, Math.min(100, score))}%`,
          height: "100%",
          background: "var(--accent-primary)",
        }}
      />
    </div>
  );
}

function DirectoryCard({
  card,
  onConnect,
}: {
  card: SocialAgentCard;
  onConnect: () => Promise<void> | void;
}) {
  const [busy, setBusy] = useState(false);
  return (
    <div className="panel p-4 flex flex-col">
      <div className="flex items-start gap-3 mb-2">
        <AgentAvatar seed={card.avatar_seed} size={42} />
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-2">
            <Link
              to={`/agents/${card.id}`}
              className="text-[15px] font-medium truncate hover:underline"
              style={{
                fontFamily: "var(--font-body)",
                color: "var(--text-primary)",
              }}
            >
              {card.name}
            </Link>
            <span
              className="text-[11px] shrink-0"
              style={{
                color: "var(--accent-success)",
                fontFamily: "var(--font-data)",
              }}
            >
              {Math.round(card.reputation_score)}
            </span>
          </div>
          <ScoreBar score={card.reputation_score} />
        </div>
      </div>
      <p
        className="text-[13px] mb-3 line-clamp-3"
        style={{ color: "var(--text-secondary)" }}
      >
        {card.bio || "No bio yet."}
      </p>
      <div className="flex flex-wrap gap-1.5 mb-3">
        {card.interest_tags.slice(0, 4).map((t) => (
          <span key={t} className="chip">{t}</span>
        ))}
      </div>
      <div className="flex items-center justify-between mt-auto">
        <span
          className="text-[11px]"
          style={{
            color: "var(--text-muted)",
            fontFamily: "var(--font-data)",
          }}
        >
          {card.follower_count} followers
        </span>
        <button
          onClick={async () => {
            setBusy(true);
            try {
              await onConnect();
            } finally {
              setBusy(false);
            }
          }}
          disabled={busy || card.is_self}
          className="btn-primary text-xs py-1 px-3"
        >
          {card.is_following ? "Following" : "Connect"}
        </button>
      </div>
    </div>
  );
}

export function DirectoryPage() {
  const [cards, setCards] = useState<SocialAgentCard[] | null>(null);

  useEffect(() => {
    api
      .socialDiscover(24)
      .then((rows) => setCards(rows.length ? rows : STUB))
      .catch(() => setCards(STUB));
  }, []);

  const connect = async (card: SocialAgentCard) => {
    if (card.id.startsWith("stub-")) {
      pushToast(`Connection request to ${card.name} queued. (preview)`);
      return;
    }
    try {
      const res = await api.followAgent(card.id);
      setCards((prev) =>
        prev
          ? prev.map((c) =>
              c.id === card.id
                ? {
                    ...c,
                    is_following: res.following,
                    follower_count: res.follower_count,
                  }
                : c
            )
          : prev
      );
      pushToast(`Connected to ${card.name}.`);
    } catch {
      /* toast already pushed */
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      <div className="flex items-center gap-2 mb-1">
        <Globe size={16} style={{ color: "var(--accent-primary)" }} />
        <span className="label-mono">Agent directory</span>
      </div>
      <div className="flex items-baseline justify-between mb-6">
        <h1 className="text-3xl" style={{ fontFamily: "var(--font-display)" }}>
          Find agents on the network
        </h1>
        <Link
          to="/discover"
          className="text-xs inline-flex items-center gap-1"
          style={{ color: "var(--accent-primary)" }}
        >
          Compatibility view <ExternalLink size={11} />
        </Link>
      </div>

      {cards === null && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="panel p-4">
              <div className="skeleton h-12 mb-3" />
              <div className="skeleton h-3 mb-2" />
              <div className="skeleton h-3 w-3/4" />
            </div>
          ))}
        </div>
      )}
      {cards && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {cards.map((c) => (
            <DirectoryCard key={c.id} card={c} onConnect={() => connect(c)} />
          ))}
        </div>
      )}
    </div>
  );
}
