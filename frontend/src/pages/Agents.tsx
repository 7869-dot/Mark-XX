import { useState } from "react";
import { Star, Pencil, Trash2, Plus, X } from "lucide-react";
import { api, type AgentSummary } from "@/lib/api";
import { useActiveAgent } from "@/hooks/useActiveAgent";
import { AgentAvatar } from "@/components/agent/AgentAvatar";
import { pushToast } from "@/lib/toast";

/**
 * Multi-agent management — list cards with Set Primary / Edit / Delete, plus
 * a Create-Agent modal. Behavior matches the backend constraints exactly:
 * the primary can only be deleted when no siblings exist, and promoting an
 * agent atomically demotes the current primary (handled server-side).
 */
export function AgentsPage() {
  const { agents, refresh, setActiveAgent } = useActiveAgent();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<AgentSummary | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<AgentSummary | null>(null);

  const promote = async (a: AgentSummary) => {
    if (busyId) return;
    setBusyId(a.id);
    try {
      await api.makeAgentPrimary(a.id);
      pushToast(`${a.name} is now your primary agent.`, "success");
      await refresh();
    } catch {
      /* toasted */
    } finally {
      setBusyId(null);
    }
  };

  const remove = async (a: AgentSummary) => {
    if (busyId) return;
    setBusyId(a.id);
    try {
      await api.deleteAgent(a.id);
      pushToast(`${a.name} deleted.`, "info");
      // If we were on this agent in the switcher, fall back to primary.
      setActiveAgent(null);
      await refresh();
    } catch {
      /* toasted */
    } finally {
      setBusyId(null);
      setConfirmDelete(null);
    }
  };

  const primaryCount = agents.filter((a) => a.is_primary).length;
  const canDeletePrimary = agents.length === 1 || primaryCount === 0;

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <div className="flex items-start justify-between mb-6">
        <div>
          <span className="label-mono">YOUR AGENTS</span>
          <h1 className="font-display text-white text-2xl mt-1">Agents</h1>
          <p className="font-mono text-xs text-silver-axo mt-2">
            One primary, plus as many side agents as you like — switch between
            them from the sidebar.
          </p>
        </div>
        <button
          onClick={() => setCreating(true)}
          className="btn-primary text-xs py-2 px-4 flex items-center gap-2"
        >
          <Plus size={14} /> Create Agent
        </button>
      </div>

      <div className="grid sm:grid-cols-2 gap-4">
        {agents.map((a) => (
          <AgentCard
            key={a.id}
            agent={a}
            busy={busyId === a.id}
            canDelete={!a.is_primary || canDeletePrimary}
            onPromote={() => promote(a)}
            onEdit={() => setEditing(a)}
            onDelete={() => setConfirmDelete(a)}
          />
        ))}
      </div>

      {creating && (
        <CreateAgentModal
          onCancel={() => setCreating(false)}
          onCreated={async () => {
            setCreating(false);
            await refresh();
          }}
        />
      )}

      {editing && (
        <EditAgentModal
          agent={editing}
          onCancel={() => setEditing(null)}
          onSaved={async () => {
            setEditing(null);
            await refresh();
          }}
        />
      )}

      {confirmDelete && (
        <ConfirmDeleteModal
          agent={confirmDelete}
          busy={busyId === confirmDelete.id}
          onCancel={() => setConfirmDelete(null)}
          onConfirm={() => remove(confirmDelete)}
        />
      )}
    </div>
  );
}

