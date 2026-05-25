/** Email Intelligence — two-section card on the dashboard.
 *
 * Top section: URGENT_HUMAN emails (must be read by the user, no agent action).
 * Bottom section: AGENT_HANDLEABLE drafts (approve/edit/discard inline).
 *
 * Reads via api.classifiedEmails(); the 30-min scheduler job is the canonical
 * source — this UI also offers a manual "refresh" button.
 */
import { useEffect, useState } from "react";
import { AlertTriangle, FileText, RefreshCcw, Check, Pencil, X } from "lucide-react";
import { api, type ClassifiedEmailRow } from "@/lib/api";
import { pushToast } from "@/lib/toast";

function relativeTime(iso: string): string {
  const d = new Date(iso);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return d.toLocaleDateString();
}

function UrgentCard({
  row,
  onDismiss,
}: {
  row: ClassifiedEmailRow;
  onDismiss: () => void;
}) {
  return (
    <div
      className="p-3 flex items-start gap-3 transition"
      style={{
        background: "var(--bg-secondary)",
        border: "1px solid var(--border)",
        borderLeft: "3px solid var(--accent-danger)",
        borderRadius: 8,
      }}
    >
      <AlertTriangle
        size={16}
        style={{ color: "var(--accent-danger)", flexShrink: 0, marginTop: 2 }}
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <span
            className="text-[13px] font-medium truncate"
            style={{ color: "var(--text-primary)" }}
          >
            {row.sender || row.sender_email || "Unknown sender"}
          </span>
          <span
            className="text-[11px] shrink-0"
            style={{
              color: "var(--text-muted)",
              fontFamily: "var(--font-data)",
            }}
          >
            {relativeTime(row.created_at)}
          </span>
        </div>
        <div
          className="text-[13px] mt-0.5 truncate"
          style={{ color: "var(--text-primary)" }}
        >
          {row.subject || "(no subject)"}
        </div>
        <div
          className="text-[12px] mt-1"
          style={{ color: "var(--text-secondary)" }}
        >
          {row.reason || "Flagged for your attention."}
        </div>
      </div>
      <button
        onClick={onDismiss}
        className="p-1 rounded transition"
        style={{ color: "var(--text-muted)" }}
        onMouseEnter={(e) => (e.currentTarget.style.color = "var(--text-primary)")}
        onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted)")}
        title="Dismiss"
      >
        <X size={14} />
      </button>
    </div>
  );
}

