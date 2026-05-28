import { useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowUp,
  Plus,
  ChevronDown,
  Sparkles,
  MessageSquare,
  RotateCcw,
  AlertTriangle,
} from "lucide-react";
import { api, type ChatMessage } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { Markdown } from "@/components/chat/Markdown";
import { NeuralTypingIndicator } from "@/components/chat/NeuralTypingIndicator";
import { useTokenReveal } from "@/hooks/useTokenReveal";

type Row = ChatMessage & { error?: boolean };

type Mood = "warm" | "neutral" | "reflective";

/** Lightweight, client-side mood read from the agent's recent replies — a
 * heuristic stand-in until a real memory-derived mood endpoint exists. Positive
 * language → warm, reflective/longer-form → reflective, otherwise neutral. */
function deriveMood(rows: Row[]): Mood {
  const recentAgent = rows.filter((r) => r.role === "agent").slice(-4);
  if (!recentAgent.length) return "neutral";
  const text = recentAgent.map((r) => r.content).join(" ").toLowerCase();
  const warm = /(great|excited|love|glad|nice|win|congrat|happy|awesome|thanks)/.test(text);
  const reflective =
    /(think|reflect|wonder|perhaps|consider|maybe|remember|realize)/.test(text) ||
    text.length / recentAgent.length > 320;
  if (warm) return "warm";
  if (reflective) return "reflective";
  return "neutral";
}

const MOOD_META: Record<Mood, { color: string; label: string }> = {
  warm: { color: "var(--mood-warm)", label: "warm" },
  neutral: { color: "var(--mood-neutral)", label: "neutral" },
  reflective: { color: "var(--mood-reflective)", label: "reflective" },
};

function MoodDot({ mood }: { mood: Mood }) {
  const meta = MOOD_META[mood];
  return (
    <span className="inline-flex items-center gap-1.5" title={`Agent mood: ${meta.label}`}>
      <motion.span
        className="w-2 h-2 rounded-full"
        style={{ background: meta.color, boxShadow: `0 0 8px ${meta.color}` }}
        animate={{ opacity: [0.6, 1, 0.6], scale: [1, 1.15, 1] }}
        transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }}
      />
      <span
        style={{
          fontFamily: "var(--font-data)",
          fontSize: 11,
          color: "var(--text-muted)",
        }}
      >
        {meta.label}
      </span>
    </span>
  );
}

const MODELS = [
  { id: "gemini-2.0-flash", label: "Gemini 2.0 Flash", short: "Flash" },
  { id: "gpt-4o-mini", label: "GPT-4o mini", short: "4o mini" },
  { id: "gpt-4o", label: "GPT-4o", short: "4o" },
];
const MODEL_KEY = "axolot_chat_model";

/** Bucket messages into per-day "conversations" for the history sidebar.
 * A new bucket starts whenever there's a >2h gap between turns OR a new
 * calendar day — close enough to a chat-thread without a schema change. */
function bucketHistory(rows: Row[]): { id: string; title: string; first: Date }[] {
  if (!rows.length) return [];
  const buckets: { id: string; title: string; first: Date; lastTs: number }[] = [];
  for (const r of rows) {
    const t = new Date(r.created_at);
    const ts = t.getTime();
    const last = buckets[buckets.length - 1];
    const newBucket =
      !last ||
      ts - last.lastTs > 2 * 60 * 60 * 1000 ||
      new Date(last.lastTs).toDateString() !== t.toDateString();
    if (newBucket) {
      const title =
        r.role === "user"
          ? r.content.slice(0, 48).replace(/\n/g, " ")
          : "Agent prompt";
      buckets.push({ id: r.id, title, first: t, lastTs: ts });
    } else {
      last.lastTs = ts;
    }
  }
  return buckets.reverse().map(({ id, title, first }) => ({ id, title, first }));
}

/** Blinking cursor shown while an agent reply reveals token-by-token. */
function StreamCursor() {
  return (
    <motion.span
      className="inline-block align-baseline ml-0.5"
      style={{
        width: 2,
        height: "1em",
        background: "var(--accent-electric)",
        transform: "translateY(2px)",
      }}
      animate={{ opacity: [1, 0, 1] }}
      transition={{ duration: 0.9, repeat: Infinity, ease: "linear" }}
    />
  );
}