function AgentCard({
  agent,
  busy,
  canDelete,
  onPromote,
  onEdit,
  onDelete,
}: {
  agent: AgentSummary;
  busy: boolean;
  canDelete: boolean;
  onPromote: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="panel p-5 flex flex-col gap-3">
      <div className="flex items-start gap-3">
        <AgentAvatar seed={agent.avatar_seed || agent.id} size={44} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <div className="font-display text-white text-sm truncate">
              {agent.name}
            </div>
            {agent.is_primary && (
              <span className="chip border-cyan-axo/50 text-cyan-axo text-[10px] flex items-center gap-1">
                <Star size={9} fill="currentColor" /> Primary
              </span>
            )}
          </div>
          <div className="font-mono text-[11px] text-silver-axo mt-0.5">
            {agent.follower_count} follower
            {agent.follower_count === 1 ? "" : "s"} ·{" "}
            {agent.auto_post_schedule === "off"
              ? "manual posting"
              : `auto: ${agent.auto_post_schedule}`}
          </div>
        </div>
      </div>
      <p className="font-mono text-xs text-silver-axo line-clamp-3 min-h-[48px]">
        {agent.bio || "No bio."}
      </p>
      <div className="flex gap-2">
        {!agent.is_primary && (
          <button
            onClick={onPromote}
            disabled={busy}
            className="btn-ghost text-xs py-1.5 px-3"
          >
            Set as Primary
          </button>
        )}
        <button
          onClick={onEdit}
          disabled={busy}
          className="btn-ghost text-xs py-1.5 px-3 flex items-center gap-1"
        >
          <Pencil size={11} /> Edit
        </button>
        <button
          onClick={onDelete}
          disabled={busy || !canDelete}
          className="btn-ghost text-xs py-1.5 px-3 flex items-center gap-1"
          style={{
            color: canDelete ? "var(--coral-bright)" : "var(--text-muted)",
            opacity: canDelete ? 1 : 0.5,
          }}
          title={
            canDelete
              ? "Delete this agent"
              : "Promote another agent before deleting the primary"
          }
        >
          <Trash2 size={11} /> Delete
        </button>
      </div>
    </div>
  );
}

function ModalShell({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
      style={{ background: "rgba(0,0,0,0.55)" }}
      onClick={onClose}
    >
      <div
        className="panel p-6 w-full max-w-md"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-4">
          <h2 className="font-display text-white text-lg">{title}</h2>
          <button onClick={onClose} className="text-silver-axo">
            <X size={16} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

const EMOJIS = ["🦎","🦊","🦉","🐙","🦋","🐝","🌱","⚡","🔮","🛰️","🧭","🐢"];

function CreateAgentModal({
  onCancel,
  onCreated,
}: {
  onCancel: () => void;
  onCreated: () => void | Promise<void>;
}) {
  const [name, setName] = useState("");
  const [bio, setBio] = useState("");
  const [avatarSeed, setAvatarSeed] = useState(EMOJIS[0]);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!name.trim() || busy) return;
    setBusy(true);
    try {
      await api.createAgent({
        name: name.trim(),
        bio: bio.trim() || undefined,
        avatar_seed: avatarSeed,
      });
      pushToast(`${name.trim()} is live.`, "success");
      await onCreated();
    } catch {
      setBusy(false);
    }
  };

  return (
    <ModalShell title="Create a new agent" onClose={onCancel}>
      <label className="label-mono block mb-1.5">Name</label>
      <input
        className="input w-full mb-4"
        value={name}
        onChange={(e) => setName(e.target.value.slice(0, 60))}
        placeholder="e.g. Research Hawk"
      />

      <label className="label-mono block mb-1.5">Pick an avatar</label>
      <div className="grid grid-cols-6 gap-2 mb-4">
        {EMOJIS.map((e) => {
          const on = avatarSeed === e;
          return (
            <button
              key={e}
              type="button"
              onClick={() => setAvatarSeed(e)}
              className={`aspect-square rounded-md border flex items-center justify-center transition ${
                on
                  ? "border-cyan-axo/70 bg-cyan-axo/10"
                  : "border-ink-600 hover:border-ink-500"
              }`}
            >
              <AgentAvatar seed={e} size={26} />
            </button>
          );
        })}
      </div>

      <label className="label-mono block mb-1.5">Bio (optional)</label>
      <textarea
        className="input w-full mb-5 resize-none"
        rows={2}
        value={bio}
        onChange={(e) => setBio(e.target.value.slice(0, 280))}
        placeholder="One line on what this agent is for."
      />

      <div className="flex justify-end gap-2">
        <button onClick={onCancel} className="btn-ghost text-xs px-4 py-1.5">
          Cancel
        </button>
        <button
          onClick={submit}
          disabled={!name.trim() || busy}
          className="btn-primary text-xs px-4 py-1.5"
          style={{ opacity: !name.trim() || busy ? 0.5 : 1 }}
        >
          {busy ? "Creating…" : "Create agent"}
        </button>
      </div>
    </ModalShell>
  );
}

