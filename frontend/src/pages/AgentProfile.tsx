import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { AgentAvatar } from "@/components/agent/AgentAvatar";
import { PersonalityRadar } from "@/components/agent/PersonalityRadar";
import { ReputationGauge } from "@/components/agent/ReputationGauge";
import { TimeAgo } from "@/components/ui/TimeAgo";

export function AgentProfilePage() {
  const { agent, refreshAgent } = useAuth();
  const [memories, setMemories] = useState<
    { id: string; memory_type: string; content: string; importance_score: number; created_at: string }[]
  >([]);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(agent?.name || "");
  const [goals, setGoals] = useState<string[]>(agent?.goals || []);
  const [newGoal, setNewGoal] = useState("");

  useEffect(() => {
    api.memoryTimeline().then(setMemories).catch(() => {});
  }, []);

  useEffect(() => {
    setName(agent?.name || "");
    setGoals(agent?.goals || []);
  }, [agent]);

  if (!agent) return null;

  const save = async () => {
    await api.updateAgent({ name, goals });
    await refreshAgent();
    setEditing(false);
  };

  const regenerateAvatar = async () => {
    await api.regenerateAvatar();
    await refreshAgent();
  };

  return (
    <div className="max-w-5xl mx-auto px-6 py-8 space-y-8">
      {/* IDENTITY */}
      <div className="panel p-6 flex flex-col md:flex-row items-start gap-6">
        <AgentAvatar
          seed={agent.avatar_seed}
          personality={agent.personality_vector as any}
          size={140}
        />
        <div className="flex-1 min-w-0">
          <span className="label-mono">AGENT IDENTITY</span>
          {editing ? (
            <input
              className="input text-xl font-display mt-2 mb-3 w-full max-w-md"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          ) : (
            <h1 className="font-display text-white text-3xl mt-2 mb-3">{agent.name}</h1>
          )}
          <div className="font-mono text-xs text-silver-axo space-y-1">
            <div>
              <span className="label-mono mr-2">USER</span>{agent.user_name}
            </div>
            <div>
              <span className="label-mono mr-2">CREATED</span>
              <TimeAgo iso={agent.created_at} />
            </div>
            <div>
              <span className="label-mono mr-2">TASKS COMPLETED</span>
              <span className="text-white tabular-nums">{agent.total_tasks_completed}</span>
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            {editing ? (
              <>
                <button onClick={save} className="btn-primary text-xs">Save</button>
                <button onClick={() => setEditing(false)} className="btn-ghost text-xs">Cancel</button>
              </>
            ) : (
              <button onClick={() => setEditing(true)} className="btn-ghost text-xs">
                Edit identity
              </button>
            )}
            <button onClick={regenerateAvatar} className="btn-ghost text-xs">
              Regenerate avatar
            </button>
          </div>
        </div>
        <ReputationGauge score={agent.reputation_score} size={140} />
      </div>

      {/* PERSONALITY */}
      <div className="grid md:grid-cols-2 gap-6">
        <div className="panel p-6">
          <span className="label-mono">PERSONALITY MATRIX</span>
          <p className="font-mono text-xs text-silver-axo mt-2 mb-3">
            Derived from your conversations and feedback. Updates weekly.
          </p>
          <PersonalityRadar personality={agent.personality_vector as any} />
        </div>

        <div className="panel p-6">
          <span className="label-mono">GOALS</span>
          <p className="font-mono text-xs text-silver-axo mt-2 mb-4">
            Drive proactive agent behavior. Edit anytime.
          </p>
          <ul className="space-y-2 mb-4">
            {goals.map((g, i) => (
              <li key={i} className="panel-inset p-3 flex items-center justify-between gap-2">
                <span className="font-mono text-xs text-white">{g}</span>
                {editing && (
                  <button
                    onClick={() => setGoals(goals.filter((_, j) => j !== i))}
                    className="text-silver-axo hover:text-rose-axo text-xs"
                  >
                    ×
                  </button>
                )}
              </li>
            ))}
          </ul>
          {editing && (
            <div className="flex gap-2">
              <input
                className="input flex-1 text-xs"
                value={newGoal}
                onChange={(e) => setNewGoal(e.target.value)}
                placeholder="Add a goal…"
              />
              <button
                onClick={() => {
                  if (newGoal.trim()) {
                    setGoals([...goals, newGoal.trim()]);
                    setNewGoal("");
                  }
                }}
                className="btn-ghost text-xs"
              >
                Add
              </button>
            </div>
          )}
        </div>
      </div>

      {/* MEMORY TIMELINE */}
      <div className="panel p-6">
        <span className="label-mono">MEMORY TIMELINE</span>
        <p className="font-mono text-xs text-silver-axo mt-2 mb-4">
          What your agent has experienced and learned.
        </p>
        <div className="space-y-2">
          {memories.length === 0 && (
            <p className="font-mono text-xs text-silver-axo/60">No memories yet.</p>
          )}
          {memories.slice(0, 30).map((m) => (
            <div key={m.id} className="panel-inset p-3 flex items-start gap-3">
              <span
                className="w-1.5 rounded-full self-stretch"
                style={{
                  background: `rgba(0,245,212,${0.2 + m.importance_score * 0.7})`,
                }}
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="chip border-ink-600 text-silver-axo">
                    {m.memory_type.replace("_", " ")}
                  </span>
                  <span className="font-mono text-[10px] text-silver-axo/60">
                    <TimeAgo iso={m.created_at} />
                  </span>
                </div>
                <p className="font-mono text-xs text-white leading-relaxed">
                  {m.content}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
