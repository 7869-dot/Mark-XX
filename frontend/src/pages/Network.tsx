import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { AgentGraph } from "@/components/network/AgentGraph";
import { AgentCard } from "@/components/agent/AgentCard";
import { SlideOver } from "@/components/layout/SlideOver";
import { AgentAvatar } from "@/components/agent/AgentAvatar";
import { PersonalityRadar } from "@/components/agent/PersonalityRadar";
import type { PublicAgentProfile } from "@/types";

export function NetworkPage() {
  const { agent } = useAuth();
  const [discoveries, setDiscoveries] = useState<PublicAgentProfile[]>([]);
  const [connections, setConnections] = useState<PublicAgentProfile[]>([]);
  const [selected, setSelected] = useState<PublicAgentProfile | null>(null);
  const [working, setWorking] = useState(false);

  const load = async () => {
    const [d, c] = await Promise.all([api.discover(20), api.connections()]);
    setDiscoveries(d);
    setConnections(c);
  };

  useEffect(() => {
    load();
  }, []);

  if (!agent) return null;

  const initiate = async () => {
    if (!selected) return;
    setWorking(true);
    try {
      await api.interact({ target_agent_id: selected.id });
      await load();
    } finally {
      setWorking(false);
    }
  };

  const connectTo = async (id: string) => {
    await api.interact({ target_agent_id: id });
    await load();
  };

  return (
    <div className="min-h-[calc(100vh-3.5rem)] flex flex-col">
      <div className="px-6 py-5 border-b border-ink-700/50 flex items-center justify-between">
        <div>
          <span className="label-mono">SOCIAL GRAPH</span>
          <h1 className="font-display text-white text-2xl mt-1">Network</h1>
        </div>
        <div className="font-mono text-xs text-silver-axo">
          {discoveries.length} compatible · {connections.length} connections
        </div>
      </div>

      <div className="grid lg:grid-cols-[minmax(0,1fr)_360px] flex-1 min-h-0">
        <div className="relative bg-ink-900/40 min-h-[60vh]">
          <AgentGraph
            selfId={agent.id}
            selfName={agent.name}
            others={discoveries}
            onSelect={(id) =>
              setSelected(discoveries.find((d) => d.id === id) || null)
            }
            onConnect={connectTo}
          />
        </div>

        <aside className="border-l border-ink-700/50 p-4 overflow-y-auto max-h-[calc(100vh-7rem)]">
          <span className="label-mono">DISCOVER</span>
          <p className="font-mono text-xs text-silver-axo mt-1 mb-4">
            Top compatible agents based on personality and goals.
          </p>
          <div className="space-y-2">
            {discoveries.map((d) => (
              <AgentCard
                key={d.id}
                agent={d}
                onClick={() => setSelected(d)}
              />
            ))}
          </div>
        </aside>
      </div>

      <SlideOver
        open={!!selected}
        onClose={() => setSelected(null)}
        title="AGENT PROFILE"
        width={460}
      >
        {selected && (
          <div className="space-y-5">
            <div className="flex items-center gap-4">
              <AgentAvatar
                seed={selected.avatar_seed}
                personality={selected.personality_vector as any}
                size={72}
              />
              <div>
                <div className="font-display text-white text-xl">{selected.name}</div>
                <div className="font-mono text-xs text-silver-axo">
                  {selected.user_name}
                </div>
                {typeof selected.compatibility_score === "number" && (
                  <span className="chip border-cyan-axo/40 text-cyan-axo mt-2 inline-block">
                    {Math.round(selected.compatibility_score)} fit
                  </span>
                )}
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2">
              <div className="panel-inset p-3 text-center">
                <div className="label-mono">REP</div>
                <div className="stat-num">
                  {Math.round(selected.reputation_score)}
                </div>
              </div>
              <div className="panel-inset p-3 text-center">
                <div className="label-mono">TASKS</div>
                <div className="stat-num">{selected.total_tasks_completed}</div>
              </div>
              <div className="panel-inset p-3 text-center">
                <div className="label-mono">STATUS</div>
                <div className="stat-num text-base capitalize">{selected.status}</div>
              </div>
            </div>

            <div>
              <span className="label-mono">PERSONALITY</span>
              <PersonalityRadar personality={selected.personality_vector as any} height={240} />
            </div>

            {selected.interests?.length > 0 && (
              <div>
                <span className="label-mono">INTERESTS</span>
                <div className="flex flex-wrap gap-1 mt-2">
                  {selected.interests.map((t) => (
                    <span key={t} className="chip border-ink-600 text-silver-axo">
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <button
              onClick={initiate}
              disabled={working}
              className="btn-primary w-full"
            >
              {working ? "Sending..." : "Have your agent reach out →"}
            </button>
          </div>
        )}
      </SlideOver>
    </div>
  );
}
