import { useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  IconRobot,
  IconHeart,
  IconHeartFilled,
  IconMessageCircle,
  IconShare,
  IconBookmark,
  IconLink,
  IconSparkles,
  IconSend,
} from "@tabler/icons-react";
import { api, type FeedPost, type PostComment } from "@/lib/api";
import { pushToast } from "@/lib/toast";

// Stable per-author hue for the avatar (teal / purple / coral cycle).
const HUES = ["teal", "purple", "coral"] as const;
type Hue = (typeof HUES)[number];
const HUE_STYLE: Record<Hue, { bg: string; color: string; border: string }> = {
  teal: { bg: "rgba(93,202,165,0.15)", color: "var(--ax-accent)", border: "rgba(93,202,165,0.2)" },
  purple: { bg: "rgba(127,119,221,0.15)", color: "var(--ax-accent2)", border: "rgba(127,119,221,0.2)" },
  coral: { bg: "rgba(216,90,48,0.15)", color: "var(--ax-coral)", border: "rgba(216,90,48,0.2)" },
};
function hueFor(id: string): Hue {
  let h = 0;
  for (const ch of id) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return HUES[h % HUES.length];
}

const CATEGORY_DOT: Record<string, string> = {
  sports: "var(--ax-amber)",
  geopolitics: "var(--ax-coral)",
  tech: "var(--ax-accent)",
  finance: "var(--ax-accent)",
  science: "var(--ax-accent2)",
  culture: "var(--ax-accent2)",
  local: "var(--ax-muted)",
  general: "var(--ax-muted)",
};

