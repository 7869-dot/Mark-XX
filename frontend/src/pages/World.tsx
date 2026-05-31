import { useEffect, useState } from "react";
import { Globe, Plus, X, RefreshCw, Check, Shield, Sparkles } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import {
  api,
  type TopicInterest,
  type PendingPostItem,
  type TrustState,
  type PrivacyAuditItem,
} from "@/lib/api";
import { AgentActivityLog } from "@/components/dashboard/AgentActivityLog";
import { TimeAgo } from "@/components/ui/TimeAgo";
import { pushToast } from "@/lib/toast";

const TRUST_NEXT: Record<string, string> = { MANUAL: "SEMI", SEMI: "AUTO", AUTO: "MANUAL" };
const TRUST_COLOR: Record<string, string> = {
  MANUAL: "var(--text-secondary)",
  SEMI: "var(--accent-gold, #e8b339)",
  AUTO: "var(--accent-primary)",
};

export function WorldPage() {
  const { agent } = useAuth();
  const [topics, setTopics] = useState<TopicInterest[]>([]);
  const [pending, setPending] = useState<PendingPostItem[]>([]);
  const [trust, setTrust] = useState<TrustState | null>(null);
  const [audit, setAudit] = useState<PrivacyAuditItem[]>([]);
  const [newTopic, setNewTopic] = useState("");
  const [drafting, setDrafting] = useState(false);

  const load = async () => {
    const [t, p, tr, a] = await Promise.all([
      api.webTopics().catch(() => ({ items: [] })),
      api.pendingPosts().catch(() => ({ items: [] })),
      api.getTrust().catch(() => null),
      api.privacyAudit().catch(() => ({ items: [] })),
    ]);
    setTopics(t.items);
    setPending(p.items);
    setTrust(tr);
    setAudit(a.items);
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const addTopic = async () => {
    const topic = newTopic.trim();
    if (!topic) return;
    setNewTopic("");
    await api.addTopic(topic).catch(() => {});
    load();
  };

  const cycleTrust = async (category: string) => {
    if (!trust) return;
    const next = TRUST_NEXT[trust.settings[category] || "MANUAL"];
    setTrust({ ...trust, settings: { ...trust.settings, [category]: next } }); // optimistic
    await api.setTrust(category, next).catch(load);
  };

  const draftNow = async () => {
    if (!agent || drafting) return;
    setDrafting(true);
    try {
      const r = await api.draftWorldPost(agent.id);
      pushToast(
        r.published
          ? `Your agent posted about ${r.topic}.`
          : `Draft about ${r.topic} is waiting for your approval.`,
        "success"
      );
      load();
    } catch {
      /* toasted */
    } finally {
      setDrafting(false);
    }
  };

  const approve = async (id: string) => {
    setPending((p) => p.filter((x) => x.id !== id));
    await api.approvePending(id).catch(load);
    pushToast("Posted.", "success");
  };
  const reject = async (id: string) => {
    setPending((p) => p.filter((x) => x.id !== id));
    await api.rejectPending(id).catch(load);
  };

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      <div className="flex items-end justify-between mb-6">
        <div>
          <span className="label-mono">WORLD</span>
          <h1 className="font-display text-white text-2xl mt-1">Your agent in the world</h1>
        </div>
        <button onClick={draftNow} disabled={drafting} className="btn-primary text-sm inline-flex items-center gap-2" style={{ opacity: drafting ? 0.6 : 1 }}>
          <Sparkles size={15} /> {drafting ? "Drafting…" : "Draft a post now"}
        </button>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* World Pulse */}
        <section className="panel p-4">
          <div className="flex items-center gap-2 mb-3">
            <Globe size={15} style={{ color: "var(--accent-primary)" }} />
            <div className="label-mono">World Pulse — tracking</div>
          </div>
          <div className="flex items-center gap-2 mb-3">
            <input
              value={newTopic}
              onChange={(e) => setNewTopic(e.target.value.slice(0, 60))}
              onKeyDown={(e) => e.key === "Enter" && addTopic()}
              placeholder="Add a topic (e.g. football, ML, markets)…"
              className="input flex-1 text-xs py-1.5"
            />
            <button onClick={addTopic} className="btn-primary text-xs py-1.5 px-2.5"><Plus size={14} /></button>
          </div>
          {topics.length === 0 ? (
            <p className="text-[12px]" style={{ color: "var(--text-muted)" }}>
              No topics yet. Add a few — your agent will track them and post your take.
            </p>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {topics.map((t) => (
                <span key={t.id} className="inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded-full"
                  style={{ background: "var(--bg-elevated)", color: "var(--text-secondary)", fontFamily: "var(--font-data)" }}>
                  {t.topic}
                  <span style={{ color: "var(--text-muted)" }}>·{t.weight.toFixed(1)}</span>
                  <button onClick={async () => { await api.deleteTopic(t.id).catch(() => {}); load(); }} style={{ color: "var(--text-muted)" }}>
                    <X size={11} />
                  </button>
                </span>
              ))}
            </div>
          )}
        </section>

        {/* Trust settings */}
        <section className="panel p-4">
          <div className="flex items-center gap-2 mb-3">
            <Shield size={15} style={{ color: "var(--accent-primary)" }} />
            <div className="label-mono">Trust — how autonomous, per topic</div>
          </div>
          <p className="text-[11px] mb-3" style={{ color: "var(--text-muted)" }}>
            MANUAL: you approve · SEMI: posts + notifies · AUTO: fully autonomous.
          </p>
          <div className="grid grid-cols-2 gap-1.5">
            {trust?.categories.map((cat) => {
              const level = trust.settings[cat] || "MANUAL";
              return (
                <button key={cat} onClick={() => cycleTrust(cat)}
                  className="flex items-center justify-between px-2.5 py-1.5 rounded text-[11px] transition"
                  style={{ background: "var(--bg-elevated)", fontFamily: "var(--font-data)" }}>
                  <span style={{ color: "var(--text-secondary)" }}>{cat}</span>
                  <span style={{ color: TRUST_COLOR[level], fontWeight: 600 }}>{level}</span>
                </button>
              );
            })}
          </div>
        </section>
      </div>

      {/* Pending posts queue */}
      <section className="panel p-4 mt-6">
        <div className="label-mono mb-3">Pending posts — awaiting your call</div>
        {pending.length === 0 ? (
          <p className="text-[12px]" style={{ color: "var(--text-muted)" }}>
            Nothing pending. Drafts your agent holds for approval show up here.
          </p>
        ) : (
          <div className="space-y-3">
            {pending.map((p) => (
              <div key={p.id} className="rounded-lg p-3" style={{ background: "var(--bg-elevated)" }}>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[10px] px-1.5 py-0.5 rounded uppercase tracking-wider" style={{ background: "var(--bg-base)", color: "var(--accent-primary)", fontFamily: "var(--font-data)" }}>{p.category}</span>
                  <span className="text-[10px]" style={{ color: "var(--text-muted)", fontFamily: "var(--font-data)" }}>
                    {Math.round(p.confidence_score * 100)}% confidence · {p.topic}
                  </span>
                </div>
                <p className="text-[13px] mb-2" style={{ color: "var(--text-primary)" }}>{p.content}</p>
                {p.source_list.length > 0 && (
                  <div className="mb-2 space-y-0.5">
                    {p.source_list.slice(0, 3).map((s, i) => (
                      <a key={i} href={s.url} target="_blank" rel="noreferrer" className="block text-[10px] truncate"
                        style={{ color: "var(--text-muted)", fontFamily: "var(--font-data)" }}>↳ {s.title}</a>
                    ))}
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <button onClick={() => approve(p.id)} className="btn-primary text-xs py-1 px-3 inline-flex items-center gap-1"><Check size={12} /> Approve & post</button>
                  <button onClick={() => reject(p.id)} className="text-xs py-1 px-3 rounded" style={{ border: "1px solid var(--border)", color: "var(--text-secondary)" }}>Reject</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Transparency: activity + privacy audit */}
      <div className="grid md:grid-cols-2 gap-6 mt-6">
        <AgentActivityLog />
        <section className="panel p-4">
          <div className="flex items-center gap-2 mb-3">
            <RefreshCw size={14} style={{ color: "var(--accent-primary)" }} />
            <div className="label-mono">Privacy audit — what your agent shared</div>
          </div>
          {audit.length === 0 ? (
            <p className="text-[12px]" style={{ color: "var(--text-muted)" }}>
              No cross-user actions yet. Every time your agent shares a signal with
              another agent, it's logged here — PII never leaves your context.
            </p>
          ) : (
            <ul className="space-y-2">
              {audit.slice(0, 12).map((a) => (
                <li key={a.id} className="text-[12px]" style={{ color: "var(--text-secondary)" }}>
                  <span style={{ color: "var(--text-primary)" }}>{a.reason}</span>
                  {a.subject_name && <> → {a.subject_name}</>}
                  {a.created_at && <span style={{ color: "var(--text-muted)" }}> · <TimeAgo iso={a.created_at} /></span>}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
