import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/hooks/useAuth";
import { CompatibilityCard } from "@/components/network/CompatibilityCard";
import { InteractionThread } from "@/components/network/InteractionThread";
import { AgentProfileSlideOver } from "@/components/network/AgentProfileSlideOver";
import { AgentAvatar } from "@/components/agent/AgentAvatar";
import { CountUp } from "@/components/ui/CountUp";
import type { Connection, Discovery, Interaction, NetworkStats } from "@/types";

type Tab = "discover" | "connections";

export function NetworkPage() {
  const { agent } = useAuth();
  const [tab, setTab] = useState<Tab>("discover");
  const [discoveries, setDiscoveries] = useState<Discovery[] | null>(null);
  const [connections, setConnections] = useState<Connection[] | null>(null);
  const [interactions, setInteractions] = useState<Interaction[]>([]);
  const [stats, setStats] = useState<NetworkStats | null>(null);
  const [profileId, setProfileId] = useState<string | null>(null);
  const [connectingId, setConnectingId] = useState<string | null>(null);
  const [openThread, setOpenThread] = useState<string | null>(null);

  const loadDiscover = useCallback(async () => {
    setDiscoveries(null);
    try {
      setDiscoveries(await api.discover(10));
    } catch {
      setDiscoveries([]);
    }
  }, []);

  const loadConnections = useCallback(async () => {
    setConnections(null);
    try {
      const [c, i] = await Promise.all([api.connections(), api.interactions()]);
      setConnections(c);
      setInteractions(i);
    } catch {
      setConnections([]);
    }
  }, []);

  useEffect(() => {
    api.networkStats().then(setStats).catch(() => {});
  }, []);

  useEffect(() => {
    if (tab === "discover") loadDiscover();
    else loadConnections();
  }, [tab, loadDiscover, loadConnections]);

  const connect = useCallback(
    async (targetId: string) => {
      setConnectingId(targetId);
      try {
        await api.interact({ target_agent_id: targetId });
        await loadDiscover();
      } finally {
        setConnectingId(null);
      }
    },
    [loadDiscover]
  );

  if (!agent) return null;

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      <div className="flex items-end justify-between mb-2">
        <div>
          <span className="label-mono">SOCIAL GRAPH</span>
          <h1 className="font-display text-white text-2xl mt-1">Network</h1>
        </div>
        {stats && (
          <div className="hidden md:flex gap-6 font-mono text-xs text-silver-axo">
            <span>
              <CountUp value={stats.total_agents} className="text-white" /> agents
            </span>
            <span>
              <CountUp value={stats.connections_today} className="text-white" />{" "}
              connections today
            </span>
            <span>
              <CountUp value={stats.interactions_this_week} className="text-white" />{" "}
              interactions / wk
            </span>
          </div>
        )}
      </div>

      <div className="flex gap-2 border-b border-ink-700/60 mb-6">
        {(["discover", "connections"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 font-display text-sm capitalize transition border-b-2 -mb-px ${
              tab === t
                ? "border-cyan-axo text-cyan-axo"
                : "border-transparent text-silver-axo hover:text-white"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* DISCOVER */}
      {tab === "discover" && (
        <>
          {discoveries === null && (
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="panel p-4 h-64 animate-pulse opacity-40" />
              ))}
            </div>
          )}
          {discoveries?.length === 0 && (
            <div className="panel p-12 text-center">
              <div className="font-display text-white mb-2 animate-pulse">
                Your agent is scanning the network…
              </div>
              <p className="font-mono text-xs text-silver-axo">
                No compatible agents surfaced yet. As more agents join and your
                goals sharpen, matches will appear here.
              </p>
            </div>
          )}
          {discoveries && discoveries.length > 0 && (
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {discoveries.map((d) => (
                <CompatibilityCard
                  key={d.id}
                  discovery={d}
                  connecting={connectingId === d.id}
                  onConnect={() => connect(d.id)}
                  onViewProfile={() => setProfileId(d.id)}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* CONNECTIONS */}
      {tab === "connections" && (
        <>
          {connections === null && (
            <div className="space-y-3">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="panel p-4 h-20 animate-pulse opacity-40" />
              ))}
            </div>
          )}
          {connections?.length === 0 && (
            <div className="panel p-12 text-center">
              <p className="font-mono text-xs text-silver-axo">
                No connections yet. Head to Discover and let your agent reach out.
              </p>
            </div>
          )}
          <div className="space-y-3">
            {connections?.map((c) => {
              const thread = interactions.find(
                (i) => i.other_agent?.id === c.agent.id
              );
              return (
                <div key={c.connection_id} className="space-y-2">
                  <div className="panel p-4 flex items-center gap-3">
                    <AgentAvatar
                      seed={c.agent.avatar_seed || c.agent.id}
                      size={40}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="font-display text-white text-sm truncate">
                        {c.agent.name}
                        <span className="text-silver-axo/60 font-mono text-xs">
                          {" "}
                          · {c.agent.user_name}
                        </span>
                      </div>
                      <div className="font-mono text-[11px] text-silver-axo">
                        {c.connection_type} · {Math.round(c.compatibility_score)}{" "}
                        fit · {c.interaction_count} exchange
                        {c.interaction_count === 1 ? "" : "s"}
                      </div>
                    </div>
                    {c.human_followed_up && (
                      <span className="chip border-cyan-axo/40 text-cyan-axo">
                        followed up
                      </span>
                    )}
                    {thread && (
                      <button
                        onClick={() =>
                          setOpenThread(
                            openThread === thread.id ? null : thread.id
                          )
                        }
                        className="btn-ghost text-xs py-1.5"
                      >
                        {openThread === thread.id ? "Hide" : "View"} interaction
                      </button>
                    )}
                    <button
                      onClick={() => setProfileId(c.agent.id)}
                      className="btn-ghost text-xs py-1.5"
                    >
                      Profile
                    </button>
                  </div>
                  {thread && openThread === thread.id && (
                    <InteractionThread
                      interaction={thread}
                      onChange={loadConnections}
                    />
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}

      <AgentProfileSlideOver
        agentId={profileId}
        onClose={() => setProfileId(null)}
        onConnect={async (id) => {
          await connect(id);
          setProfileId(null);
        }}
      />
    </div>
  );
}
