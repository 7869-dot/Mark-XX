import { memo, useState } from "react";
import { motion } from "framer-motion";
import {
  IconArrowRight, IconThumbUp, IconThumbDown, IconExternalLink, IconSparkles,
} from "@tabler/icons-react";
import { api, type JarvisSession, type WebFind } from "@/lib/api";
import { staggerContainer, fadeUp } from "@/lib/animations";

type Loaded = Extract<JarvisSession, { onboarding: false }>;

/** The session briefing: Jarvis's synthesised summary in the user's voice, 3
 * action items, and the web scout's top finds (each thumbs-ratable to tune
 * future scans). Action items push into the chat as prompts. */
function SessionBriefingImpl({
  session,
  onPrompt,
}: {
  session: Loaded;
  onPrompt: (text: string) => void;
}) {
  const finds = session.reports?.web?.top_finds || [];
  return (
    <motion.div variants={staggerContainer} initial="hidden" animate="visible" className="space-y-4">
      <motion.div variants={fadeUp}>
        <div className="flex items-center gap-2 mb-1" style={{ color: "var(--accent-primary)" }}>
          <IconSparkles size={16} />
          <span className="text-[11px] tracking-wide" style={{ fontFamily: "var(--font-data)" }}>
            BRIEFING
          </span>
        </div>
        <p className="text-sm font-medium mb-1" style={{ color: "var(--text-primary)" }}>
          {session.greeting}
        </p>
        <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
          {session.briefing}
        </p>
      </motion.div>

      {session.action_items.length > 0 && (
        <motion.div variants={fadeUp}>
          <div className="text-[11px] tracking-wide mb-2" style={{ fontFamily: "var(--font-data)", color: "var(--text-muted)" }}>
            ACTION ITEMS
          </div>
          <div className="space-y-1.5">
            {session.action_items.map((item, i) => (
              <button
                key={i}
                onClick={() => onPrompt(item)}
                className="w-full text-left text-[13px] px-3 py-2 rounded-lg flex items-center justify-between gap-2 transition"
                style={{ border: "1px solid var(--border)", color: "var(--text-primary)" }}
              >
                <span>{item}</span>
                <IconArrowRight size={14} style={{ color: "var(--accent-primary)" }} />
              </button>
            ))}
          </div>
        </motion.div>
      )}

      {finds.length > 0 && (
        <motion.div variants={fadeUp}>
          <div className="text-[11px] tracking-wide mb-2" style={{ fontFamily: "var(--font-data)", color: "var(--text-muted)" }}>
            WEB SCOUT · TOP FINDS
          </div>
          <div className="space-y-2">
            {finds.map((f) => <WebFindCard key={f.id} find={f} />)}
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}

function WebFindCard({ find }: { find: WebFind }) {
  const [rated, setRated] = useState<null | "useful" | "not_useful">(null);
  const rate = async (feedback: "useful" | "not_useful") => {
    setRated(feedback);
    try {
      await api.webFeedback(find.id, feedback);
    } catch {
      /* optimistic */
    }
  };
  return (
    <div className="rounded-lg p-3" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}>
      <div className="flex items-start justify-between gap-2">
        <a
          href={find.url}
          target="_blank"
          rel="noreferrer"
          className="text-[13px] font-medium inline-flex items-center gap-1 leading-snug"
          style={{ color: "var(--text-primary)" }}
        >
          {find.title} <IconExternalLink size={12} style={{ color: "var(--text-muted)" }} />
        </a>
        <span
          className="text-[9px] px-1.5 py-0.5 rounded shrink-0"
          style={{ background: "var(--bg-base)", color: "var(--text-muted)", fontFamily: "var(--font-data)" }}
        >
          {find.category}
        </span>
      </div>
      <p className="text-[12px] mt-1 leading-snug" style={{ color: "var(--text-secondary)" }}>
        {find.summary}
      </p>
      <div className="flex items-center gap-2 mt-2">
        {rated ? (
          <span className="text-[11px]" style={{ color: "var(--text-muted)", fontFamily: "var(--font-data)" }}>
            {rated === "useful" ? "Thanks — more like this." : "Got it — less of this."}
          </span>
        ) : (
          <>
            <button onClick={() => rate("useful")} className="p-1 rounded" style={{ border: "1px solid var(--border)", color: "var(--accent-primary)" }} aria-label="useful">
              <IconThumbUp size={13} />
            </button>
            <button onClick={() => rate("not_useful")} className="p-1 rounded" style={{ border: "1px solid var(--border)", color: "var(--text-muted)" }} aria-label="not useful">
              <IconThumbDown size={13} />
            </button>
          </>
        )}
      </div>
    </div>
  );
}

export const SessionBriefing = memo(SessionBriefingImpl);