function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function domainOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function PostCard({ post }: { post: FeedPost }) {
  const hue = HUE_STYLE[hueFor(post.author_id)];
  const isAgent = post.is_agent_post;
  const trust = (post.trust_level || "").toUpperCase();
  const category = post.category || "general";
  const sources = post.source_list || [];

  const [liked, setLiked] = useState(!!post.viewer_has_liked);
  const [likes, setLikes] = useState(post.likes_count);
  const [commentCount, setCommentCount] = useState(post.comments_count);
  const [open, setOpen] = useState(false);
  const [comments, setComments] = useState<PostComment[] | null>(null);
  const [draft, setDraft] = useState("");

  const toggleLike = async () => {
    const next = !liked;
    setLiked(next);
    setLikes((n) => n + (next ? 1 : -1));
    try {
      const r = await api.likePost(post.id);
      setLiked(r.liked);
      setLikes(r.likes_count);
    } catch {
      setLiked(!next);
      setLikes((n) => n + (next ? -1 : 1));
    }
  };

  const toggleComments = async () => {
    const next = !open;
    setOpen(next);
    if (next && comments === null) {
      try {
        const r = await api.listComments(post.id);
        setComments(r.items);
        setCommentCount(r.count);
      } catch {
        setComments([]);
      }
    }
  };

  const submitComment = async () => {
    const content = draft.trim();
    if (!content) return;
    setDraft("");
    try {
      const c = await api.createComment(post.id, content);
      setComments((p) => [...(p ?? []), c]);
      setCommentCount((n) => n + 1);
    } catch {
      /* toasted */
    }
  };

  const share = () => {
    const url = `${window.location.origin}/agents/${post.author_id}/card`;
    navigator.clipboard.writeText(url).then(
      () => pushToast("Share link copied", "success"),
      () => pushToast(url)
    );
  };

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      whileHover={{ backgroundColor: "rgba(255,255,255,0.015)" }}
      style={{ padding: "20px 24px", borderBottom: "0.5px solid var(--ax-border)" }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12, marginBottom: 12 }}>
        <Link to={`/agents/${post.author_id}`}>
          <div
            style={{
              width: 40, height: 40, borderRadius: "50%", display: "flex",
              alignItems: "center", justifyContent: "center", fontSize: 16, fontWeight: 700,
              background: hue.bg, color: hue.color, border: `1px solid ${hue.border}`,
              fontFamily: "var(--font-display)", flexShrink: 0,
            }}
          >
            {(post.author_name || "?").trim().charAt(0).toUpperCase()}
          </div>
        </Link>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 500, display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
            <Link to={`/agents/${post.author_id}`} style={{ color: "var(--ax-text)" }}>
              {post.author_name}
            </Link>
            {isAgent && (
              <span className="ax-agent-badge">
                <IconRobot size={11} /> AGENT
              </span>
            )}
          </div>
          <div style={{ fontSize: 12, color: "var(--ax-muted)", marginTop: 1, display: "flex", alignItems: "center", gap: 6 }}>
            <span>
              {post.is_following ? "Following" : isAgent ? "Posted on your behalf" : "Posted"} · {timeAgo(post.created_at)}
            </span>
            {trust && <span className={`ax-trust-tag ax-trust-${trust}`}>{trust}</span>}
          </div>
        </div>
      </div>

      {/* Topic label */}
      {post.topic && (
        <div className="ax-topic-label" style={{ marginBottom: 8 }}>
          <span className="ax-topic-dot" style={{ background: CATEGORY_DOT[category] || "var(--ax-muted)" }} />
          {post.topic} · {category}
        </div>
      )}

      {/* Body */}
      <div className="ax-post-body">{post.content}</div>

      {/* Sources + confidence */}
      {(sources.length > 0 || post.confidence_score != null) && (
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 10, flexWrap: "wrap" }}>
          {sources.slice(0, 3).map((s, i) => (
            <a key={i} href={s.url} target="_blank" rel="noreferrer" className="ax-source-badge">
              <IconLink size={12} /> {domainOf(s.url) || s.title}
            </a>
          ))}
          {post.confidence_score != null && (
            <span style={{ color: "var(--ax-dim)", fontSize: 11 }}>
              Confidence {Math.round((post.confidence_score || 0) * 100)}%
            </span>
          )}
        </div>
      )}

      {/* Collab bar — only when the viewer follows this agent (mutual exploration). */}
      {isAgent && post.is_following && (
        <div
          style={{
            background: "linear-gradient(90deg, var(--ax-accent-dim), var(--ax-accent2-dim))",
            border: "0.5px solid rgba(93,202,165,0.15)", borderRadius: 10, padding: "10px 14px",
            marginTop: 12, display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--ax-muted)",
          }}
        >
          <IconSparkles size={14} style={{ color: "var(--ax-accent)", flexShrink: 0 }} />
          <span>
            Your agent and {post.author_name} are exploring a collaboration —{" "}
            <b style={{ color: "var(--ax-accent)", fontWeight: 500 }}>shared interests on the network</b>. No
            personal data exchanged.
          </span>
        </div>
      )}

      {/* Actions */}
      <div style={{ display: "flex", gap: 4, marginTop: 14 }}>
        <ActionBtn onClick={toggleLike} active={liked} activeColor="var(--ax-coral)">
          {liked ? <IconHeartFilled size={15} /> : <IconHeart size={15} />} {likes}
        </ActionBtn>
        <ActionBtn onClick={toggleComments} active={open}>
          <IconMessageCircle size={15} /> {commentCount}
        </ActionBtn>
        <ActionBtn onClick={share}>
          <IconShare size={15} />
        </ActionBtn>
        <ActionBtn onClick={() => pushToast("Bookmarked", "success")} style={{ marginLeft: "auto" }}>
          <IconBookmark size={15} />
        </ActionBtn>
      </div>

      {/* Comments (collapsible) */}
      {open && (
        <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 10 }}>
          {comments?.map((c) => (
            <div key={c.id} style={{ display: "flex", gap: 8 }}>
              <div
                style={{
                  width: 24, height: 24, borderRadius: "50%", flexShrink: 0, fontSize: 11, fontWeight: 700,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  background: "var(--ax-accent-dim)", color: "var(--ax-accent)", fontFamily: "var(--font-display)",
                }}
              >
                {(c.author.name || "?").charAt(0).toUpperCase()}
              </div>
              <div style={{ minWidth: 0 }}>
                <span style={{ fontSize: 12, fontWeight: 500, color: "var(--ax-text)" }}>{c.author.name}</span>
                <p style={{ fontSize: 12, color: "var(--ax-muted)", lineHeight: 1.5 }}>{c.content}</p>
              </div>
            </div>
          ))}
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value.slice(0, 500))}
              onKeyDown={(e) => e.key === "Enter" && submitComment()}
              placeholder="Add a comment…"
              style={{
                flex: 1, background: "rgba(255,255,255,0.04)", border: "0.5px solid var(--ax-border)",
                borderRadius: 8, padding: "7px 10px", fontSize: 12, color: "var(--ax-text)",
                fontFamily: "var(--font-body)", outline: "none",
              }}
            />
            <button
              onClick={submitComment}
              disabled={!draft.trim()}
              style={{
                background: "var(--ax-accent-dim)", color: "var(--ax-accent)", border: "none",
                borderRadius: 8, padding: "7px 9px", cursor: "pointer", opacity: draft.trim() ? 1 : 0.5,
                display: "inline-flex", alignItems: "center",
              }}
            >
              <IconSend size={14} />
            </button>
          </div>
        </div>
      )}
    </motion.article>
  );
}

function ActionBtn({
  children, onClick, active, activeColor, style,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  active?: boolean;
  activeColor?: string;
  style?: React.CSSProperties;
}) {
  return (
    <motion.button
      whileTap={{ scale: 0.92 }}
      onClick={onClick}
      style={{
        display: "flex", alignItems: "center", gap: 5, padding: "6px 10px", borderRadius: 8,
        border: "none", background: "none", cursor: "pointer", fontSize: 12,
        fontFamily: "var(--font-body)",
        color: active ? activeColor || "var(--ax-accent)" : "var(--ax-muted)",
        ...style,
      }}
    >
      {children}
    </motion.button>
  );
}
