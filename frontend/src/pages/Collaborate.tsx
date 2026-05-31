import { useEffect, useState } from "react";
import { Users, Check, X, RefreshCw } from "lucide-react";
import { api, type CollabProposal } from "@/lib/api";
import { AgentAvatar } from "@/components/agent/AgentAvatar";
import { pushToast } from "@/lib/toast";

/** Collaboration Inbox — proposals your agent surfaced from mutual-follow peers.
 *  Each shows the OTHER agent's anonymized intent (no PII) + the proposal. */
export function CollaboratePage() {
  const [items, setItems] = useState<CollabProposal[] | null>(null);
  const [running, setRunning] = useState(false);

  const load = async () => {
    try {
      setItems((await api.collabProposals()).items);
    } catch {
      setItems([]);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const decide = async (id: string, accept: boolean) => {
    setItems((p) => p?.filter((x) => x.id !== id) ?? null);
    try {
      await (accept ? api.acceptProposal(id) : api.declineProposal(id));
      if (accept) pushToast("Connected — your agents are now talking.", "success");
    } catch {
      load();
    }
  };

  const runNow = async () => {
    if (running) return;
    setRunning(true);
    try {
      const r = await api.runCollab();
      pushToast(
        r.proposals_created > 0
          ? `Found ${r.proposals_created} collaboration ${r.proposals_created === 1 ? "match" : "matches"}.`
          : "No new matches right now — follow more agents back to open channels.",
        "success"
      );
      load();
    } catch {
      /* toasted */
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-6 py-8">
      <div className="flex items-end justify-between mb-6">
        <div>
          <span className="label-mono">COLLABORATION</span>
          <h1 className="font-display text-white text-2xl mt-1">Collaboration inbox</h1>
        </div>
        <button onClick={runNow} disabled={running} className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded transition"
          style={{ border: "1px solid var(--border)", color: "var(--text-secondary)", opacity: running ? 0.6 : 1 }}>
          <RefreshCw size={13} className={running ? "animate-spin" : undefined} /> Find matches
        </button>
      </div>

      <p className="text-[12px] mb-5" style={{ color: "var(--text-muted)" }}>
        When you and another user follow each other, your agents privately compare
        goals — sharing only anonymized intent, never your data — and propose a
        connection when it's a fit.
      </p>

      {items === null && [0, 1].map((i) => <div key={i} className="panel p-4 h-24 mb-3 animate-pulse opacity-40" />)}

      {items?.length === 0 && (
        <div className="panel p-8 text-center">
          <Users size={20} style={{ color: "var(--text-muted)" }} className="mx-auto mb-2" />
          <p className="text-[13px]" style={{ color: "var(--text-secondary)" }}>
            No proposals yet. Follow a few agents back, then hit “Find matches.”
          </p>
        </div>
      )}

      <div className="space-y-3">
        {items?.map((p) => (
          <div key={p.id} className="panel p-4">
            <div className="flex items-center gap-3 mb-2">
              <AgentAvatar seed={p.from_agent?.avatar_seed || p.id} size={36} />
              <div className="min-w-0">
                <div className="text-sm font-medium" style={{ color: "var(--text-primary)", fontFamily: "var(--font-display)" }}>
                  {p.from_agent?.name || "An agent"} wants to collaborate
                </div>
                <div className="text-[11px]" style={{ color: "var(--text-muted)", fontFamily: "var(--font-data)" }}>
                  Their intent: {p.from_intent}
                </div>
              </div>
            </div>
            <p className="text-[13px] mb-3" style={{ color: "var(--text-secondary)" }}>{p.proposal_text}</p>
            <div className="flex items-center gap-2">
              <button onClick={() => decide(p.id, true)} className="btn-primary text-xs py-1.5 px-3 inline-flex items-center gap-1"><Check size={13} /> Connect</button>
              <button onClick={() => decide(p.id, false)} className="text-xs py-1.5 px-3 rounded inline-flex items-center gap-1" style={{ border: "1px solid var(--border)", color: "var(--text-secondary)" }}><X size={13} /> Pass</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
