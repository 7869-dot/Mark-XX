import { useState } from "react";
import { IconCheck, IconX, IconMessage, IconChevronDown, IconChevronUp } from "@tabler/icons-react";
import type { AgentDraft } from "@/lib/api";
import { api } from "@/lib/api";
import { pushToast } from "@/lib/toast";

const PREVIEW_CHARS = 80;

export function EmailDraftCard({
  draft,
  onAskJarvis,
  onResolve,
}: {
  draft: AgentDraft;
  onAskJarvis: (draft: AgentDraft) => void;
  onResolve: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);

  const contact = draft.recipient_hint || "your contact";
  const subject = draft.subject_line || "(no subject)";
  const body = draft.draft_content || "";
  const preview =
    body.length > PREVIEW_CHARS ? body.slice(0, PREVIEW_CHARS).trimEnd() + "…" : body;

  const approve = async () => {
    // Copy the full draft to the clipboard — never auto-send.
    try {
      await navigator.clipboard.writeText(body);
      setCopied(true);
      pushToast("Draft copied to clipboard", "success");
    } catch {
      pushToast("Couldn't access the clipboard — select and copy manually.");
    }
    // Record the approval server-side (no send path in V1), best-effort.
    setBusy(true);
    try {
      await api.decideDraft(draft.id, true);
    } catch {
      /* optimistic — the copy already happened */
    }
    setTimeout(() => onResolve(draft.id), 900);
  };

  const dismiss = async () => {
    setBusy(true);
    try {
      await api.decideDraft(draft.id, false);
    } catch {
      /* optimistic */
    }
    onResolve(draft.id);
  };

  return (
    <div
      className="rounded-xl p-3.5"
      style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm font-medium truncate" style={{ color: "var(--text-primary)" }}>
          {contact}
        </span>
        {draft.created_at && (
          <span
            className="text-[10px] shrink-0"
            style={{ color: "var(--text-tertiary)", fontFamily: "var(--font-data)" }}
          >
            {new Date(draft.created_at).toLocaleDateString()}
          </span>
        )}
      </div>
      <div className="text-xs mt-0.5 truncate" style={{ color: "var(--text-secondary)" }}>
        Re: {subject}
      </div>

      <p
        className="text-[13px] mt-2 leading-relaxed whitespace-pre-wrap"
        style={{ color: "var(--text-secondary)" }}
      >
        {expanded ? body : preview}
      </p>

      {body.length > PREVIEW_CHARS && (
        <button
          onClick={() => setExpanded((e) => !e)}
          className="mt-1.5 text-[11px] inline-flex items-center gap-1"
          style={{ color: "var(--accent-primary)" }}
        >
          {expanded ? <IconChevronUp size={12} /> : <IconChevronDown size={12} />}
          {expanded ? "Collapse" : "Expand"}
        </button>
      )}

      <div className="flex items-center gap-2 mt-3">
        <button
          onClick={approve}
          disabled={busy}
          className="btn-primary text-xs py-1.5 px-3 inline-flex items-center gap-1.5"
          style={{ opacity: busy ? 0.6 : 1 }}
        >
          <IconCheck size={13} /> {copied ? "Copied!" : "Approve"}
        </button>
        <button
          onClick={() => onAskJarvis(draft)}
          className="text-xs py-1.5 px-3 rounded-lg inline-flex items-center gap-1.5"
          style={{ border: "1px solid var(--border)", color: "var(--text-primary)" }}
        >
          <IconMessage size={13} /> Ask Jarvis
        </button>
        <button
          onClick={dismiss}
          disabled={busy}
          className="text-xs py-1.5 px-2.5 rounded-lg inline-flex items-center gap-1 ml-auto"
          style={{ border: "1px solid var(--border)", color: "var(--text-secondary)" }}
          title="Dismiss"
        >
          <IconX size={13} />
        </button>
      </div>
    </div>
  );
}