function Bubble({ row, streaming }: { row: Row; streaming?: string | null }) {
  const isUser = row.role === "user";
  const isStreaming = streaming != null && !isUser && !row.error;
  const ts = new Date(row.created_at).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
  // Human posts: warm white, solid, no glow. Agent posts: frosted glass with a
  // subtle electric-blue glow — the human/agent visual distinction from §10.
  const userStyle = {
    background: "var(--accent-primary)",
    color: "#FFFFFF",
    borderRadius: "16px 16px 4px 16px",
    fontFamily: "var(--font-body)",
  } as const;
  const agentStyle = {
    background: "var(--glass-bg)",
    border: "1px solid var(--glass-border)",
    backdropFilter: "var(--glass-blur)",
    WebkitBackdropFilter: "var(--glass-blur)",
    borderRadius: "16px 16px 16px 4px",
    color: "var(--text-primary)",
    boxShadow: "var(--glow-agent)",
    fontFamily: "var(--font-body)",
  } as const;
  const errorStyle = {
    background: "var(--accent-danger-soft)",
    border: "1px solid var(--accent-danger)",
    borderRadius: "16px 16px 16px 4px",
    color: "var(--accent-danger)",
    fontFamily: "var(--font-body)",
  } as const;
  return (
    <motion.div
      // User messages spring in from the right; agent messages rise gently.
      initial={isUser ? { opacity: 0, x: 24 } : { opacity: 0, y: 12 }}
      animate={isUser ? { opacity: 1, x: 0 } : { opacity: 1, y: 0 }}
      transition={
        isUser
          ? { type: "spring", stiffness: 420, damping: 30 }
          : { duration: 0.25, ease: "easeOut" }
      }
      className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}
    >
      <div
        className="max-w-[78%] px-4 py-2.5 text-[14px] leading-relaxed break-words"
        style={row.error ? errorStyle : isUser ? userStyle : agentStyle}
      >
        {isUser ? (
          <div className="whitespace-pre-wrap">{row.content}</div>
        ) : isStreaming ? (
          <div className="whitespace-pre-wrap">
            {streaming}
            <StreamCursor />
          </div>
        ) : (
          <Markdown source={row.content} />
        )}
      </div>
      <span
        className="mt-1 px-1"
        style={{
          fontFamily: "var(--font-data)",
          fontSize: 11,
          color: "var(--text-muted)",
        }}
      >
        {ts}
      </span>
    </motion.div>
  );
}

