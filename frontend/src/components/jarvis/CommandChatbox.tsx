import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  IconMail, IconCalendar, IconSearch, IconPencil, IconSend,
  IconCheck, IconX, IconChevronRight,
} from "@tabler/icons-react";
import { api, type ChatModeValue, type JarvisAction } from "@/lib/api";
import { fadeUp, slideUp } from "@/lib/animations";
import { pushToast } from "@/lib/toast";

const MODES: { id: Exclude<ChatModeValue, "default">; label: string; icon: React.ReactNode; placeholder: string }[] = [
  { id: "email", label: "Email", icon: <IconMail size={15} />, placeholder: "Who do you need to reach, and what do you want to say?" },
  { id: "schedule", label: "Schedule", icon: <IconCalendar size={15} />, placeholder: "What needs to go on the calendar?" },
  { id: "research", label: "Research", icon: <IconSearch size={15} />, placeholder: "What do you want to know?" },
  { id: "post", label: "Post", icon: <IconPencil size={15} />, placeholder: "What do you want to say to the world?" },
];
const DEFAULT_PLACEHOLDER = "Think out loud with Jarvis…";

type Turn = {
  id: string;
  role: "user" | "jarvis";
  text: string;
  action?: JarvisAction | null;
  followUp?: string | null;
};