function DraftCard({
  row,
  onChange,
}: {
  row: ClassifiedEmailRow;
  onChange: (next: ClassifiedEmailRow | null) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(row.drafted_reply || "");
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    try {
      const next = await api.editEmailDraft(row.id, draft);
      onChange(next);
      setEditing(false);
      pushToast("Draft updated.");
    } catch {
      /* error toast already pushed */
    } finally {
      setBusy(false);
    }
  };

  const approve = async () => {
    setBusy(true);
    try {
      const next = await api.approveEmailDraft(row.id);
      onChange(null); // remove from list — it's sent
      pushToast(`Reply sent to ${next.sender || next.sender_email}.`);
    } finally {
      setBusy(false);
    }
  };

  const discard = async () => {
    setBusy(true);
    try {
      await api.discardEmailDraft(row.id);
      onChange(null);
      pushToast("Draft discarded.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="p-3"
      style={{
        background: "var(--bg-secondary)",
        border: "1px solid var(--border)",
        borderLeft: "3px solid var(--accent-primary)",
        borderRadius: 8,
      }}
    >
      <div className="flex items-baseline justify-between gap-2 mb-2">
        <div className="min-w-0 flex-1">
          <div
            className="text-[13px] font-medium truncate"
            style={{ color: "var(--text-primary)" }}
          >
            Re: {row.subject || "(no subject)"}
          </div>
          <div
            className="text-[11px] mt-0.5"
            style={{
              color: "var(--text-muted)",
              fontFamily: "var(--font-data)",
            }}
          >
            to {row.sender || row.sender_email} · {relativeTime(row.created_at)}
          </div>
        </div>
      </div>

      {editing ? (
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={5}
          className="w-full text-[13px] px-2.5 py-2 outline-none resize-y"
          style={{
            background: "var(--bg-tertiary)",
            border: "1px solid var(--border)",
            borderRadius: 6,
            color: "var(--text-primary)",
            fontFamily: "var(--font-body)",
          }}
        />
      ) : (
        <div
          className="text-[13px] whitespace-pre-wrap p-2.5"
          style={{
            background: "var(--bg-tertiary)",
            border: "1px solid var(--border)",
            borderRadius: 6,
            color: "var(--text-primary)",
            fontFamily: "var(--font-body)",
            maxHeight: 200,
            overflowY: "auto",
          }}
        >
          {row.drafted_reply || "(no draft)"}
        </div>
      )}

      <div className="flex items-center gap-2 mt-2.5">
        {editing ? (
          <>
            <button
              onClick={save}
              disabled={busy}
              className="btn-primary text-xs py-1 px-3"
            >
              Save
            </button>
            <button
              onClick={() => {
                setEditing(false);
                setDraft(row.drafted_reply || "");
              }}
              className="btn-ghost text-xs py-1 px-3"
            >
              Cancel
            </button>
          </>
        ) : (
          <>
            <button
              onClick={approve}
              disabled={busy}
              className="btn-primary text-xs py-1 px-3 inline-flex items-center gap-1"
            >
              <Check size={12} /> Approve &amp; send
            </button>
            <button
              onClick={() => setEditing(true)}
              disabled={busy}
              className="btn-ghost text-xs py-1 px-3 inline-flex items-center gap-1"
            >
              <Pencil size={12} /> Edit
            </button>
            <button
              onClick={discard}
              disabled={busy}
              className="btn-ghost text-xs py-1 px-3 inline-flex items-center gap-1"
              style={{ color: "var(--text-secondary)" }}
            >
              <X size={12} /> Discard
            </button>
          </>
        )}
      </div>
    </div>
  );
}

export function EmailIntelligence() {
  const [data, setData] = useState<
    | {
        urgent: ClassifiedEmailRow[];
        drafts: ClassifiedEmailRow[];
        urgent_count: number;
        drafts_count: number;
      }
    | null
  >(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    try {
      const res = await api.classifiedEmails();
      setData({
        urgent: res.urgent,
        drafts: res.drafts,
        urgent_count: res.urgent_count,
        drafts_count: res.drafts_count,
      });
    } catch {
      setData({ urgent: [], drafts: [], urgent_count: 0, drafts_count: 0 });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // Re-fetch every 2 min — the backend job runs every 30 min, but local
    // approve/dismiss actions also mutate state and we want the next load
    // to converge quickly.
    const id = setInterval(load, 120_000);
    return () => clearInterval(id);
  }, []);

  const refresh = async () => {
    setRefreshing(true);
    try {
      await api.refreshClassifications();
      await load();
    } catch {
      /* toast already shown */
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <section className="panel p-4 mb-5">
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="label-mono">Email intelligence</div>
          <h2
            className="text-base mt-0.5"
            style={{ fontFamily: "var(--font-display)" }}
          >
            What needs your attention
          </h2>
        </div>
        <button
          onClick={refresh}
          disabled={refreshing}
          className="btn-ghost text-xs py-1 px-2.5 inline-flex items-center gap-1.5"
          title="Re-run classification now"
        >
          <RefreshCcw
            size={12}
            style={{
              animation: refreshing ? "spin 0.8s linear infinite" : undefined,
            }}
          />
          {refreshing ? "Classifying…" : "Refresh"}
        </button>
      </div>

      {loading && (
        <div className="space-y-2">
          <div className="skeleton h-16" />
          <div className="skeleton h-16" />
        </div>
      )}

      {!loading && data && (
        <>
          {/* URGENT */}
          <div className="mb-4">
            <div
              className="text-[11px] uppercase tracking-wider mb-2"
              style={{
                color: "var(--text-secondary)",
                fontFamily: "var(--font-data)",
              }}
            >
              Urgent · needs you ({data.urgent.length})
            </div>
            {data.urgent.length === 0 ? (
              <p
                className="text-[13px] py-3 px-3"
                style={{
                  color: "var(--text-secondary)",
                  background: "var(--bg-tertiary)",
                  borderRadius: 6,
                }}
              >
                Nothing urgent in the last 48h. Your agent is filtering the rest.
              </p>
            ) : (
              <div className="space-y-2">
                {data.urgent.map((row) => (
                  <UrgentCard
                    key={row.id}
                    row={row}
                    onDismiss={async () => {
                      try {
                        await api.dismissEmail(row.id);
                        setData((prev) =>
                          prev
                            ? {
                                ...prev,
                                urgent: prev.urgent.filter((r) => r.id !== row.id),
                                urgent_count: Math.max(0, prev.urgent_count - 1),
                              }
                            : prev
                        );
                      } catch {
                        /* toast shown */
                      }
                    }}
                  />
                ))}
              </div>
            )}
          </div>

          {/* DRAFTS */}
          <div>
            <div
              className="text-[11px] uppercase tracking-wider mb-2 flex items-center gap-1.5"
              style={{
                color: "var(--text-secondary)",
                fontFamily: "var(--font-data)",
              }}
            >
              <FileText size={11} />
              Agent drafts ({data.drafts.length})
            </div>
            {data.drafts.length === 0 ? (
              <p
                className="text-[13px] py-3 px-3"
                style={{
                  color: "var(--text-secondary)",
                  background: "var(--bg-tertiary)",
                  borderRadius: 6,
                }}
              >
                No routine emails waiting for a reply.
              </p>
            ) : (
              <div className="space-y-2">
                {data.drafts.map((row) => (
                  <DraftCard
                    key={row.id}
                    row={row}
                    onChange={(next) =>
                      setData((prev) => {
                        if (!prev) return prev;
                        if (!next) {
                          return {
                            ...prev,
                            drafts: prev.drafts.filter((r) => r.id !== row.id),
                            drafts_count: Math.max(0, prev.drafts_count - 1),
                          };
                        }
                        return {
                          ...prev,
                          drafts: prev.drafts.map((r) =>
                            r.id === next.id ? next : r
                          ),
                        };
                      })
                    }
                  />
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}
