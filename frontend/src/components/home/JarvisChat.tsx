import { useEffect, useRef, useState, type ReactNode } from "react";
import { IconSend, IconArrowRight } from "@tabler/icons-react";
import { api, type AgentDraft, type JarvisAction } from "@/lib/api";
import { Markdown } from "@/components/chat/Markdown";
import type { PanelTab } from "./AgentPanel";

export type ChatPrefill = { text: string; nonce: number; draftId?: string };

type Turn = {
  id: string;
  role: "user" | "jarvis";
  text: string;
  panelHint?: PanelTab | null;
};

function panelHintFor(action: JarvisAction | null, reply: string, delegated?: string | null): PanelTab | null {
  if (delegated === "web") return "web";
  if (delegated === "email") return "emails";
  if (action?.type === "draft_email") return "emails";
  if (action?.type === "research_result") return "web";
  const r = reply.toLowerCase();
  if (/\b(email|inbox|draft|repl(y|ies))\b/.test(r)) return "emails";
  if (/\b(web|news|research|article|found|sources?)\b/.test(r)) return "web";
  return null;
}

export function JarvisChat({
  briefingSlot,
  prefill,
  onSwitchTab,
  onDraftRevised,
  onDraftCreated,
}: {
  briefingSlot: ReactNode;
  prefill?: ChatPrefill;
  onSwitchTab: (t: PanelTab) => void;
  onDraftRevised: (draftId: string, content: string) => void;
  onDraftCreated: (draft: AgentDraft) => void;
}) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [slow, setSlow] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const contextDraftId = useRef<string | undefined>(undefined);

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
      // mode=auto → Jarvis classifies the task and delegates to a sub-agent.
      const r = await api.jarvisChat(text, "auto", ctx);
      // Reflect any email draft Jarvis produced into the Emails panel.
      if (r.action?.type === "draft_email") {
        const content = (r.action.payload?.draft_content as string) || "";
        if (draftId && content) {
          onDraftRevised(draftId, content); // revision of an existing draft
        } else if (content) {
          onDraftCreated({
            id: String(r.action.payload?.draft_id ?? crypto.randomUUID()),
            task_id: null,
            agent_role: "email",
            subject_line: String(r.action.payload?.subject_line ?? ""),
            recipient_hint: String(r.action.payload?.recipient_hint ?? ""),
            draft_content: content,
            requires_approval: true,
            approved: null,
            created_at: new Date().toISOString(),
          });
        }
      }
      setTurns((t) => [
        ...t,
        {
          id: crypto.randomUUID(),
          role: "jarvis",
          text: r.reply,
          panelHint: panelHintFor(r.action, r.reply, r.delegated_to),
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
    <div className="axo-jarvis-pane">
      <div className="axo-briefing-area" ref={scrollRef}>
        <div className="axo-jarvis-header">
          <div className="axo-jarvis-avatar">J</div>
          <span className="axo-jarvis-name">Jarvis · just now</span>
        </div>

        {briefingSlot}

        {turns.map((t) => (
          <div key={t.id} className={`axo-turn ${t.role}`}>
            <div>
              <div className={`axo-bubble ${t.role}`}>
                {t.role === "jarvis" ? <Markdown source={t.text} /> : t.text}
              </div>
              {t.panelHint && (
                <button className="axo-see-panel" onClick={() => onSwitchTab(t.panelHint!)}>
                  → see {t.panelHint === "emails" ? "Emails" : "Web"} <IconArrowRight size={12} />
                </button>
              )}
            </div>
          </div>
        ))}

        {sending && (
          <div className="axo-thinking">
            {slow ? "Still working on it — this is taking longer than usual…" : "Jarvis is thinking…"}
          </div>
        )}
      </div>

      <div className="axo-chat-input-wrap">
        <input
          ref={inputRef}
          className="axo-chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Tell Jarvis what to do…"
        />
        <button className="axo-chat-send" onClick={send} disabled={!input.trim() || sending} aria-label="Send">
          <IconSend size={15} />
        </button>
      </div>
    </div>
  );
}
