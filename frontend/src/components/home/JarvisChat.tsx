import { useEffect, useRef, useState } from "react";
import { IconSend, IconArrowRight } from "@tabler/icons-react";
import { api, type JarvisAction } from "@/lib/api";
import { Markdown } from "@/components/chat/Markdown";
import type { PanelTab } from "./AgentPanel";

export type ChatPrefill = { text: string; nonce: number; draftId?: string };

type Turn = {
  id: string;
  role: "user" | "jarvis";
  text: string;
  panelHint?: PanelTab | null;
};

/** Which panel an action/reply points the user toward, for the "see panel" link. */
function panelHintFor(action: JarvisAction | null, reply: string): PanelTab | null {
  if (action?.type === "draft_email") return "emails";
  if (action?.type === "research_result") return "web";
  const r = reply.toLowerCase();
  if (/\b(email|inbox|draft|repl(y|ies))\b/.test(r)) return "emails";
  if (/\b(web|news|research|article|found|sources?)\b/.test(r)) return "web";
  return null;
}

export function JarvisChat({
  greeting,
  prefill,
  onSwitchTab,
  onDraftRevised,
}: {
  greeting: string;
  prefill?: ChatPrefill;
  onSwitchTab: (t: PanelTab) => void;
  onDraftRevised: (draftId: string, content: string) => void;
}) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [slow, setSlow] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const contextDraftId = useRef<string | undefined>(undefined);

  // Ask-Jarvis prefill from an email card → fill input, focus, remember context.
  useEffect(() => {
    if (prefill) {
      setInput(prefill.text);
      contextDraftId.current = prefill.draftId;
      inputRef.current?.focus();
    }
  }, [prefill]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, sending]);

  const send = async () => {
    const text = input.trim();
    if (!text || sending) return;
    const draftId = contextDraftId.current;
    contextDraftId.current = undefined;
    setInput("");
    setSending(true);
    setSlow(false);
    const slowTimer = setTimeout(() => setSlow(true), 15000);
    setTurns((t) => [...t, { id: crypto.randomUUID(), role: "user", text }]);
    try {
      const ctx = draftId ? { draft_id: draftId } : undefined;
      const r = await api.jarvisChat(text, "default", ctx);
      // If Jarvis revised a draft, push the new text back to the email card.
      if (draftId && r.action?.type === "draft_email") {
        const revised = (r.action.payload?.draft_content as string) || "";
        if (revised) onDraftRevised(draftId, revised);
      }
      setTurns((t) => [
        ...t,
        {
          id: crypto.randomUUID(),
          role: "jarvis",
          text: r.reply,
          panelHint: panelHintFor(r.action, r.reply),
        },
      ]);
    } catch {
      setTurns((t) => [
        ...t,
        { id: crypto.randomUUID(), role: "jarvis", text: "Something glitched — try that again?" },
      ]);
    } finally {
      clearTimeout(slowTimer);
      setSending(false);
      setSlow(false);
      inputRef.current?.focus();
    }
  };

  return (
    <div className="flex flex-col h-full min-h-0" style={{ background: "var(--bg-base)" }}>
      <div ref={scrollRef} className="flex-1 min-h-0 overflow-y-auto px-4 py-5 space-y-4">
        {/* Pinned greeting / briefing */}
        <div className="flex justify-start">
          <div
            className="max-w-[85%] rounded-2xl px-4 py-3 text-[14px]"
            style={{ background: "var(--bg-surface)", color: "var(--text-primary)" }}
          >
            <Markdown source={greeting} />
          </div>
        </div>

        {turns.map((t) => (
          <div key={t.id} className={`flex ${t.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className="max-w-[85%]">
              <div
                className="rounded-2xl px-4 py-2.5 text-[14px] leading-relaxed"
                style={
                  t.role === "user"
                    ? { background: "var(--accent-primary)", color: "#fff" }
                    : { background: "var(--bg-surface)", color: "var(--text-primary)" }
                }
              >
                {t.role === "jarvis" ? <Markdown source={t.text} /> : t.text}
              </div>
              {t.panelHint && (
                <button
                  onClick={() => onSwitchTab(t.panelHint!)}
                  className="mt-1.5 text-[12px] inline-flex items-center gap-1"
                  style={{ color: "var(--accent-primary)" }}
                >
                  → see {t.panelHint === "emails" ? "Emails" : "Web Intel"}
                  <IconArrowRight size={12} />
                </button>
              )}
            </div>
          </div>
        ))}

        {sending && (
          <div className="flex items-center gap-2">
            <span
              className="text-[12px] animate-pulse"
              style={{ color: "var(--text-secondary)", fontFamily: "var(--font-data)" }}
            >
              {slow ? "Still working on it — this is taking longer than usual…" : "Jarvis is thinking…"}
            </span>
          </div>
        )}
      </div>

      <div
        className="px-4 py-3 flex items-center gap-2 shrink-0"
        style={{ borderTop: "1px solid var(--border)" }}
      >
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Talk to Jarvis…"
          className="input flex-1 text-sm"
        />
        <button
          onClick={send}
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