export function ChatPage() {
  const { agent } = useAuth();
  const [rows, setRows] = useState<Row[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [model, setModel] = useState<string>(
    () => localStorage.getItem(MODEL_KEY) || MODELS[0].id
  );
  const [modelOpen, setModelOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Last user message kept around so the inline error banner's "Retry"
  // button can resend without making the user retype.
  const [lastSent, setLastSent] = useState<string | null>(null);

  const reveal = useTokenReveal();

  const scrollRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const modelMenuRef = useRef<HTMLDivElement>(null);

  // Close model selector on outside click.
  useEffect(() => {
    if (!modelOpen) return;
    const onDown = (e: MouseEvent) => {
      if (modelMenuRef.current && !modelMenuRef.current.contains(e.target as Node)) {
        setModelOpen(false);
      }
    };
    window.addEventListener("mousedown", onDown);
    return () => window.removeEventListener("mousedown", onDown);
  }, [modelOpen]);

  // Cmd/Ctrl+K toggles the model selector. Escape closes it.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setModelOpen((o) => !o);
      } else if (e.key === "Escape" && modelOpen) {
        setModelOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [modelOpen]);

  useEffect(() => {
    localStorage.setItem(MODEL_KEY, model);
  }, [model]);

  const scrollToBottom = (smooth = true) => {
    // Double rAF so React commits the new node and the browser lays it out
    // before we scroll — a single rAF occasionally scrolled to a stale height.
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const el = scrollRef.current;
        if (!el) return;
        el.scrollTo({
          top: el.scrollHeight,
          behavior: smooth ? "smooth" : "auto",
        });
      });
    });
  };

  useEffect(() => {
    api
      .chatHistory()
      .then((res) => {
        setRows(res.messages);
        scrollToBottom(false);
      })
      .catch(() => setError("Couldn't load chat history."));
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [rows, sending, reveal.text]);

  const autoSize = () => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 22 * 6 + 20)}px`;
  };

  const newChat = () => {
    setRows([]);
    setError(null);
    taRef.current?.focus();
  };

  const sendText = async (text: string, fromRetry: boolean = false) => {
    if (!text || sending) return;
    setError(null);
    setLastSent(text);

    // For a retry, the optimistic row already exists from the first attempt.
    let optimisticId: string | null = null;
    if (!fromRetry) {
      const optimistic: Row = {
        id: `tmp-${Date.now()}`,
        role: "user",
        content: text,
        created_at: new Date().toISOString(),
      };
      optimisticId = optimistic.id;
      setRows((r) => [...r, optimistic]);
    }
    setSending(true);

    try {
      const res = await api.sendChatMessage(text);
      setRows((r) => {
        const swapped = optimisticId
          ? r.map((m) => (m.id === optimisticId ? { ...res.echo, id: optimisticId! } : m))
          : r;
        return swapped.concat(res.reply);
      });
      // Reveal the reply token-by-token (client-side; see useTokenReveal).
      reveal.start(res.reply.id, res.reply.content);
      setLastSent(null);
    } catch {
      // No more synthetic "I couldn't reach the network" agent bubble — that
      // pretended to be a real reply. Instead surface a real error banner
      // with a Retry button below the input.
      setError(
        "Your agent couldn't respond. The backend may be down or the API key isn't configured."
      );
    } finally {
      setSending(false);
      taRef.current?.focus();
    }
  };

  const send = async () => {
    const text = draft.trim();
    if (!text || sending) return;
    setDraft("");
    requestAnimationFrame(autoSize);
    await sendText(text, false);
  };

  const retry = async () => {
    if (!lastSent || sending) return;
    await sendText(lastSent, true);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const history = useMemo(() => bucketHistory(rows), [rows]);
  const mood = useMemo(() => deriveMood(rows), [rows]);
  const activeModel = MODELS.find((m) => m.id === model) || MODELS[0];

  return (
    <div
      className="h-full flex"
      style={{ background: "var(--bg-primary)" }}
    >
      {/* History sidebar (desktop only) */}
      <aside
        className="hidden lg:flex flex-col w-64 shrink-0"
        style={{
          background: "var(--bg-secondary)",
          borderRight: "1px solid var(--border)",
        }}
      >
        <div
          className="px-4 py-3 flex items-center justify-between"
          style={{ borderBottom: "1px solid var(--border)" }}
        >
          <span
            className="text-xs uppercase tracking-wider"
            style={{
              fontFamily: "var(--font-data)",
              color: "var(--text-secondary)",
            }}
          >
            Conversations
          </span>
          <button
            onClick={newChat}
            className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-md transition"
            style={{
              border: "1px solid var(--border)",
              color: "var(--text-primary)",
              fontFamily: "var(--font-body)",
            }}
          >
            <Plus size={12} />
            New
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {history.length === 0 && (
            <div
              className="text-xs px-2 py-4"
              style={{ color: "var(--text-muted)", fontFamily: "var(--font-body)" }}
            >
              No past conversations yet.
            </div>
          )}
          {history.map((h) => (
            <div
              key={h.id}
              className="px-2.5 py-2 rounded-md cursor-default mb-0.5"
              style={{ color: "var(--text-primary)" }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = "var(--bg-tertiary)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = "transparent")
              }
            >
              <div
                className="text-[13px] truncate"
                style={{ fontFamily: "var(--font-body)" }}
              >
                {h.title || "Untitled"}
              </div>
              <div
                className="text-[11px] mt-0.5"
                style={{
                  color: "var(--text-muted)",
                  fontFamily: "var(--font-data)",
                }}
              >
                {h.first.toLocaleDateString([], {
                  month: "short",
                  day: "numeric",
                })}
                {" · "}
                {h.first.toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </div>
            </div>
          ))}
        </div>
      </aside>

      {/* Chat column */}
      <div className="flex-1 min-w-0 flex flex-col">
        {/* Header */}
        <div
          className="flex items-center justify-between px-6 py-3 shrink-0"
          style={{
            background: "var(--bg-secondary)",
            borderBottom: "1px solid var(--border)",
          }}
        >
          <div className="flex items-center gap-3">
            <span
              className="inline-flex w-9 h-9 items-center justify-center rounded-full"
              style={{
                background: "var(--accent-primary-soft)",
                color: "var(--accent-primary)",
              }}
            >
              <Sparkles size={16} />
            </span>
            <div>
              <div
                className="text-sm font-medium"
                style={{
                  fontFamily: "var(--font-body)",
                  color: "var(--text-primary)",
                }}
              >
                {agent?.name || "Your Agent"}
              </div>
              <div className="flex items-center gap-2">
                <span
                  style={{
                    fontFamily: "var(--font-data)",
                    fontSize: 11,
                    color: sending ? "var(--accent-gold)" : "var(--accent-green)",
                  }}
                >
                  {sending ? "Thinking…" : "Online · mirrors your voice"}
                </span>
                {!sending && rows.some((r) => r.role === "agent") && (
                  <>
                    <span style={{ color: "var(--text-tertiary)", fontSize: 11 }}>·</span>
                    <MoodDot mood={mood} />
                  </>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Model selector */}
            <div className="relative" ref={modelMenuRef}>
              <button
                onClick={() => setModelOpen((o) => !o)}
                className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-md transition"
                style={{
                  border: "1px solid var(--border)",
                  background: "var(--bg-secondary)",
                  color: "var(--text-primary)",
                  fontFamily: "var(--font-body)",
                }}
              >
                <span
                  className="w-1.5 h-1.5 rounded-full"
                  style={{ background: "var(--accent-primary)" }}
                />
                {activeModel.label}
                <kbd
                  className="ml-1 px-1 py-px rounded text-[9px]"
                  style={{
                    background: "var(--bg-tertiary)",
                    border: "1px solid var(--border)",
                    color: "var(--text-muted)",
                    fontFamily: "var(--font-data)",
                  }}
                >
                  ⌘K
                </kbd>
                <ChevronDown size={12} />
              </button>
              {modelOpen && (
                <div
                  className="absolute right-0 mt-1 z-30 rounded-md overflow-hidden"
                  style={{
                    background: "var(--bg-secondary)",
                    border: "1px solid var(--border)",
                    boxShadow: "var(--shadow-lg)",
                    minWidth: 200,
                  }}
                >
                  {MODELS.map((m) => (
                    <button
                      key={m.id}
                      onClick={() => {
                        setModel(m.id);
                        setModelOpen(false);
                      }}
                      className="w-full text-left px-3 py-2 text-xs transition flex items-center justify-between"
                      style={{
                        background:
                          m.id === model ? "var(--accent-primary-soft)" : "transparent",
                        color: "var(--text-primary)",
                        fontFamily: "var(--font-body)",
                      }}
                      onMouseEnter={(e) => {
                        if (m.id !== model)
                          e.currentTarget.style.background = "var(--bg-tertiary)";
                      }}
                      onMouseLeave={(e) => {
                        if (m.id !== model)
                          e.currentTarget.style.background = "transparent";
                      }}
                    >
                      {m.label}
                      {m.id === model && (
                        <span
                          className="text-[10px]"
                          style={{ color: "var(--accent-primary)" }}
                        >
                          ●
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Messages */}
        <div
          ref={scrollRef}
          className="flex-1 min-h-0 overflow-y-auto flex flex-col gap-4"
          style={{ padding: 24, background: "var(--bg-primary)" }}
        >
          {rows.length === 0 && !sending && (
            <div
              className="m-auto text-center max-w-md"
              style={{ color: "var(--text-secondary)" }}
            >
              <div className="mb-4 flex justify-center">
                <span
                  className="inline-flex w-14 h-14 items-center justify-center rounded-full"
                  style={{
                    background: "var(--accent-primary-soft)",
                    color: "var(--accent-primary)",
                  }}
                >
                  <MessageSquare size={22} />
                </span>
              </div>
              <div
                className="text-lg mb-2"
                style={{
                  fontFamily: "var(--font-display)",
                  color: "var(--text-primary)",
                }}
              >
                Talk to {agent?.name || "your agent"}
              </div>
              <p style={{ fontFamily: "var(--font-body)", fontSize: 14 }}>
                It remembers your past messages and mirrors how you write.
                The more you talk to it, the more it sounds like you.
              </p>
            </div>
          )}
          <AnimatePresence initial={false}>
            {rows.map((row) => (
              <Bubble
                key={row.id}
                row={row}
                streaming={reveal.activeId === row.id ? reveal.text : null}
              />
            ))}
          </AnimatePresence>
          {sending && (
            <div className="flex items-start">
              <div
                className="px-3 py-1"
                style={{
                  background: "var(--glass-bg)",
                  border: "1px solid var(--glass-border)",
                  backdropFilter: "var(--glass-blur)",
                  WebkitBackdropFilter: "var(--glass-blur)",
                  borderRadius: "16px 16px 16px 4px",
                  boxShadow: "var(--glow-agent)",
                }}
              >
                <NeuralTypingIndicator />
              </div>
            </div>
          )}
        </div>

        {/* Inline error banner with Retry — shown below the last message,
            above the input. The agent never lies about "I couldn't reach the
            network" any more; failures surface here and the user can resend
            with one click. */}
        {error && (
          <div
            className="mx-6 mb-2 mt-1 px-3 py-2.5 flex items-center justify-between gap-3 rounded-md"
            style={{
              background: "var(--accent-danger-soft)",
              border: "1px solid var(--accent-danger)",
              color: "var(--accent-danger)",
              fontFamily: "var(--font-body)",
            }}
          >
            <div className="flex items-center gap-2 min-w-0">
              <AlertTriangle size={14} className="shrink-0" />
              <span className="text-[13px] truncate">{error}</span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {lastSent && (
                <button
                  onClick={retry}
                  disabled={sending}
                  className="inline-flex items-center gap-1 text-[12px] px-2 py-1 rounded"
                  style={{
                    background: "var(--accent-danger)",
                    color: "#FFFFFF",
                    fontFamily: "var(--font-body)",
                  }}
                >
                  <RotateCcw size={11} />
                  Retry
                </button>
              )}
              <button
                onClick={() => setError(null)}
                className="text-[12px] underline opacity-80 hover:opacity-100"
                style={{ color: "var(--accent-danger)" }}
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        {/* Input */}
        <div
          className="shrink-0 flex items-end gap-3 px-4 py-3"
          style={{
            background: "var(--bg-secondary)",
            borderTop: "1px solid var(--border)",
          }}
        >
          <div
            className="flex-1 flex items-end px-3 py-2"
            style={{
              background: "var(--bg-elevated)",
              border: "1px solid var(--border-default)",
              borderRadius: 8,
              transition: "border-color 120ms ease",
            }}
            onFocusCapture={(e) => {
              e.currentTarget.style.borderColor = "var(--border-strong)";
            }}
            onBlurCapture={(e) => {
              e.currentTarget.style.borderColor = "var(--border-default)";
            }}
          >
            <textarea
              ref={taRef}
              rows={1}
              value={draft}
              onChange={(e) => {
                setDraft(e.target.value);
                autoSize();
              }}
              onKeyDown={onKeyDown}
              placeholder={`Message ${agent?.name || "your agent"}…`}
              className="flex-1 bg-transparent outline-none resize-none text-[14px] leading-[22px]"
              style={{
                color: "var(--text-primary)",
                fontFamily: "var(--font-body)",
                maxHeight: 22 * 6 + 20,
              }}
            />
          </div>

          <button
            type="button"
            onClick={send}
            disabled={!draft.trim() || sending}
            className="shrink-0 h-10 w-10 flex items-center justify-center rounded-lg transition"
            style={{
              background:
                !draft.trim() || sending
                  ? "var(--bg-tertiary)"
                  : "var(--accent-primary)",
              color:
                !draft.trim() || sending
                  ? "var(--text-muted)"
                  : "#FFFFFF",
              cursor: !draft.trim() || sending ? "not-allowed" : "pointer",
              border: "1px solid var(--border)",
            }}
            aria-label="Send message"
          >
            <ArrowUp size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}
