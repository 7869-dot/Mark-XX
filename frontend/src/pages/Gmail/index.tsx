/**
 * Gmail inbox — agent-triaged.
 *
 * Flat chronological is intentionally avoided: when an inbox summary exists,
 * emails are grouped Urgent / Needs reply / Informational. Every Gmail-touching
 * surface degrades to a "Connect Gmail" CTA when not connected.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Sparkles, PenLine, Archive, CalendarPlus, Bot } from "lucide-react";
import { gmailApi } from "@/api/gmail";
import { integrationsApi } from "@/api/integrations";
import type { EmailFull, EmailListItem, InboxSummary } from "@/api/types";
import { EmailRow } from "@/components/email/EmailRow";
import { AgentBanner } from "@/components/shared/AgentBanner";
import { SlideOver } from "@/components/layout/SlideOver";
import { pushToast } from "@/lib/toast";

type Tab = "all" | "urgent" | "reply" | "info";

const TABS: { id: Tab; label: string }[] = [
  { id: "all", label: "All" },
  { id: "urgent", label: "Urgent" },
  { id: "reply", label: "Needs reply" },
  { id: "info", label: "Informational" },
];

function tagFor(subject: string, summary: InboxSummary | null): string {
  if (!summary) return "FYI";
  const has = (arr?: { subject: string }[]) =>
    (arr || []).some((x) => subject && x.subject && subject.includes(x.subject.slice(0, 20)));
  if (has(summary.urgent)) return "Reply today";
  if (has(summary.important)) return "Decision needed";
  return "FYI";
}

export function GmailPage() {
  const navigate = useNavigate();
  const [connected, setConnected] = useState<boolean | null>(null);
  const [emails, setEmails] = useState<EmailListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("all");
  const [summary, setSummary] = useState<InboxSummary | null>(null);
  const [summarizing, setSummarizing] = useState(false);
  const [showSummary, setShowSummary] = useState(false);

  const [detail, setDetail] = useState<EmailFull | null>(null);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [compose, setCompose] = useState<null | { to: string; subject: string; body: string }>(null);
  const [draftFor, setDraftFor] = useState<EmailFull | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const st = await integrationsApi.getStatus();
      setConnected(st.gmail || st.stub_mode);
      if (st.gmail || st.stub_mode) {
        setEmails(await gmailApi.getInbox(false, 30));
      }
    } catch {
      setConnected(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!detailId) {
      setDetail(null);
      return;
    }
    gmailApi.getEmail(detailId).then(setDetail).catch(() => setDetail(null));
  }, [detailId]);

  const runSummary = async () => {
    setSummarizing(true);
    try {
      const res = await gmailApi.summarizeInbox();
      setSummary(res.summary);
      pushToast("Inbox triaged by your agent.", "success");
    } finally {
      setSummarizing(false);
    }
  };

  const counts = useMemo(() => {
    const c = { all: emails.length, urgent: 0, reply: 0, info: 0 };
    for (const e of emails) {
      const t = tagFor(e.subject, summary);
      if (t === "Reply today") c.urgent++;
      else if (t === "Decision needed") c.reply++;
      else c.info++;
    }
    return c;
  }, [emails, summary]);

  const visible = useMemo(() => {
    if (tab === "all") return emails;
    return emails.filter((e) => {
      const t = tagFor(e.subject, summary);
      if (tab === "urgent") return t === "Reply today";
      if (tab === "reply") return t === "Decision needed";
      return t === "FYI";
    });
  }, [emails, tab, summary]);

  const grouped = useMemo(() => {
    const g: Record<string, EmailListItem[]> = {
      "Urgent — reply today": [],
      "Waiting on others": [],
      Informational: [],
    };
    for (const e of visible) {
      const t = tagFor(e.subject, summary);
      if (t === "Reply today") g["Urgent — reply today"].push(e);
      else if (t === "Decision needed") g["Waiting on others"].push(e);
      else g.Informational.push(e);
    }
    return g;
  }, [visible, summary]);

  const archive = async (id: string) => {
    await gmailApi.archive(id);
    setEmails((p) => p.filter((e) => e.id !== id));
    setDetailId(null);
    pushToast("Archived.", "info");
  };

  // ── Not connected ────────────────────────────────────────────────────────
  if (connected === false) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-8">
        <h1 className="font-display text-white text-2xl mb-4">Inbox</h1>
        <AgentBanner
          variant="warning"
          text="Connect Gmail to let your agent triage your inbox."
          actionLabel="Connect"
          onAction={() => navigate("/settings/integrations")}
        />
      </div>
    );
  }

  const DetailBody = detail && (
    <div className="space-y-4">
      <div>
        <div className="font-display text-white text-lg">{detail.subject}</div>
        <div className="font-mono text-xs text-silver-axo mt-1">
          {detail.sender} &lt;{detail.sender_email}&gt; · {detail.date}
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <button onClick={() => setDraftFor(detail)} className="btn-primary text-xs py-1.5">
          <PenLine size={13} className="inline mr-1" /> Draft reply
        </button>
        <button
          onClick={() =>
            setCompose({ to: detail.sender_email, subject: "Meeting?", body: "" })
          }
          className="btn-ghost text-xs py-1.5"
        >
          <CalendarPlus size={13} className="inline mr-1" /> Schedule meeting
        </button>
        <button onClick={() => archive(detail.id)} className="btn-ghost text-xs py-1.5">
          <Archive size={13} className="inline mr-1" /> Archive
        </button>
      </div>
      <pre className="panel-inset p-4 font-mono text-xs text-silver-axo whitespace-pre-wrap leading-relaxed">
        {detail.body_plain}
      </pre>
    </div>
  );

  return (
    <div className="h-[calc(100vh-3.5rem)] flex flex-col">
      {/* Top bar */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-ink-700/50">
        <h1 className="font-display text-white text-xl">Inbox</h1>
        <div className="flex gap-2">
          <button
            onClick={runSummary}
            disabled={summarizing}
            className="btn-ghost text-xs"
          >
            <Bot size={13} className="inline mr-1" />
            {summarizing ? "Triaging…" : "Ask agent"}
          </button>
          <button
            onClick={() => setCompose({ to: "", subject: "", body: "" })}
            className="btn-primary text-xs"
          >
            Compose
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 px-6 border-b border-ink-700/40">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-3 py-2 font-display text-xs capitalize border-b-2 -mb-px transition ${
              tab === t.id
                ? "border-cyan-axo text-cyan-axo"
                : "border-transparent text-silver-axo hover:text-white"
            }`}
          >
            {t.label}{" "}
            <span className="text-silver-axo/50">
              {t.id === "all"
                ? counts.all
                : t.id === "urgent"
                ? counts.urgent
                : t.id === "reply"
                ? counts.reply
                : counts.info}
            </span>
          </button>
        ))}
      </div>

      <div className="flex-1 min-h-0 flex">
        <div className="flex-1 min-w-0 overflow-y-auto">
          {summary && (
            <div className="p-4">
              <AgentBanner
                variant="info"
                text={`Agent triaged ${counts.all} emails. ${counts.urgent} need your reply today, ${counts.reply} awaiting a decision.`}
                actionLabel="View summary"
                onAction={() => setShowSummary(true)}
              />
            </div>
          )}
          {!summary && connected && (
            <div className="p-4">
              <AgentBanner
                variant="info"
                text="Have your agent triage this inbox into urgent / reply / FYI."
                actionLabel={summarizing ? "Working…" : "Summarize inbox"}
                onAction={runSummary}
              />
            </div>
          )}

          {loading && (
            <div className="p-4 space-y-2">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="panel h-14 animate-pulse opacity-40" />
              ))}
            </div>
          )}

          {!loading &&
            Object.entries(grouped).map(([group, rows]) =>
              rows.length === 0 ? null : (
                <div key={group}>
                  <div className="px-4 pt-4 pb-1 flex items-center gap-2">
                    {group.startsWith("Urgent") && (
                      <span className="w-1.5 h-1.5 rounded-full bg-rose-axo" />
                    )}
                    <span className="label-mono">{group}</span>
                  </div>
                  {rows.map((e) => (
                    <EmailRow
                      key={e.id}
                      email={e}
                      isSelected={detailId === e.id}
                      tag={tagFor(e.subject, summary)}
                      onClick={() => setDetailId(e.id)}
                    />
                  ))}
                </div>
              )
            )}
          {!loading && visible.length === 0 && (
            <p className="p-8 text-center font-mono text-xs text-silver-axo">
              Nothing here.
            </p>
          )}
        </div>

        {/* Desktop inline detail */}
        {detail && (
          <div className="hidden lg:block w-[460px] border-l border-ink-700/50 overflow-y-auto p-6">
            {DetailBody}
          </div>
        )}
      </div>

      {/* Mobile detail */}
      <div className="lg:hidden">
        <SlideOver
          open={!!detail}
          onClose={() => setDetailId(null)}
          title="EMAIL"
          width={520}
        >
          {DetailBody}
        </SlideOver>
      </div>

      {/* Summary slide-over */}
      <SlideOver
        open={showSummary}
        onClose={() => setShowSummary(false)}
        title="AGENT INBOX SUMMARY"
        width={460}
      >
        {summary && (
          <div className="space-y-5">
            {(["urgent", "important", "informational"] as const).map((k) =>
              (summary[k]?.length ?? 0) === 0 ? null : (
                <div key={k}>
                  <span className="label-mono capitalize">{k}</span>
                  <div className="mt-2 space-y-2">
                    {summary[k]!.map((s, i) => (
                      <div key={i} className="panel-inset p-3">
                        <div className="font-display text-white text-xs">
                          {s.subject}
                        </div>
                        <div className="font-mono text-[10px] text-silver-axo/70">
                          {s.from}
                        </div>
                        {"suggested_reply" in s && s.suggested_reply && (
                          <p className="font-mono text-xs text-cyan-axo mt-2">
                            → {s.suggested_reply}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )
            )}
          </div>
        )}
      </SlideOver>

      {/* Compose */}
      <SlideOver
        open={!!compose}
        onClose={() => setCompose(null)}
        title="COMPOSE"
        width={520}
      >
        {compose && (
          <ComposeForm
            initial={compose}
            onClose={() => setCompose(null)}
          />
        )}
      </SlideOver>

      {/* Agent draft */}
      <SlideOver
        open={!!draftFor}
        onClose={() => setDraftFor(null)}
        title="ASK YOUR AGENT TO DRAFT A REPLY"
        width={520}
      >
        {draftFor && (
          <AgentDraftForm
            email={draftFor}
            onUse={(body) => {
              setCompose({
                to: draftFor.sender_email,
                subject: "Re: " + draftFor.subject,
                body,
              });
              setDraftFor(null);
            }}
          />
        )}
      </SlideOver>
    </div>
  );
}

function ComposeForm({
  initial,
  onClose,
}: {
  initial: { to: string; subject: string; body: string };
  onClose: () => void;
}) {
  const [to, setTo] = useState(initial.to);
  const [subject, setSubject] = useState(initial.subject);
  const [body, setBody] = useState(initial.body);
  const [busy, setBusy] = useState(false);

  const act = async (kind: "send" | "draft") => {
    setBusy(true);
    try {
      if (kind === "send") {
        await gmailApi.sendEmail(to, subject, body);
        pushToast("Email sent.", "success");
      } else {
        await gmailApi.draftEmail(to, subject, body);
        pushToast("Draft saved to Gmail.", "info");
      }
      onClose();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <label className="label-mono block mb-1">To</label>
        <input
          className="input w-full"
          value={to}
          onChange={(e) => setTo(e.target.value)}
          placeholder="comma,separated@emails.com"
        />
      </div>
      <div>
        <label className="label-mono block mb-1">Subject</label>
        <input
          className="input w-full"
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
        />
      </div>
      <div>
        <label className="label-mono block mb-1">Body</label>
        <textarea
          className="input w-full min-h-[160px] resize-y"
          value={body}
          onChange={(e) => setBody(e.target.value)}
        />
      </div>
      <div className="flex gap-2">
        <button
          disabled={busy || !to}
          onClick={() => act("send")}
          className="btn-primary text-xs"
        >
          Send
        </button>
        <button
          disabled={busy}
          onClick={() => act("draft")}
          className="btn-ghost text-xs"
        >
          Save draft
        </button>
      </div>
    </div>
  );
}

function AgentDraftForm({
  email,
  onUse,
}: {
  email: EmailFull;
  onUse: (body: string) => void;
}) {
  const [instruction, setInstruction] = useState("");
  const [draft, setDraft] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const generate = async () => {
    setBusy(true);
    try {
      const res = await gmailApi.draftReply(email.id, instruction);
      setDraft(res.draft_body);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="font-mono text-xs text-silver-axo">
        Replying to <span className="text-white">{email.sender}</span> —{" "}
        {email.subject}
      </div>
      <div>
        <label className="label-mono block mb-1">
          What should the reply say?
        </label>
        <textarea
          className="input w-full min-h-[100px] resize-y"
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          placeholder="e.g. Confirm Thursday 2pm works. / Decline politely, suggest next month."
        />
      </div>
      <button
        disabled={busy || !instruction}
        onClick={generate}
        className="btn-primary text-xs w-full"
      >
        <Sparkles size={13} className="inline mr-1" />
        {busy ? "Generating…" : "Generate draft"}
      </button>

      {draft && (
        <div className="space-y-3 animate-fade-in">
          <pre className="panel-inset p-3 font-mono text-xs text-white whitespace-pre-wrap leading-relaxed">
            {draft}
          </pre>
          <div className="flex gap-2">
            <button onClick={() => onUse(draft)} className="btn-primary text-xs">
              Use this draft
            </button>
            <button onClick={generate} disabled={busy} className="btn-ghost text-xs">
              Regenerate
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
