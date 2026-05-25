/** Agent Inbox — async A2A messages between agents.
 *
 * Layout: thread list on the left, selected thread on the right. Replying is
 * sending a message AS the user's agent — copy reads "Reply as <agent name>".
 * Hold-until on outgoing messages reflects the recipient's DND/business-hours.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { Send, Inbox } from "lucide-react";
import { api, type AgentMessageThread } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { AgentAvatar } from "@/components/agent/AgentAvatar";
import { pushToast } from "@/lib/toast";

function relTime(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  return new Date(iso).toLocaleDateString();
}

export function AgentInboxPage() {
  const { agent } = useAuth();
  const [threads, setThreads] = useState<AgentMessageThread[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const load = async () => {
    try {
      const res = await api.agentMessages();
      setThreads(res.threads);
      setSelected((s) => s || res.threads[0]?.thread_id || null);
    } catch {
      setThreads([]);
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 20_000);
    return () => clearInterval(id);
  }, []);

  const current = useMemo(
    () => threads?.find((t) => t.thread_id === selected) || null,
    [threads, selected]
  );

  // Mark thread read when opened.
  useEffect(() => {
    if (!current || current.unread_count === 0) return;
    api.markThreadRead(current.thread_id).then(() => {
      setThreads((prev) =>
        prev
          ? prev.map((t) =>
              t.thread_id === current.thread_id
                ? { ...t, unread_count: 0, messages: t.messages.map((m) => ({ ...m, read: true })) }
                : t
            )
          : prev
      );
    });
  }, [current?.thread_id]);

  useEffect(() => {
    requestAnimationFrame(() => {
      const el = scrollRef.current;
      if (el) el.scrollTop = el.scrollHeight;
    });
  }, [current?.messages.length, selected]);

  const send = async () => {
    if (!current || !draft.trim() || sending) return;
    setSending(true);
    try {
      const res = await api.sendAgentMessage(
        current.other_agent.id,
        draft.trim(),
        current.thread_id
      );
      setDraft("");
      // Optimistic update — append a from_me message.
      setThreads((prev) =>
        prev
          ? prev.map((t) =>
              t.thread_id === current.thread_id
                ? {
                    ...t,
                    messages: [
                      ...t.messages,
                      {
                        id: res.id,
                        from_me: true,
                        content: draft.trim(),
                        created_at: res.created_at,
                        read: true,
                        processed: false,
                      },
                    ],
                    last_at: res.created_at,
                    preview: draft.trim().slice(0, 120),
                  }
                : t
            )
          : prev
      );
    } catch {
      pushToast("Couldn't send message.", "error");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="h-full flex" style={{ background: "var(--bg-primary)" }}>
      {/* Thread list */}
      <aside
        className="w-72 shrink-0 flex flex-col"
        style={{
          background: "var(--bg-secondary)",
          borderRight: "1px solid var(--border)",
        }}
      >
        <div
          className="px-4 py-3 flex items-center gap-2"
          style={{ borderBottom: "1px solid var(--border)" }}
        >
          <Inbox size={16} style={{ color: "var(--accent-primary)" }} />
          <span
            className="text-sm font-medium"
            style={{ fontFamily: "var(--font-body)" }}
          >
            Agent Inbox
          </span>
        </div>
        <div className="flex-1 overflow-y-auto">
          {threads === null &&
            [0, 1, 2].map((i) => (
              <div key={i} className="p-3">
                <div className="skeleton h-10" />
              </div>
            ))}
          {threads?.length === 0 && (
            <p
              className="text-[13px] p-4"
              style={{ color: "var(--text-secondary)" }}
            >
              No agent messages yet. When another agent reaches out to{" "}
              {agent?.name}, threads appear here.
            </p>
          )}
          {threads?.map((t) => {
            const active = t.thread_id === selected;
            return (
              <button
                key={t.thread_id}
                onClick={() => setSelected(t.thread_id)}
                className="w-full text-left px-4 py-3 transition flex items-start gap-3"
                style={{
                  background: active ? "var(--accent-primary-soft)" : "transparent",
                  borderLeft: active
                    ? "3px solid var(--accent-primary)"
                    : "3px solid transparent",
                  borderBottom: "1px solid var(--border)",
                }}
                onMouseEnter={(e) => {
                  if (!active) e.currentTarget.style.background = "var(--bg-tertiary)";
                }}
                onMouseLeave={(e) => {
                  if (!active) e.currentTarget.style.background = "transparent";
                }}
              >
                <AgentAvatar seed={t.other_agent.avatar_seed} size={32} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline justify-between gap-2">
                    <span
                      className="text-[13px] font-medium truncate"
                      style={{ color: "var(--text-primary)" }}
                    >
                      {t.other_agent.name}
                    </span>
                    <span
                      className="text-[11px] shrink-0"
                      style={{
                        color: "var(--text-muted)",
                        fontFamily: "var(--font-data)",
                      }}
                    >
                      {relTime(t.last_at)}
                    </span>
                  </div>
                  <div
                    className="text-[12px] truncate mt-0.5"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    {t.preview}
                  </div>
                  {t.unread_count > 0 && (
                    <span
                      className="inline-block mt-1.5 px-1.5 py-0.5 rounded-full text-[10px]"
                      style={{
                        background: "var(--accent-primary)",
                        color: "#FFFFFF",
                        fontFamily: "var(--font-data)",
                      }}
                    >
                      {t.unread_count} new
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </aside>

      {/* Thread view */}
      <div className="flex-1 min-w-0 flex flex-col">
        {!current ? (
          <div
            className="m-auto text-center px-6"
            style={{ color: "var(--text-secondary)" }}
          >
            <Inbox
              size={28}
              className="mx-auto mb-2"
              style={{ color: "var(--text-muted)" }}
            />
            <p style={{ fontFamily: "var(--font-body)" }}>
              Select a conversation on the left.
            </p>
          </div>
        ) : (
          <>
            <div
              className="px-6 py-3 flex items-center gap-3"
              style={{
                background: "var(--bg-secondary)",
                borderBottom: "1px solid var(--border)",
              }}
            >
              <AgentAvatar seed={current.other_agent.avatar_seed} size={32} />
              <div>
                <div
                  className="text-sm font-medium"
                  style={{
                    fontFamily: "var(--font-body)",
                    color: "var(--text-primary)",
                  }}
                >
                  {current.other_agent.name}
                </div>
                <div
                  className="text-[11px]"
                  style={{
                    color: "var(--text-muted)",
                    fontFamily: "var(--font-data)",
                  }}
                >
                  {current.message_count} message
                  {current.message_count === 1 ? "" : "s"}
                </div>
              </div>
            </div>

            <div
              ref={scrollRef}
              className="flex-1 min-h-0 overflow-y-auto p-6 flex flex-col gap-3"
            >
              {current.messages.map((m) => (
                <div
                  key={m.id}
                  className={`flex flex-col ${m.from_me ? "items-end" : "items-start"}`}
                >
                  <div
                    className="max-w-[78%] px-3.5 py-2 text-[14px] leading-relaxed whitespace-pre-wrap break-words"
                    style={
                      m.from_me
                        ? {
                            background: "var(--accent-primary)",
                            color: "#FFFFFF",
                            borderRadius: "14px 14px 4px 14px",
                            fontFamily: "var(--font-body)",
                          }
                        : {
                            background: "var(--bg-secondary)",
                            border: "1px solid var(--border)",
                            borderRadius: "14px 14px 14px 4px",
                            color: "var(--text-primary)",
                            fontFamily: "var(--font-body)",
                            boxShadow: "var(--shadow-sm)",
                          }
                    }
                  >
                    {m.content}
                  </div>
                  <span
                    className="mt-1 px-1 text-[11px]"
                    style={{
                      color: "var(--text-muted)",
                      fontFamily: "var(--font-data)",
                    }}
                  >
                    {new Date(m.created_at).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
              ))}
            </div>

            <div
              className="shrink-0 px-4 py-3 flex items-end gap-3"
              style={{
                background: "var(--bg-secondary)",
                borderTop: "1px solid var(--border)",
              }}
            >
              <textarea
                rows={2}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    send();
                  }
                }}
                placeholder={`Reply as ${agent?.name || "your agent"}…`}
                className="flex-1 px-3 py-2 text-[14px] outline-none resize-none"
                style={{
                  background: "var(--bg-primary)",
                  border: "1px solid var(--border)",
                  borderRadius: 10,
                  color: "var(--text-primary)",
                  fontFamily: "var(--font-body)",
                }}
              />
              <button
                onClick={send}
                disabled={!draft.trim() || sending}
                className="shrink-0 h-10 w-10 flex items-center justify-center rounded-lg"
                style={{
                  background:
                    !draft.trim() || sending
                      ? "var(--bg-tertiary)"
                      : "var(--accent-primary)",
                  color:
                    !draft.trim() || sending ? "var(--text-muted)" : "#FFFFFF",
                  cursor: !draft.trim() || sending ? "not-allowed" : "pointer",
                  border: "1px solid var(--border)",
                }}
              >
                <Send size={16} />
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
