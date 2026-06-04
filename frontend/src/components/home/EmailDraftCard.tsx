import { useState } from "react";
import { IconCheck, IconX, IconMessage, IconChevronDown, IconChevronUp } from "@tabler/icons-react";
import type { AgentDraft } from "@/lib/api";
import { api } from "@/lib/api";
import { pushToast } from "@/lib/toast";

const PREVIEW_CHARS = 90;

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
  const preview = body.length > PREVIEW_CHARS ? body.slice(0, PREVIEW_CHARS).trimEnd() + "…" : body;

  const approve = async () => {
    try {
      await navigator.clipboard.writeText(body);
      setCopied(true);
      pushToast("Draft copied to clipboard", "success");
    } catch {
      pushToast("Couldn't access the clipboard — select and copy manually.");
    }
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
    <div className="axo-draft">
      <div className="axo-email-top">
        <span className="axo-email-sender">{contact}</span>
        {draft.created_at && (
          <span className="axo-email-time">{new Date(draft.created_at).toLocaleDateString()}</span>
        )}
      </div>
      <div className="axo-email-subject">Re: {subject}</div>

      <div className="axo-draft-body">{expanded ? body : preview}</div>
      {body.length > PREVIEW_CHARS && (
        <button className="axo-link" onClick={() => setExpanded((e) => !e)}>
          {expanded ? (
            <>
              <IconChevronUp size={11} style={{ verticalAlign: "-1px" }} /> Collapse
            </>
          ) : (
            <>
              <IconChevronDown size={11} style={{ verticalAlign: "-1px" }} /> Expand
            </>
          )}
        </button>
      )}

      <div className="axo-draft-actions" style={{ marginTop: 10 }}>
        <button className="axo-btn axo-btn-primary" onClick={approve} disabled={busy}>
          <IconCheck size={12} /> {copied ? "Copied!" : "Approve"}
        </button>
        <button className="axo-btn" onClick={() => onAskJarvis(draft)}>
          <IconMessage size={12} /> Ask Jarvis
        </button>
        <button
          className="axo-btn axo-btn-ghost"
          onClick={dismiss}
          disabled={busy}
          title="Dismiss"
          style={{ marginLeft: "auto" }}
        >
          <IconX size={12} />
        </button>
      </div>
    </div>
  );
}