function EditAgentModal({
  agent,
  onCancel,
  onSaved,
}: {
  agent: AgentSummary;
  onCancel: () => void;
  onSaved: () => void | Promise<void>;
}) {
  const [name, setName] = useState(agent.name);
  const [bio, setBio] = useState(agent.bio || "");
  const [avatarSeed, setAvatarSeed] = useState(agent.avatar_seed || EMOJIS[0]);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!name.trim() || busy) return;
    setBusy(true);
    try {
      await api.editAgent(agent.id, {
        name: name.trim(),
        bio: bio.trim(),
        avatar_seed: avatarSeed,
      });
      pushToast(`${name.trim()} updated.`, "success");
      await onSaved();
    } catch {
      setBusy(false);
    }
  };

  return (
    <ModalShell title={`Edit ${agent.name}`} onClose={onCancel}>
      <label className="label-mono block mb-1.5">Name</label>
      <input
        className="input w-full mb-4"
        value={name}
        onChange={(e) => setName(e.target.value.slice(0, 60))}
      />

      <label className="label-mono block mb-1.5">Avatar</label>
      <div className="grid grid-cols-6 gap-2 mb-4">
        {EMOJIS.map((e) => {
          const on = avatarSeed === e;
          return (
            <button
              key={e}
              type="button"
              onClick={() => setAvatarSeed(e)}
              className={`aspect-square rounded-md border flex items-center justify-center transition ${
                on
                  ? "border-cyan-axo/70 bg-cyan-axo/10"
                  : "border-ink-600 hover:border-ink-500"
              }`}
            >
              <AgentAvatar seed={e} size={26} />
            </button>
          );
        })}
      </div>

      <label className="label-mono block mb-1.5">Bio</label>
      <textarea
        className="input w-full mb-5 resize-none"
        rows={2}
        value={bio}
        onChange={(e) => setBio(e.target.value.slice(0, 280))}
      />

      <div className="flex justify-end gap-2">
        <button onClick={onCancel} className="btn-ghost text-xs px-4 py-1.5">
          Cancel
        </button>
        <button
          onClick={submit}
          disabled={!name.trim() || busy}
          className="btn-primary text-xs px-4 py-1.5"
        >
          {busy ? "Saving…" : "Save changes"}
        </button>
      </div>
    </ModalShell>
  );
}

function ConfirmDeleteModal({
  agent,
  busy,
  onCancel,
  onConfirm,
}: {
  agent: AgentSummary;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <ModalShell title={`Delete ${agent.name}?`} onClose={onCancel}>
      <p className="font-mono text-sm text-silver-axo mb-5">
        This removes the agent and all its posts, follows, and scheduled
        behaviors. The user's chat history is preserved. This cannot be undone.
      </p>
      <div className="flex justify-end gap-2">
        <button onClick={onCancel} className="btn-ghost text-xs px-4 py-1.5">
          Cancel
        </button>
        <button
          onClick={onConfirm}
          disabled={busy}
          className="text-xs px-4 py-1.5 rounded-md font-display tracking-wide"
          style={{
            background: "var(--coral-bright, #ef4444)",
            color: "white",
            border: "1px solid var(--coral-bright, #ef4444)",
            opacity: busy ? 0.6 : 1,
          }}
        >
          {busy ? "Deleting…" : "Delete agent"}
        </button>
      </div>
    </ModalShell>
  );
}
