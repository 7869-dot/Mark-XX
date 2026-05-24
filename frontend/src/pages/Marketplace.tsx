import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type MarketplaceTemplate } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { AgentAvatar } from "@/components/agent/AgentAvatar";
import { CloneConfirmModal } from "@/components/marketplace/CloneConfirmModal";
import { pushToast } from "@/lib/toast";

const CATEGORIES = ["All", "Productivity", "Social", "Research", "Finance"] as const;
type Category = (typeof CATEGORIES)[number];

/**
 * Agent marketplace — browse curated templates and apply one to your agent.
 *
 * Because the schema is one-agent-per-user, "Clone Agent" re-themes the
 * caller's existing agent (name, bio, avatar, voice, schedule) rather than
 * creating a second agent. The user's social graph + history is preserved.
 */
export function MarketplacePage() {
  const navigate = useNavigate();
  const { refreshAgent } = useAuth();
  const [items, setItems] = useState<MarketplaceTemplate[] | null>(null);
  const [active, setActive] = useState<Category>("All");
  const [cloningId, setCloningId] = useState<string | null>(null);
  // Two-step clone: a pending template populates the confirm modal,
  // and only "Replace my agent" actually fires the POST /clone.
  const [pending, setPending] = useState<MarketplaceTemplate | null>(null);

  useEffect(() => {
    api
      .marketplace()
      .then((r) => setItems(r.items))
      .catch(() => setItems([]));
  }, []);

  const filtered = useMemo(() => {
    if (!items) return null;
    if (active === "All") return items;
    return items.filter((t) => t.category === active);
  }, [items, active]);

  const requestClone = (t: MarketplaceTemplate) => {
    if (cloningId) return;
    setPending(t);
  };

  const confirmClone = async () => {
    if (!pending || cloningId) return;
    setCloningId(pending.id);
    try {
      await api.cloneTemplate(pending.id);
      pushToast(`Your agent is ready — meet ${pending.name}.`, "success");
      setPending(null);
      await refreshAgent();
      navigate("/agent");
    } catch {
      // toasted by the API client
    } finally {
      setCloningId(null);
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      <span className="label-mono">AGENT MARKETPLACE</span>
      <h1 className="font-display text-white text-2xl mt-1 mb-1">
        Templates
      </h1>
      <p className="font-mono text-xs text-silver-axo mb-6">
        Clone a pre-built agent — voice, schedule and capabilities all wired up.
      </p>

      {/* Category tabs */}
      <div className="flex flex-wrap gap-2 mb-6">
        {CATEGORIES.map((cat) => {
          const on = active === cat;
          return (
            <button
              key={cat}
              onClick={() => setActive(cat)}
              className={`text-xs font-mono px-3 py-1.5 rounded-md border transition ${
                on
                  ? "border-cyan-axo/70 bg-cyan-axo/10 text-cyan-axo"
                  : "border-ink-600 text-silver-axo hover:border-ink-500"
              }`}
            >
              {cat}
            </button>
          );
        })}
      </div>

      {filtered === null && (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="panel p-5 h-44 animate-pulse opacity-40" />
          ))}
        </div>
      )}

      {filtered?.length === 0 && (
        <div className="panel p-12 text-center">
          <p className="font-mono text-xs text-silver-axo">
            No templates in {active} yet.
          </p>
        </div>
      )}

      {filtered && filtered.length > 0 && (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((t) => (
            <TemplateCard
              key={t.id}
              template={t}
              busy={cloningId === t.id}
              onClone={() => requestClone(t)}
            />
          ))}
        </div>
      )}

      {pending && (
        <CloneConfirmModal
          templateId={pending.id}
          templateName={pending.name}
          busy={cloningId === pending.id}
          onCancel={() => cloningId || setPending(null)}
          onConfirm={confirmClone}
        />
      )}
    </div>
  );
}

function TemplateCard({
  template,
  busy,
  onClone,
}: {
  template: MarketplaceTemplate;
  busy: boolean;
  onClone: () => void;
}) {
  return (
    <div className="panel p-5 flex flex-col gap-3">
      <div className="flex items-start gap-3">
        <AgentAvatar seed={template.avatar_seed} size={44} />
        <div className="min-w-0 flex-1">
          <div className="font-display text-white text-sm truncate">
            {template.name}
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="chip border-ink-600 text-silver-axo/80 text-[10px]">
              {template.category}
            </span>
            <span className="font-mono text-[10px] text-silver-axo/70">
              {template.clone_count} clone{template.clone_count === 1 ? "" : "s"}
            </span>
          </div>
        </div>
      </div>
      <p className="font-mono text-xs text-silver-axo flex-1 line-clamp-4">
        {template.description}
      </p>
      <button
        onClick={onClone}
        disabled={busy}
        className="btn-primary text-xs py-1.5 w-full"
        style={{ opacity: busy ? 0.6 : 1 }}
      >
        {busy ? "Applying…" : "Clone Agent"}
      </button>
    </div>
  );
}
