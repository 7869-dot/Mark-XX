import { useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowUp,
  Plus,
  ChevronDown,
  Beaker,
  Sparkles,
  MessageSquare,
} from "lucide-react";
import { api, type ChatMessage } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { Markdown } from "@/components/chat/Markdown";

type Row = ChatMessage & { error?: boolean };

const MODELS = [
  { id: "gemini-1.5-flash", label: "Gemini 1.5 Flash", short: "Flash" },
  { id: "gemini-1.5-pro", label: "Gemini 1.5 Pro", short: "Pro" },
  { id: "gpt-4o-mini", label: "GPT-4o mini", short: "4o mini" },
  { id: "gpt-4o", label: "GPT-4o", short: "4o" },
];
const MODEL_KEY = "axolot_chat_model";
const STUB_KEY = "axolot_chat_stub";

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

function TypingDots() {
  return (
    <div className="flex gap-1.5 px-1 py-2" aria-label="agent is typing">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="w-1.5 h-1.5 rounded-full"
          style={{ background: "var(--accent-primary)" }}
          animate={{ opacity: [0.3, 1, 0.3], y: [0, -3, 0] }}
          transition={{
            duration: 1,
            repeat: Infinity,
            delay: i * 0.15,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  );
}

function Bubble({ row }: { row: Row }) {
  const isUser = row.role === "user";
  const ts = new Date(row.created_at).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
  const userStyle = {
    background: "var(--accent-primary)",
    color: "#FFFFFF",
    borderRadius: "16px 16px 4px 16px",
    fontFamily: "var(--font-body)",
  } as const;
  const agentStyle = {
    background: "var(--bg-secondary)",
    border: "1px solid var(--border)",
    borderRadius: "16px 16px 16px 4px",
    color: "var(--text-primary)",
    fontFamily: "var(--font-body)",
    boxShadow: "var(--shadow-sm)",
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
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
      className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}
    >
      <div
        className="max-w-[78%] px-4 py-2.5 text-[14px] leading-relaxed break-words"
        style={row.error ? errorStyle : isUser ? userStyle : agentStyle}
      >
        {isUser ? (
          <div className="whitespace-pre-wrap">{row.content}</div>
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

/** Stubbed responses for the local STUB MODE — lets the UI be iterated on
 * without burning Gemini quota when the live agent is misbehaving. */
const STUB_REPLIES = [
  "Got it. Here's how I'd break that down:\n\n- **Step 1:** Frame the goal in one sentence.\n- **Step 2:** Pick the smallest test that proves it out.\n- **Step 3:** Set a deadline you'll actually hit.\n\nWhich one's blocking you right now?",
  "Honestly — that sounds like something you'd want to sleep on for a night. The version I'd ship today is probably 80% of the version you'd ship next week, but the missing 20% is the only part that matters. Worth waiting.",
  "Quick read: this is a *distribution* problem dressed up as a product problem. The thing you're building is fine. The thing you haven't built is the channel.",
  "Here's a draft you can edit:\n\n> Hi — quick note. I've been thinking about the conversation we started on Tuesday and I have a clearer answer now. Want to grab 15 minutes Thursday?",
  "I checked the notes from our last few threads — the pattern is that you keep deferring the boring parts of this. If we keep doing that, the deadline becomes the decision.",
];

export function ChatPage() {
  const { agent } = useAuth();
  const [rows, setRows] = useState<Row[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [model, setModel] = useState<string>(
    () => localStorage.getItem(MODEL_KEY) || MODELS[0].id
  );
  const [modelOpen, setModelOpen] = useState(false);
  const [stubMode, setStubMode] = useState<boolean>(
    () => localStorage.getItem(STUB_KEY) === "1"
  );
  const [error, setError] = useState<string | null>(null);

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
  useEffect(() => {
    localStorage.setItem(STUB_KEY, stubMode ? "1" : "0");
  }, [stubMode]);

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
  }, [rows, sending]);

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

  const send = async () => {
    const text = draft.trim();
    if (!text || sending) return;
    setDraft("");
    setError(null);
    requestAnimationFrame(autoSize);

    const optimistic: Row = {
      id: `tmp-${Date.now()}`,
      role: "user",
      content: text,
      created_at: new Date().toISOString(),
    };
    setRows((r) => [...r, optimistic]);
    setSending(true);

    if (stubMode) {
      // Local stub — no network call. Simulates the UX for design iteration.
      await new Promise((r) => setTimeout(r, 600 + Math.random() * 500));
      const reply: Row = {
        id: `stub-${Date.now()}`,
        role: "agent",
        content: STUB_REPLIES[Math.floor(Math.random() * STUB_REPLIES.length)],
        created_at: new Date().toISOString(),
      };
      setRows((r) => [...r, reply]);
      setSending(false);
      taRef.current?.focus();
      return;
    }

    try {
      const res = await api.sendChatMessage(text);
      setRows((r) =>
        r
          .map((m) =>
            m.id === optimistic.id ? { ...res.echo, id: optimistic.id } : m
          )
          .concat(res.reply)
      );
    } catch {
      setRows((r) => [
        ...r,
        {
          id: `err-${Date.now()}`,
          role: "agent",
          content:
            "I couldn't reach the network just now. Check your connection and try again.",
          created_at: new Date().toISOString(),
          error: true,
        },
      ]);
      setError("Network error — message not delivered.");
    } finally {
      setSending(false);
      taRef.current?.focus();
    }
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const history = useMemo(() => bucketHistory(rows), [rows]);
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
              <div
                style={{
                  fontFamily: "var(--font-data)",
                  fontSize: 11,
                  color: sending ? "var(--accent-secondary)" : "var(--accent-success)",
                }}
              >
                {sending ? "Thinking…" : "Online · mirrors your voice"}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {stubMode && (
              <span
                className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-[10px] uppercase tracking-wider"
                style={{
                  background: "var(--accent-secondary-soft)",
                  color: "#8A6810",
                  border: "1px solid var(--accent-secondary)",
                  fontFamily: "var(--font-data)",
                  fontWeight: 600,
                }}
                title="Local stub mode — no API calls"
              >
                <Beaker size={11} /> Stub mode
              </span>
            )}
            <button
              onClick={() => setStubMode((s) => !s)}
              className="text-[11px] px-2 py-1 rounded-md transition"
              style={{
                border: "1px solid var(--border)",
                color: "var(--text-secondary)",
                fontFamily: "var(--font-body)",
              }}
              title="Toggle local stub responses"
            >
              {stubMode ? "Disable stubs" : "Stubs"}
            </button>

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
              <Bubble key={row.id} row={row} />
            ))}
          </AnimatePresence>
          {sending && (
            <div className="flex items-start">
              <div
                className="px-3"
                style={{
                  background: "var(--bg-secondary)",
                  border: "1px solid var(--border)",
                  borderRadius: "16px 16px 16px 4px",
                  boxShadow: "var(--shadow-sm)",
                }}
              >
                <TypingDots />
              </div>
            </div>
          )}
        </div>

        {/* Error banner */}
        {error && (
          <div
            className="px-6 py-2 text-xs flex items-center justify-between"
            style={{
              background: "var(--accent-danger-soft)",
              color: "var(--accent-danger)",
              borderTop: "1px solid var(--accent-danger)",
            }}
          >
            <span>{error}</span>
            <button
              onClick={() => setError(null)}
              className="underline"
              style={{ color: "var(--accent-danger)" }}
            >
              Dismiss
            </button>
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
              background: "var(--bg-primary)",
              border: "1px solid var(--border)",
              borderRadius: 12,
              transition: "border-color 120ms ease, box-shadow 120ms ease",
            }}
            onFocusCapture={(e) => {
              e.currentTarget.style.borderColor = "var(--accent-primary)";
              e.currentTarget.style.boxShadow = "0 0 0 3px var(--accent-primary-soft)";
            }}
            onBlurCapture={(e) => {
              e.currentTarget.style.borderColor = "var(--border)";
              e.currentTarget.style.boxShadow = "none";
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