export function CommandChatbox() {
  const [params] = useSearchParams();
  const [mode, setMode] = useState<ChatModeValue>("default");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // "Let's get into it" pre-loads the Jarvis question and focuses the input.
  useEffect(() => {
    const q = params.get("q");
    if (q) {
      setInput(q);
      inputRef.current?.focus();
    }
  }, [params]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns]);

  const placeholder = mode === "default" ? DEFAULT_PLACEHOLDER : MODES.find((m) => m.id === mode)!.placeholder;

  const send = async (override?: string) => {
    const text = (override ?? input).trim();
    if (!text || sending) return;
    setInput("");
    setSending(true);
    const uid = crypto.randomUUID();
    setTurns((t) => [...t, { id: uid, role: "user", text }]);
    try {
      const r = await api.jarvisChat(text, mode);
      setTurns((t) => [
        ...t,
        { id: crypto.randomUUID(), role: "jarvis", text: r.reply, action: r.action, followUp: r.follow_up },
      ]);
    } catch {
      setTurns((t) => [...t, { id: crypto.randomUUID(), role: "jarvis", text: "Something glitched — try that again?" }]);
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  };

  return (
    <div className="flex flex-col h-full" style={{ background: "var(--bg-base)" }}>
      {/* Mode bar */}
      <div className="flex items-center gap-2 px-4 py-3" style={{ borderBottom: "1px solid var(--border)" }}>
        {MODES.map((m) => {
          const active = mode === m.id;
          return (
            <motion.button
              key={m.id}
              layout
              onClick={() => setMode(active ? "default" : m.id)}
              whileTap={{ scale: 0.96 }}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition"
              style={{
                border: `1px solid ${active ? "var(--accent-primary)" : "var(--border)"}`,
                background: active ? "var(--accent-blue-muted, rgba(93,202,165,0.12))" : "transparent",
                color: active ? "var(--accent-primary)" : "var(--text-secondary)",
                fontFamily: "var(--font-data)",
                scale: active ? 1.04 : 1,
              }}
            >
              {m.icon} {m.label}
            </motion.button>
          );
        })}
      </div>

      {/* Transcript */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-5 space-y-4">
        {turns.length === 0 && (
          <div className="text-center mt-10 text-sm" style={{ color: "var(--text-muted)" }}>
            {mode === "default"
              ? "Think out loud — Jarvis pushes back, builds on it, names what you're avoiding."
              : `${MODES.find((m) => m.id === mode)!.label} mode — Jarvis routes this to your team.`}
          </div>
        )}
        <AnimatePresence initial={false}>
          {turns.map((t) => (
            <motion.div
              key={t.id}
              variants={fadeUp}
              initial="hidden"
              animate="visible"
              className={`flex ${t.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div className="max-w-[80%]">
                <div
                  className="rounded-2xl px-4 py-2.5 text-[14px] leading-relaxed"
                  style={
                    t.role === "user"
                      ? { background: "var(--accent-primary)", color: "#08121c" }
                      : { background: "var(--bg-elevated)", color: "var(--text-primary)" }
                  }
                >
                  {t.text}
                </div>
                {t.action && <ActionCard action={t.action} />}
                {t.followUp && (
                  <button
                    onClick={() => send(t.followUp!)}
                    className="mt-2 text-[12px] px-2.5 py-1 rounded-full inline-flex items-center gap-1"
                    style={{ border: "1px solid var(--border)", color: "var(--accent-primary)" }}
                  >
                    {t.followUp} <IconChevronRight size={12} />
                  </button>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        {sending && (
          <div className="text-[12px]" style={{ color: "var(--text-muted)", fontFamily: "var(--font-data)" }}>
            Jarvis is thinking…
          </div>
        )}
      </div>

      {/* Input */}
      <div className="px-4 py-3 flex items-center gap-2" style={{ borderTop: "1px solid var(--border)" }}>
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder={placeholder}
          className="input flex-1 text-sm"
        />
        <button
          onClick={() => send()}
          disabled={!input.trim() || sending}
          className="btn-primary inline-flex items-center px-3 py-2"
          style={{ opacity: !input.trim() || sending ? 0.5 : 1 }}
        >
          <IconSend size={16} />
        </button>
      </div>
    </div>
  );
}

/** Inline action card. Research = synthesis (no approval); others = approval card. */
function ActionCard({ action }: { action: JarvisAction }) {
  const [resolved, setResolved] = useState<null | "approved" | "killed">(null);
  const [expanded, setExpanded] = useState(false);

  if (action.type === "research_result") {
    const p = action.payload;
    return (
      <motion.div variants={slideUp} initial="hidden" animate="visible" className="mt-2 rounded-lg p-3" style={{ background: "var(--bg-elevated)" }}>
        {Array.isArray(p.key_points) && p.key_points.length > 0 && (
          <ul className="space-y-1 mb-2">
            {p.key_points.map((k: string, i: number) => (
              <li key={i} className="text-[12px] flex gap-2" style={{ color: "var(--text-secondary)" }}>
                <span style={{ color: "var(--accent-primary)" }}>•</span> {k}
              </li>
            ))}
          </ul>
        )}
        {Array.isArray(p.sources) && p.sources.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {p.sources.slice(0, 4).map((s: string, i: number) => (
              <a key={i} href={s} target="_blank" rel="noreferrer" className="text-[10px] px-2 py-0.5 rounded"
                style={{ background: "var(--bg-base)", color: "var(--text-muted)", fontFamily: "var(--font-data)" }}>
                {hostname(s)}
              </a>
            ))}
          </div>
        )}
      </motion.div>
    );
  }

  // Approval card (email / schedule / post)
  const meta = ACTION_META[action.type];
  const decide = async (approved: boolean) => {
    const id = action.payload.draft_id as string;
    try {
      if (action.type === "draft_email") await api.decideDraft(id, approved);
      else if (action.type === "schedule_event") await api.decideScheduleDraft(id, approved);
      else if (action.type === "post_draft") await api.decidePostDraft(id, approved);
    } catch {
      /* ignore — optimistic */
    }
    setResolved(approved ? "approved" : "killed");
    pushToast(approved ? `${meta.label} approved (not sent — V1)` : `${meta.label} killed`, approved ? "success" : undefined);
  };

  if (resolved) {
    return (
      <div className="mt-2 text-[12px]" style={{ color: "var(--text-muted)", fontFamily: "var(--font-data)" }}>
        {meta.label} {resolved}.
      </div>
    );
  }

  const p = action.payload;
  return (
    <motion.div variants={slideUp} initial="hidden" animate="visible" className="mt-2 rounded-lg p-3" style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}>
      <div className="flex items-center gap-1.5 mb-1 text-[13px] font-medium" style={{ color: "var(--text-primary)" }}>
        {meta.icon} {meta.label} ready
      </div>
      {p.recipient_hint && <div className="text-[12px]" style={{ color: "var(--text-secondary)" }}>To: {p.recipient_hint}</div>}
      {p.subject_line && <div className="text-[12px]" style={{ color: "var(--text-secondary)" }}>Subject: {p.subject_line}</div>}
      {p.title && <div className="text-[12px]" style={{ color: "var(--text-secondary)" }}>{p.title}{p.proposed_datetime ? ` · ${new Date(p.proposed_datetime).toLocaleString()}` : " · (time TBD)"}</div>}
      <p className="text-[12px] mt-1 leading-snug" style={{ color: "var(--text-muted)" }}>
        {expanded ? (p.draft_content || p.content || p.notes) : (p.draft_content || p.content || p.notes || "").slice(0, 100)}
        {!expanded && (p.draft_content || p.content || p.notes || "").length > 100 ? "…" : ""}
      </p>
      <div className="flex gap-2 mt-2.5">
        <button onClick={() => setExpanded((e) => !e)} className="text-xs py-1 px-2.5 rounded" style={{ border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
          {expanded ? "Collapse" : "View full"}
        </button>
        <button onClick={() => decide(true)} className="btn-primary text-xs py-1 px-2.5 inline-flex items-center gap-1"><IconCheck size={12} /> Approve</button>
        <button onClick={() => decide(false)} className="text-xs py-1 px-2.5 rounded inline-flex items-center gap-1" style={{ border: "1px solid var(--border)", color: "var(--text-muted)" }}><IconX size={12} /> Kill</button>
      </div>
    </motion.div>
  );
}

const ACTION_META: Record<string, { label: string; icon: React.ReactNode }> = {
  draft_email: { label: "Draft", icon: <IconMail size={14} style={{ color: "var(--accent-primary)" }} /> },
  schedule_event: { label: "Event", icon: <IconCalendar size={14} style={{ color: "var(--accent-primary)" }} /> },
  post_draft: { label: "Post", icon: <IconPencil size={14} style={{ color: "var(--accent-primary)" }} /> },
};

function hostname(u: string): string {
  try {
    return new URL(u).hostname.replace(/^www\./, "");
  } catch {
    return u;
  }
}
