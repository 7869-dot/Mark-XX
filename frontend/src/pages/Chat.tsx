import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Paperclip, ArrowUp } from "lucide-react";
import { api, type ChatMessage } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { AgentOrb } from "@/components/agent/AgentOrb";

type Row = ChatMessage & { error?: boolean };

function TypingDots() {
  return (
    <div className="flex gap-1.5 px-1 py-2" aria-label="agent is typing">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="w-1.5 h-1.5 rounded-full"
          style={{ background: "var(--teal-bright)" }}
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
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: "easeOut" }}
      className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}
    >
      <div
        className="max-w-[78%] px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words"
        style={
          row.error
            ? {
                background: "var(--coral-dim)",
                border: "1px solid rgba(255,112,67,0.4)",
                borderRadius: "16px 16px 16px 4px",
                color: "var(--coral-bright)",
                fontFamily: "var(--font-body)",
              }
            : isUser
            ? {
                background: "var(--teal-dim)",
                borderRadius: "16px 16px 4px 16px",
                color: "var(--text-primary)",
                fontFamily: "var(--font-body)",
              }
            : {
                background: "var(--bg-elevated)",
                border: "1px solid var(--border-default)",
                borderRadius: "16px 16px 16px 4px",
                color: "var(--text-primary)",
                fontFamily: "var(--font-body)",
              }
        }
      >
        {row.content}
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
  const scrollRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = (smooth = true) => {
    // Double rAF: the first frame lets React commit the new message node, the
    // second lets the browser lay it out — so scrollHeight is final before we
    // scroll. A single rAF occasionally scrolled to a stale (short) height and
    // stopped above the latest message.
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
      .catch(() => {});
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [rows, sending]);

  const autoSize = () => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    // ~22px line-height, cap at 4 lines.
    ta.style.height = `${Math.min(ta.scrollHeight, 22 * 4 + 20)}px`;
  };

  const send = async () => {
    const text = draft.trim();
    if (!text || sending) return;
    setDraft("");
    requestAnimationFrame(autoSize);
    const optimistic: Row = {
      id: `tmp-${Date.now()}`,
      role: "user",
      content: text,
      created_at: new Date().toISOString(),
    };
    setRows((r) => [...r, optimistic]);
    setSending(true);
    try {
      const res = await api.sendChatMessage(text);
      // Keep the optimistic row's id when swapping in the server echo. The
      // AnimatePresence key is the row id — letting it change from `tmp-…` to
      // the real UUID re-mounted the bubble, causing a visible exit/enter
      // flicker on every send. Stable id = no flicker.
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

  const statusText = sending ? "Online · Thinking..." : "Online · Ready";

  return (
    <div className="flex flex-col h-full">
      {/* Agent header */}
      <div
        className="flex items-center gap-3 px-6 py-3 shrink-0"
        style={{ borderBottom: "1px solid var(--border-subtle)" }}
      >
        <AgentOrb state={sending ? "thinking" : "idle"} size={36} />
        <div>
          <div
            className="text-sm"
            style={{
              fontFamily: "var(--font-display)",
              color: "var(--text-primary)",
            }}
          >
            {agent?.name || "Your Agent"}
          </div>
          <div
            style={{
              fontFamily: "var(--font-data)",
              fontSize: 12,
              color: "var(--teal-bright)",
            }}
          >
            {statusText}
          </div>
        </div>
      </div>

      {/* Messages */}
      <div
        ref={scrollRef}
        className="flex-1 min-h-0 overflow-y-auto flex flex-col gap-4"
        style={{ padding: 24 }}
      >
        {rows.length === 0 && !sending && (
          <div
            className="m-auto text-center max-w-sm"
            style={{ color: "var(--text-muted)", fontFamily: "var(--font-data)" }}
          >
            <div className="mb-3 flex justify-center">
              <AgentOrb state="idle" size={56} />
            </div>
            Say hello to {agent?.name || "your agent"}. It remembers everything
            you tell it.
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
                background: "var(--bg-elevated)",
                border: "1px solid var(--border-default)",
                borderRadius: "16px 16px 16px 4px",
              }}
            >
              <TypingDots />
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div
        className="shrink-0 flex items-end gap-3 px-4"
        style={{
          minHeight: 72,
          background: "var(--bg-surface)",
          borderTop: "1px solid var(--border-subtle)",
          paddingTop: 12,
          paddingBottom: 12,
        }}
      >
        <button
          type="button"
          disabled
          title="Attachments coming soon"
          className="shrink-0 h-10 w-10 flex items-center justify-center rounded-lg"
          style={{
            color: "var(--text-muted)",
            border: "1px solid var(--border-subtle)",
            opacity: 0.5,
            cursor: "not-allowed",
          }}
        >
          <Paperclip size={16} />
        </button>

        <div
          className="flex-1 flex items-end px-3 py-2"
          style={{
            background: "var(--bg-elevated)",
            border: "1px solid var(--border-default)",
            borderRadius: 12,
          }}
          onFocusCapture={(e) =>
            (e.currentTarget.style.borderColor = "var(--border-active)")
          }
          onBlurCapture={(e) =>
            (e.currentTarget.style.borderColor = "var(--border-default)")
          }
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
            placeholder="Message your agent…"
            className="flex-1 bg-transparent outline-none resize-none text-sm leading-[22px]"
            style={{
              color: "var(--text-primary)",
              fontFamily: "var(--font-body)",
              maxHeight: 22 * 4 + 20,
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
                ? "var(--bg-overlay)"
                : "var(--teal-mid)",
            color:
              !draft.trim() || sending
                ? "var(--text-muted)"
                : "var(--bg-void)",
            cursor: !draft.trim() || sending ? "not-allowed" : "pointer",
          }}
        >
          <ArrowUp size={18} />
        </button>
      </div>
    </div>
  );
}
